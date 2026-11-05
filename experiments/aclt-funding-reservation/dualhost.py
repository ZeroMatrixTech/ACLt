# SPDX-License-Identifier: Apache-2.0
"""Opt-in two-physical-host LAN reservation matrix; SSH only controls/provisions."""

if not __debug__:
    raise SystemExit('assert-based validation requires Python without -O/PYTHONOPTIMIZE')

import argparse
import copy
import importlib.util
import subprocess
import tarfile
import time
from wire import *
from ledger import Ledger
from audit import reduce
from fixtures import task

spec = importlib.util.spec_from_file_location('funding_ssh_matrix', AUTH/'dualhost.py')
old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)


class Matrix(old.Matrix):
    def __init__(self, args):
        need(not args.output.resolve().is_relative_to(ROOT), 'output outside repository required')
        super().__init__(args)
        self.script = self.remote+'/experiments/aclt-funding-reservation/'
        self.other = sha(b'other-funding-payer'); self.payee = sha(b'funding-payee')
        self.credentials = {ZERO: secrets.token_bytes(32), self.other: secrets.token_bytes(32)}

    def prepare(self):
        self.ssh_run(['python3', '-c', f"from pathlib import Path; p=Path({self.remote!r}); p.mkdir(parents=True,exist_ok=False); (p/'private').mkdir(mode=0o700); (p/'B').mkdir()"], 'mkdir-remote.log')
        files = []
        for name in ['aclt-funding-reservation', 'aclt-task-authorization', 'aclt-task-commitment', 'aclt-rir-stats-probe']:
            files += [p for p in (ROOT/'experiments'/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
        lock = {p.relative_to(ROOT).as_posix(): sha(regular(p)).hex() for p in sorted(files)}
        (self.out/'source-lock.json').write_text(json.dumps(lock, indent=2)+'\n')
        with tarfile.open(self.out/'source.tar', 'w') as tar:
            for p in files: tar.add(p, arcname=p.relative_to(ROOT), recursive=False)
            tar.add(self.out/'source-lock.json', arcname='source-lock.json')
        self.copy_to(self.out/'source.tar', self.remote+'/source.tar', 'copy-source.log')
        code = f"import pathlib,tarfile,json,hashlib; r=pathlib.Path({self.remote!r}); tarfile.open(r/'source.tar').extractall(r,filter='data'); d=json.loads((r/'source-lock.json').read_text()); assert all(hashlib.sha256((r/n).read_bytes()).hexdigest()==h for n,h in d.items()); print('SOURCE_LOCK_OK',len(d))"
        self.ssh_run(['python3', '-c', code], 'remote-source-check.log')
        env = "import json,platform,sqlite3,ssl; print(json.dumps({'hostname':platform.node(),'kernel':platform.release(),'machine':platform.machine(),'python':platform.python_version(),'sqlite':sqlite3.sqlite_version,'openssl':ssl.OPENSSL_VERSION}))"
        self.run([sys.executable, '-c', env], 'environment-A.log')
        self.ssh_run(['python3', '-c', env], 'environment-B.log')
        self.ssh_run(['python3', '-B', '-W', 'error::ResourceWarning', '-m', 'unittest', 'discover', '-s', self.script+'tests', '-v'], 'remote-unit.log')
        self.key, self.pub = create_keys(self.private/'keys')
        self.copy_to(self.pub, self.pub_path, 'copy-public.log')
        self.enrollment_file = self.private/'enrollment.json'
        self.enrollment_file.write_text(json.dumps({k.hex(): v.hex() for k,v in self.credentials.items()})); self.enrollment_file.chmod(0o600)
        self.ledger = Ledger(self.a/'ledger.sqlite', self.key, self.pub, self.credentials, {ZERO: 300, self.other: 0, self.payee: 0})
        self.start_server()

    def start_server(self):
        index = len(list(self.a.glob('ready-*.json'))); ready = self.a/f'ready-{index}.json'
        with (self.a/f'service-{index}.log').open('xb') as log:
            self.server = subprocess.Popen([sys.executable, '-B', HERE/'service.py', '--database', self.a/'ledger.sqlite', '--private', self.key,
                '--public', self.pub, '--enrollment', self.enrollment_file, '--host', self.args.a_host, '--ready', ready], stdout=log, stderr=subprocess.STDOUT)
        for _ in range(100):
            if ready.exists(): break
            if self.server.poll() is not None: raise RuntimeError('funding server exited')
            time.sleep(.05)
        else: raise RuntimeError('funding readiness timeout')
        port = json.loads(ready.read_text())['port']
        for name, actor in [('payer', ZERO), ('other', self.other)]:
            cfg = {'host': self.args.a_host, 'port': port, 'authority_id': self.ledger.authority.hex(),
                   'requester': actor.hex(), 'secret': self.credentials[actor].hex(), 'public_digest': self.ledger.pin.hex()}
            path = self.private/(name+'.json'); path.write_text(json.dumps(cfg)); path.chmod(0o600)
            self.copy_to(path, self.remote+'/private/'+name+'.json', f'config-{name}-{index}.log')

    def case(self, name, cap, fee, nonce):
        local = self.a/name; local.mkdir()
        remote = self.remote+'/B/'+name
        self.ssh_run(['python3', '-c', f"from pathlib import Path; Path({remote!r}).mkdir()"], name+'-mkdir.log')
        c, identity, artifact, data = task(bytes([nonce])*16)
        raw = policy(c, self.payee, cap, fee)
        for filename, contents in [('policy.cbor', raw), ('task.cbor', c), ('artifact.cbor', artifact), ('input.bin', data)]:
            (local/filename).write_bytes(contents); self.copy_to(local/filename, remote+'/'+filename, name+'-copy-'+filename+'.log')
        return {'name': name, 'remote': remote, 'local': local, 'pid': policy_id(raw), 'task': identity}

    def argv(self, case, op, label, actor='payer'):
        args = ['python3', '-B', self.script+'client.py', op, '--config', self.remote+'/private/'+actor+'.json', '--public', self.pub_path,
                '--report', case['remote']+'/'+label+'.json']
        if op == 'freeze':
            for field, name in [('policy','policy.cbor'), ('commitment','task.cbor'), ('artifact','artifact.cbor'), ('input','input.bin')]: args += ['--'+field, case['remote']+'/'+name]
        elif op in ['reserve','status']: args += ['--policy-id', case['pid'].hex()]
        return args

    def action(self, case, op, label, actor='payer'):
        self.ssh_run(self.argv(case, op, label, actor), case['name']+'-'+label+'.log')
        path = self.out/(case['name']+'-'+label+'-response.json')
        self.copy_from(case['remote']+'/'+label+'.json', path, case['name']+'-'+label+'-collect.log')
        data = json.loads(path.read_text()); cfg = {'authority_id': self.ledger.authority, 'public_digest': self.ledger.pin}
        result = response(bytes.fromhex(data['request']), bytes.fromhex(data['signed_response']), cfg, self.pub)
        return result

    def record(self, name): self.records.append({'scenario': name, 'status': 'PASS'})

    def matrix(self):
        self.prepare()
        normal = self.case('normal',100,30,1)
        assert self.action(normal,'freeze','freeze')['status'] == 'FROZEN'; self.record('freeze-without-debit')
        first = self.action(normal,'reserve','reserve'); assert first['status'] == 'RESERVED'; receipt = first['result']['receipt']; self.record('reserve-frozen-cap')
        duplicate = self.action(normal,'reserve','duplicate'); assert duplicate['status'] == 'DUPLICATE' and duplicate['result']['receipt'] == receipt; self.record('new-nonce-idempotence')
        jobs = []
        for n in range(2):
            with (self.out/f'parallel-{n}.log').open('xb') as log:
                p = subprocess.Popen([*self.ssh, old.shlex.join(self.argv(normal,'reserve','parallel-'+str(n)))], stdout=log, stderr=subprocess.STDOUT)
            self.background.append(p); jobs.append(p)
        assert [p.wait(timeout=20) for p in jobs] == [0,0]; self.record('concurrent-identical-reservations')
        changed = {**decode(regular(normal['local']/'policy.cbor')), 'success_fee': 20}
        path = normal['local']/'changed-policy.cbor'; path.write_bytes(encode(changed)); self.copy_to(path,normal['remote']+'/policy.cbor','changed-policy-copy.log')
        assert self.action(normal,'freeze','changed-policy')['status'] == 'CONFLICT'; self.record('frozen-policy-conflict')
        races = [self.case('race-'+str(n),150,30,n+2) for n in range(2)]
        for case in races: assert self.action(case,'freeze','freeze')['status'] == 'FROZEN'
        jobs = []
        for n,case in enumerate(races):
            with (self.out/f'race-{n}.log').open('xb') as log:
                p = subprocess.Popen([*self.ssh, old.shlex.join(self.argv(case,'reserve','race'))], stdout=log, stderr=subprocess.STDOUT)
            self.background.append(p); jobs.append(p)
        assert [p.wait(timeout=20) for p in jobs] == [0,0]
        statuses = []
        for n,case in enumerate(races):
            path = self.out/f'race-{n}-response.json'; self.copy_from(case['remote']+'/race.json',path,f'race-{n}-collect.log'); statuses.append(json.loads(path.read_text())['response']['status'])
        assert sorted(statuses) == ['INSUFFICIENT','RESERVED']; self.record('different-tasks-compete-without-overdraft')
        insufficient = self.case('insufficient',51,10,4)
        self.action(insufficient,'freeze','freeze'); assert self.action(insufficient,'reserve','reserve')['status'] == 'INSUFFICIENT'; self.record('insufficient-no-partial-lock-or-credit')
        assert self.action(normal,'reserve','wrong-payer','other')['status'] == 'DENIED'; self.record('wrong-payer-denied')
        assert self.action({**normal,'pid':ZERO},'reserve','unknown')['status'] == 'DENIED'; self.record('unknown-policy-denied')
        self.stop_server(); self.start_server()
        query = self.action(normal,'status','restart-status'); again = self.action(normal,'reserve','restart-duplicate')
        assert query['status'] == 'RESERVED' and query['result']['receipt'] == again['result']['receipt'] == receipt; self.record('restart-query-stable-reservation')
        self.stop_server(); failed = self.ssh_run(self.argv(normal,'balance','offline'), 'offline.log', (1,))
        assert failed.returncode == 1; self.record('service-offline-no-local-funding-fallback')
        self.start_server(); balance = self.action(normal,'balance','final-balance')
        assert balance['result'] == {'asset':ASSET,'available':50,'reserved':250}; self.record('conservation-and-reservation-retained')
        self.stop_server()
        bundle, anchor = self.ledger.export()
        (self.out/'ledger-export.json').write_text(json.dumps(bundle,indent=2)+'\n'); (self.out/'checkpoint.cbor').write_bytes(anchor)
        (self.a/'issuer.pub').write_bytes(regular(self.pub))
        reduced = reduce(bundle,anchor,self.pub,self.ledger.pin,sha(anchor))
        assert (reduced['available'],reduced['reserved'],reduced['policies'],reduced['reservations']) == (50,250,4,2)
        (self.out/'reduced.json').write_text(json.dumps(reduced,indent=2)+'\n')
        controls=[]
        for name in ['truncate','projection','event-bytes','wrong-key','wrong-anchor']:
            bad=copy.deepcopy(bundle); pin=self.ledger.pin; ad=sha(anchor)
            if name=='truncate': bad['events'].pop()
            elif name=='projection': bad['projection']['accounts'][ZERO.hex()]['available']+=1
            elif name=='event-bytes':
                e=decode(bytes.fromhex(bad['events'][1])); e['prev']=bytes([1])*32; bad['events'][1]=encode(e).hex()
            elif name=='wrong-key': pin=ZERO
            else: ad=ZERO
            try: reduce(bad,anchor,self.pub,pin,ad)
            except Rejected as exc: controls.append({'control':name,'status':'REJECTED','reason':str(exc)})
            else: raise AssertionError('accepted negative control '+name)
        # Collect only public B files. Config/enrollment stays in remote private/.
        code=f"import tarfile; t=tarfile.open({(self.remote+'/B.tar')!r},'w'); t.add({(self.remote+'/B')!r},arcname='B'); t.close()"
        self.ssh_run(['python3','-c',code],'archive-B.log'); self.copy_from(self.remote+'/B.tar',self.out/'B.tar','collect-B.log')
        with tarfile.open(self.out/'B.tar') as tar: tar.extractall(self.out,filter='data')
        # Validate every retained successful B response against its signed A decision.
        events={event_id(bytes.fromhex(raw)):decode(bytes.fromhex(raw)) for raw in bundle['events']}
        responses=0
        for p in (self.out/'B').rglob('*.json'):
            obj=json.loads(p.read_text()); req=bytes.fromhex(obj['request']); raw=bytes.fromhex(obj['signed_response'])
            parsed=response(req,raw,{'authority_id':self.ledger.authority,'public_digest':self.ledger.pin},self.pub)
            ev=events[parsed['event_ref']]
            assert ev['data']=={'request':req,'status':parsed['status'],'result':parsed['result']}; responses+=1
        return {'status':'PASS','scenarios':len(self.records),'records':self.records,'negative_controls':controls,
                'public_digest':self.ledger.pin.hex(),'anchor_digest':sha(anchor).hex(),'signed_B_responses':responses,
                'reduced':reduced,'scope':'integer prefunded test-asset freeze/reserve only; no payment/refund or execution grant',
                'topology':'A single trusted test funding ledger/service; B authenticated requester over real LAN TCP'}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['peer','a-host','remote-root']: p.add_argument('--'+n,required=True)
    p.add_argument('--output',type=Path,required=True); a=p.parse_args()
    need(a.remote_root.startswith('/') and a.remote_root.rstrip('/')!='/' and '..' not in Path(a.remote_root).parts,'absolute fresh remote root')
    matrix=Matrix(a)
    try:
        result=matrix.matrix(); (matrix.out/'report.json').write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps({'status':'PASS','scenarios':result['scenarios'],'reserved':result['reduced']['reserved']}))
    except BaseException as exc:
        (matrix.out/'report.json').write_text(json.dumps({'status':'FAIL','error':type(exc).__name__+': '+str(exc),'completed_scenarios':matrix.records},indent=2)+'\n'); raise
    finally: matrix.close()
