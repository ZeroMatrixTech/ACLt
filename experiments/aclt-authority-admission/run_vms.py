# SPDX-License-Identifier: Apache-2.0
"""QEMU/ext4 fault evidence. All outputs are new; never edit old VM evidence."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from authority import Authority
from protocol import canonical, claim, create_keys, digest, envelope, exchange, verified_reply


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def post(port, obj, timeout=40):
    req = urllib.request.Request(f'http://127.0.0.1:{port}/', data=canonical(obj),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as f:
            return json.load(f)
    except urllib.error.HTTPError as e:
        return json.load(e)


class Run:
    def __init__(self, args):
        self.args = args
        self.out = args.output.absolute()
        self.out.mkdir(parents=True, exist_ok=False)
        self.events, self.faults, self.vms = [], [], []
        self.record_lock = threading.Lock()
        self.rng = random.Random(args.seed)

    def record(self, name, evidence, passed=None):
        row = {'name': name, 'evidence': evidence}
        if passed is not None:
            row['passed'] = bool(passed)
        with self.record_lock:
            self.events.append(row)
            (self.out/'events.json').write_text(json.dumps(self.events, indent=2)+'\n')
        print(name, str(evidence)[:300], flush=True)
        if passed is False:
            raise AssertionError((name, evidence))

    def disk(self, path, files):
        with path.open('wb') as f:
            f.truncate(96*1024*1024)
        subprocess.run(['mkfs.ext4', '-q', '-F', '-m', '0', str(path)], check=True)
        for name, source in files.items():
            r = subprocess.run(['debugfs', '-w', '-R', f'write {source} /{name}', str(path)], capture_output=True)
            if r.returncode or b'File not found' in r.stderr:
                raise RuntimeError(r.stderr.decode())

    def prepare(self):
        guest = self.out/'guest-root'
        shutil.copytree(self.args.runtime_root, guest,
                        ignore=shutil.ignore_patterns('repo', 'experiment', '__pycache__'))
        experiment = guest/'experiment'
        experiment.mkdir()
        for p in ROOT.glob('*.py'):
            shutil.copy2(p, experiment/p.name)
        worker = ROOT.parent/'aclt-minimal-verifier-state3/build/worker'
        shutil.copy2(worker, experiment/'worker-bin')
        # Preserve existing lib paths; place OpenSSL and all of its actual host dependencies.
        binary = Path(shutil.which('openssl'))
        target = guest/str(binary).lstrip('/')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(binary, target)
        ldd = subprocess.check_output(['ldd', str(binary)]).decode()
        for line in ldd.splitlines():
            for word in line.split():
                if word.startswith('/'):
                    src = Path(word)
                    dest = guest/str(src).lstrip('/')
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src.resolve(), dest)
        (self.out/'openssl-ldd.txt').write_text(ldd)
        init = (guest/'init').read_text()
        init = init.replace('chmod 777 /data /evidence', 'chown -R 1000:1000 /data /evidence\nchmod 700 /data /evidence')
        (guest/'init').write_text(init)
        (experiment/'boot.py').write_text('''import json,os,pathlib,runpy,sys
args=dict(x.split('=',1) for x in pathlib.Path('/proc/cmdline').read_text().split() if '=' in x)
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
p=pathlib.Path('/evidence')/('boot-'+boot+'.json');p.write_text(json.dumps({'boot':boot,'role':args['role']}))
with p.open('rb') as f:os.fsync(f.fileno())
os.setgid(1000);os.setuid(1000);sys.path.insert(0,'/experiment')
if args['role']=='node':runpy.run_path('/experiment/vm_node.py',run_name='__main__')
else:
 sys.argv=['server.py',args['role'],'--config','/data/config.json','--host','0.0.0.0','--port','9000','--test-admin-port','9001']
 runpy.run_path('/experiment/server.py',run_name='__main__')
''')
        paths = [Path('.')] + sorted(p.relative_to(guest) for p in guest.rglob('*'))
        with (self.out/'guest.cpio').open('wb') as f:
            subprocess.run(['cpio','--null','-o','--format=newc'], cwd=guest,
                           input=b'\0'.join(str(p).encode() for p in paths)+b'\0',
                           stdout=f, stderr=subprocess.PIPE, check=True)
        self.record('guest-built', {'kernel': str(self.args.kernel), 'acceleration': self.args.accel,
                    'kernel_sha256': digest(self.args.kernel.read_bytes()),
                    'initramfs_sha256': digest((self.out/'guest.cpio').read_bytes()),
                    'worker_sha256': digest(worker.read_bytes()),
                    'sources': {p.name: digest(p.read_bytes()) for p in ROOT.glob('*.py')}})

    def fixture(self, name, obj):
        p = self.out/(name+'.json')
        p.write_bytes(canonical(obj))
        return p

    def client(self, task, op='audit', key='a', **extra):
        credential = self.manifest['keys'][key]
        config = dict(self.base, key=key, **credential)
        message = envelope(config, op, '00000000-0000-0000-0000-000000000000', task=task, **extra)
        reply = exchange('127.0.0.1', self.authority.port, message, timeout=10)
        return verified_reply(reply, self.public, message, config)

    def job(self, node, action, task=None, **extra):
        return post(node.control, dict(action=action, **({'task': task} if task else {}), **extra))

    def initialize(self):
        private, self.public = create_keys(self.out/'test-keys')
        names = ['normal','reserved-rollback','accepted-rollback','parallel','conflict','drop-reserve',
                 'drop-submit','partition','unfinished','invalid','other-units','alias-check',
                 'reserve-before','reserve-after','submit-before','submit-after']
        names += [f'random-{op}-{i}' for op in ['reserve','submit'] for i in range(self.args.random_cuts)]
        tasks = {n: {'values': [3+i,-1,8,0,-7,12], 'chunk': 4, 'units': ['A','B']} for i,n in enumerate(names)}
        tasks['normal-alias'] = tasks['normal']
        self.manifest = {'keys': {k: {'unit': u, 'secret': 'v2-privileged-fixture-'+k}
                                  for k,u in [('a','A'),('a-alias','A'),('b','B'),('c','C')]}, 'tasks': tasks}
        database = self.out/'initial-authority.sqlite'
        initial = Authority(self.manifest, database, private, self.public, True)
        self.base = {'authority_id': initial.authority_id, 'config_digest': initial.config_digest,
                     'public_digest': initial.public_digest, 'tasks': tasks}
        authority_config = dict(manifest=self.manifest, database='/data/authority.sqlite',
                                private_key='/data/authority.key', public_key='/data/authority.pub')
        self.authority = VM(self, 'authority', 'authority', {
            'config.json': self.fixture('authority-config', authority_config), 'authority.sqlite': database,
            'authority.key': private, 'authority.pub': self.public})
        gateway_config = self.fixture('gateway-config', {'host': '10.0.2.2', 'port': self.authority.port, 'timeout': 10})
        self.primary = VM(self, 'gateway-primary', 'gateway', {'config.json': gateway_config})
        self.clone = VM(self, 'gateway-clone', 'gateway', {'config.json': gateway_config})
        shutil.copy2(self.primary.data, self.clone.data)
        self.snapshot = self.out/'gateway-before.raw'
        shutil.copy2(self.primary.data, self.snapshot)
        node_config = self.fixture('node-config', {'base': self.base,
                       'keys': self.manifest['keys'],
                       'gateways': {'primary': self.primary.port, 'clone': self.clone.port}})
        self.a = VM(self, 'node-a', 'node', {'config.json': node_config, 'authority.pub': self.public})
        self.b = VM(self, 'node-b', 'node', {'config.json': node_config, 'authority.pub': self.public})
        (self.out/'client-pins.json').write_bytes(canonical(self.base))
        with concurrent.futures.ThreadPoolExecutor(5) as pool:
            list(pool.map(lambda vm: vm.start(), self.vms))
        # Probe only read operations. Never hide a failed mutating request with a retry.
        for gateway in [self.primary,self.clone]:
            cfg=dict(self.base,key='a',**self.manifest['keys']['a'])
            message=envelope(cfg,'audit','00000000-0000-0000-0000-000000000000',task='normal')
            verified_reply(exchange('127.0.0.1',gateway.port,message,timeout=20),self.public,message,cfg)

    def restore_gateway(self):
        self.primary.kill()
        shutil.copy2(self.snapshot, self.primary.data)
        self.primary.start()

    def matrix(self):
        a, b = self.a, self.b
        first = self.job(a, 'compute', 'normal')
        self.record('R01-normal', first, first.get('reply',{}).get('status') == 'accepted')
        alias = self.job(b, 'reserve', 'normal-alias', key='a-alias')
        self.record('R11-alias', alias, alias.get('status') == 'consumed')
        old = self.job(a, 'info');a.kill();a.start()
        again = self.job(a, 'compute', 'normal');replay = self.job(a, 'replay', 'normal')
        new = self.job(a, 'info')
        self.record('worker-reboot-no-resume', [again,replay],
                    old['boot'] != new['boot'] and old['files'] == new['files']
                    and 'error' in again and replay.get('receipt') == first['reply']['receipt'])
        reserved = self.job(a, 'reserve', 'reserved-rollback')
        self.restore_gateway()
        denied = self.job(b, 'compute', 'reserved-rollback')
        self.record('R02-gateway-snapshot-before-reserve', [reserved,denied],
                    reserved.get('status') == 'reserved' and denied.get('computed') is False
                    and denied.get('reservation',{}).get('status') == 'consumed')
        accepted = self.job(a, 'compute', 'accepted-rollback')
        self.restore_gateway()
        duplicate = self.job(a, 'replay', 'accepted-rollback')
        self.record('R03-gateway-snapshot-before-accept', [accepted,duplicate],
                    duplicate == {'status':'duplicate','receipt':accepted['reply']['receipt']})
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            x=pool.submit(self.job,a,'compute','parallel');y=pool.submit(self.job,b,'compute','parallel',gateway='clone')
            parallel = [x.result(),y.result()]
        self.record('R04-live-cloned-gateways', parallel,
                    sum(r.get('computed') is True for r in parallel) == 1 and self.client('parallel')['count']==1)
        good = self.job(a,'compute','conflict');conflict = self.job(a,'inject','conflict',changes={'rows':'WRONG\n'})
        duplicate = self.job(a,'replay','conflict',gateway='clone')
        self.record('R05-conflict-and-duplicate', [conflict,duplicate],
                    conflict.get('status')=='conflict' and conflict.get('receipt')==good['reply']['receipt']
                    and duplicate.get('receipt')==good['reply']['receipt'] and self.client('conflict')['count']==1)
        post(self.primary.control, {'action':'drop'})
        lost = self.job(a,'compute','drop-reserve');retry = self.job(b,'compute','drop-reserve',gateway='clone')
        self.record('R06-lost-reserve-reply',[lost,retry], 'error' in lost and retry.get('computed') is False
                    and self.client('drop-reserve')['reserved'] and self.client('drop-reserve')['count']==0)
        self.job(a,'compute','drop-submit',prepare_only=True)
        post(self.primary.control,{'action':'drop'})
        lost = self.job(a,'replay','drop-submit');accepted = self.client('drop-submit')
        replay = self.job(a,'replay','drop-submit',gateway='clone')
        self.record('R07-lost-submit-reply',[lost,replay], 'error' in lost and accepted['count']==1
                    and replay=={'status':'duplicate','receipt':accepted['receipt']})
        self.job(a,'compute','partition',prepare_only=True)
        self.primary.link(False)
        lost = self.job(a,'replay','partition')
        during = self.client('partition')
        self.primary.link(True)
        replay = self.job(a,'replay','partition')
        self.record('R08-actual-gateway-NIC-partition',[lost,during,replay],
                    'error' in lost and during['count']==0 and replay.get('status') in ['accepted','duplicate']
                    and replay.get('receipt')==self.client('partition')['receipt'] and self.client('partition')['count']==1)
        self.authority.link(False)
        no_grant=self.job(a,'compute','unfinished')
        worker_info=self.job(a,'info')
        self.authority.link(True)
        self.record('R08-actual-authority-NIC-partition',no_grant,
                    'error' in no_grant and self.client('unfinished')['count']==0
                    and not any(n.endswith('.started') and n.startswith(claim(self.base['tasks']['unfinished']['values']))
                                for n in worker_info['files']))
        self.job(a,'compute','invalid',prepare_only=True)
        invalid=self.job(a,'inject','invalid',changes={'rows':'WRONG\n'});retry=self.job(a,'replay','invalid')
        self.record('R12-invalid-first',[invalid,retry], invalid.get('status')=='invalid' and retry.get('status')=='rejected')
        one=self.job(a,'compute','other-units');two=self.job(b,'compute','other-units',key='b',gateway='clone')
        self.record('R12-independent-enrolled-units',[one,two],
                    one.get('reply',{}).get('status')=='accepted' and two.get('reply',{}).get('status')=='accepted')

    def cuts(self):
        for op in ['reserve','submit']:
            for moment in ['before','after']:
                task=f'{op}-{moment}'
                if op=='submit':
                    self.job(self.a,'compute',task,prepare_only=True)
                stage=f'{op}-{moment}-commit'
                post(self.authority.control,{'action':'pause','stage':stage})
                with concurrent.futures.ThreadPoolExecutor(1) as pool:
                    pending=pool.submit(self.job,self.a,'compute' if op=='reserve' else 'replay',task)
                    self.authority.wait('CHECKPOINT '+stage)
                    self.authority.kill();self.authority.start();interrupted=pending.result()
                state=self.client(task)
                if op=='reserve':
                    expected=moment=='after'
                    self.record('R09-'+stage,{'state':state,'interrupted':interrupted},state['reserved']==expected)
                    retry=self.job(self.b,'compute',task)
                    self.record('R09-'+stage+'-retry',retry,
                                retry.get('reservation',{}).get('status')=='consumed' if expected else retry.get('reply',{}).get('status')=='accepted')
                else:
                    self.record('R09-'+stage,{'state':state,'interrupted':interrupted},state['count']==int(moment=='after'))
                    replay=self.job(self.a,'replay',task)
                    self.record('R09-'+stage+'-replay',replay,
                                replay.get('status')==('duplicate' if moment=='after' else 'accepted')
                                and (moment!='after' or replay['receipt']==state['receipt']))
                self.faults.append({'task':task,'stage':stage,'state':state,'interrupted':interrupted})
                (self.out/'faults.json').write_text(json.dumps(self.faults,indent=2)+'\n')
        for op in ['reserve','submit']:
            for i in range(self.args.random_cuts):
                task=f'random-{op}-{i}'
                if op=='submit':
                    self.job(self.a,'compute',task,prepare_only=True)
                delay=self.rng.uniform(0, .25)
                with concurrent.futures.ThreadPoolExecutor(1) as pool:
                    pending=pool.submit(self.job,self.a,'compute' if op=='reserve' else 'replay',task)
                    time.sleep(delay)
                    self.authority.kill()
                    trace=[line for line in self.authority.log.read_text().splitlines() if line.startswith('TX_STAGE ')]
                    self.authority.start();reply=pending.result()
                state=self.client(task)
                if op=='reserve':
                    retry=self.job(self.b,'compute',task)
                    if state['reserved']:
                        passed=retry.get('reservation',{}).get('status')=='consumed'
                    else:
                        passed=retry.get('reply',{}).get('status')=='accepted'
                else:
                    retry=self.job(self.a,'replay',task)
                    passed=retry.get('status') in ['accepted','duplicate'] and self.client(task)['count']==1
                    if state['count']:
                        passed=passed and retry['receipt']==state['receipt']
                evidence={'task':task,'delay_seconds':delay,'interrupted':reply,'state':state,'retry':retry,
                          'trace_before_cut':trace,
                          'observed_commit':state['reserved'] if op=='reserve' else bool(state['count'])}
                self.record('R09-random-'+op+'-'+str(i),evidence,passed)
                self.faults.append(evidence)
                (self.out/'faults.json').write_text(json.dumps(self.faults,indent=2)+'\n')

    def missing_ledger(self):
        self.authority.kill()
        missing=VM(self,'missing-authority','authority',{})
        shutil.copy2(self.authority.data, missing.data)
        recovered=subprocess.run(['e2fsck','-p',str(missing.data)],capture_output=True)
        (missing.path/'pre-mutation-recovery.log').write_bytes(recovered.stdout+recovered.stderr)
        if recovered.returncode not in (0,1):
            raise RuntimeError('cannot recover missing-ledger fixture')
        subprocess.run(['debugfs','-w','-R','rm /authority.sqlite',str(missing.data)],check=True,capture_output=True)
        try:
            missing.start()
        except RuntimeError as exc:
            self.record('R10-missing-authority-refused',str(exc)[-2000:], 'FileNotFoundError' in str(exc))
        else:
            raise AssertionError('missing authority ledger was recreated')
        finally:
            missing.kill()

    def run(self):
        try:
            self.prepare();self.initialize();self.matrix();self.cuts()
            final={name:{key:self.client(name,key=key) for key in ['a','b']}
                   for name in self.manifest['tasks']}
            (self.out/'final-audit.json').write_text(json.dumps(final,indent=2)+'\n')
            infos={vm.name:self.job(vm,'info') for vm in [self.a,self.b]}
            (self.out/'final-node-info.json').write_text(json.dumps(infos,indent=2)+'\n')
            self.missing_ledger()
            result={'passed':True,'scenarios':sum('passed' in e for e in self.events),
                    'random_seed':self.args.seed,'random_cuts_per_operation':self.args.random_cuts,
                    'deterministic_authority_cuts':4,'acceleration':self.args.accel,
                    'scope':'controlled QEMU/ext4; trusted external authority not rolled back; enrolled simulation identities'}
            (self.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        finally:
            for vm in self.vms:
                vm.kill()


class VM:
    def __init__(self, run, name, role, files):
        self.run,self.name,self.role=run,name,role
        self.path=run.out/'vms'/name;self.path.mkdir(parents=True)
        self.data,self.evidence=self.path/'data.raw',self.path/'evidence.raw'
        run.disk(self.data,files);run.disk(self.evidence,{})
        self.port,self.control,self.qmp=free_port(),free_port(),free_port()
        self.n=0;self.process=None;self.handle=None
        run.vms.append(self)

    def start(self):
        self.n+=1;self.log=self.path/f'boot-{self.n}.log'
        cmd=['qemu-system-x86_64','-accel',self.run.args.accel,'-cpu','max','-m','768','-smp','2',
             '-kernel',str(self.run.args.kernel),'-initrd',str(self.run.out/'guest.cpio'),
             '-append',f'console=ttyS0 quiet rootfstype=ramfs panic=1 role={self.role}',
             '-drive',f'file={self.data},format=raw,if=virtio,cache=none',
             '-drive',f'file={self.evidence},format=raw,if=virtio,cache=none',
             '-netdev',f'user,id=net0,hostfwd=tcp:127.0.0.1:{self.port}-:9000,hostfwd=tcp:127.0.0.1:{self.control}-:9001',
             '-device','e1000,id=nic0,netdev=net0','-qmp',f'tcp:127.0.0.1:{self.qmp},server=on,wait=off',
             '-display','none','-monitor','none','-serial','stdio','-no-reboot']
        (self.path/f'boot-{self.n}-command.json').write_text(json.dumps(cmd,indent=2)+'\n')
        self.handle=self.log.open('wb');self.process=subprocess.Popen(cmd,stdout=self.handle,stderr=subprocess.STDOUT)
        self.wait('NODE_READY' if self.role=='node' else 'READY '+self.role,timeout=120)
        deadline=time.monotonic()+30
        while True:
            try:
                response=post(self.control,{'action':'info' if self.role=='node' else 'health'},timeout=2)
                if (response.get('boot') if self.role=='node' else response.get('ok')):
                    break
            except (OSError,ValueError):
                pass
            if time.monotonic()>deadline:
                raise TimeoutError('control health failed: '+self.name)
            time.sleep(.1)
        self.run.record('boot-'+self.name,{'generation':self.n})

    def wait(self,needle,timeout=30):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            text=self.log.read_text(errors='replace')
            if needle in text:
                return
            if self.process.poll() is not None:
                raise RuntimeError(self.name+' exited: '+text[-4000:])
            time.sleep(.05)
        raise TimeoutError(self.name+' waiting '+needle+': '+text[-4000:])

    def kill(self):
        if self.process is not None and self.process.poll() is None:
            self.process.kill();self.process.wait(timeout=15)
            self.run.record('hard-stop-'+self.name,{'generation':self.n})
        if self.handle is not None:
            self.handle.close();self.handle=None

    def link(self,up):
        with socket.create_connection(('127.0.0.1',self.qmp),timeout=5) as sock:
            f=sock.makefile('rwb');json.loads(f.readline())
            for command in [{'execute':'qmp_capabilities'},
                            {'execute':'set_link','arguments':{'name':'nic0','up':up}}]:
                f.write(canonical(command)+b'\n');f.flush()
                while True:
                    result=json.loads(f.readline())
                    if 'return' in result:
                        break
                    if 'error' in result:
                        raise RuntimeError(result)
        self.run.record('NIC-'+self.name,{'up':up})


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--runtime-root',type=Path,required=True)
    p.add_argument('--kernel',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--accel',choices=['tcg','kvm'],default='tcg')
    p.add_argument('--random-cuts',type=int,default=20)
    p.add_argument('--seed',type=int,default=20261020)
    Run(p.parse_args()).run()
