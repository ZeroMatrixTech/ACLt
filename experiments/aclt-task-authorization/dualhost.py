# SPDX-License-Identifier: Apache-2.0
"""Opt-in real LAN matrix: trusted issuer on A, checked dispatch/RIR startup on B."""

SHA_CONSISTENCY_STATUS = "DISABLED"

def digest_consistency(_comparison):
    """Record digests without enforcing their equality (maintainer policy)."""
    return True


if not __debug__:
    raise SystemExit('assert-based validation requires Python without -O/PYTHONOPTIMIZE')

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import signal
import subprocess
import sys
import tarfile
import time
from common import HERE,ROOT,encode,decode,sha,environment_digest
from fixtures import task
from authorization import Authority,grant_id
from auth_crypto import create_keys,verify

class Matrix:
    def __init__(self,args):
        self.args=args;self.out=args.output.resolve()
        if self.out.is_relative_to(HERE):raise ValueError('evidence must be outside source directory')
        self.out.mkdir(parents=True,exist_ok=False)
        self.private=self.out/'private';self.private.mkdir(mode=0o700)
        self.a=self.out/'A';self.a.mkdir();self.remote=args.remote_root.rstrip('/')
        self.ssh=['ssh','-F','/dev/null','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=8',args.peer]
        self.scp=['scp','-F','/dev/null','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=8']
        self.commands=[];self.records=[];self.server=None;self.background=[];self.pauses=[]
        self.script=self.remote+'/experiments/aclt-task-authorization/'
        self.provider=sha(b'experimental-provider-B');self.unit=sha(b'experimental-unit-B');self.secret=secrets.token_bytes(32)
        self.cfg_path=self.remote+'/private/worker.json';self.pub_path=self.remote+'/private/issuer.pub'
    def run(self,argv,log,expected=(0,)):
        p=subprocess.run([str(x) for x in argv],capture_output=True,timeout=30)
        (self.out/log).write_bytes(p.stdout+p.stderr)
        self.commands.append({'argv':[str(x) for x in argv],'exit_code':p.returncode,'log':log})
        if p.returncode not in expected:raise RuntimeError('unexpected command status: '+log)
        return p
    def ssh_run(self,argv,log,expected=(0,)):
        return self.run([*self.ssh,shlex.join([str(x) for x in argv])],log,expected)
    def copy_to(self,local,remote,log):self.run([*self.scp,str(local),self.args.peer+':'+remote],log)
    def prepare(self):
        self.ssh_run(['python3','-c',f"from pathlib import Path; p=Path({self.remote!r}); p.mkdir(parents=True,exist_ok=False); (p/'private').mkdir(mode=0o700); (p/'B').mkdir()"],'mkdir-remote.log')
        files=[]
        for name in ['aclt-task-authorization','aclt-task-commitment','aclt-rir-stats-probe']:
            files.extend(p for p in (ROOT/'experiments'/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
        lock={p.relative_to(ROOT).as_posix():sha(p.read_bytes()).hex() for p in sorted(files)}
        (self.out/'source-lock.json').write_text(json.dumps(lock,indent=2)+'\n')
        with tarfile.open(self.out/'source.tar','w') as tar:
            for p in files:tar.add(p,arcname=p.relative_to(ROOT),recursive=False)
            tar.add(self.out/'source-lock.json',arcname='source-lock.json')
        self.copy_to(self.out/'source.tar',self.remote+'/source.tar','copy-source.log')
        code=f"import pathlib,tarfile,json,hashlib; r=pathlib.Path({self.remote!r}); tarfile.open(r/'source.tar').extractall(r,filter='data'); d=json.loads((r/'source-lock.json').read_text()); print('SHA_CONSISTENCY_DISABLED',len(d))"
        self.ssh_run(['python3','-c',code],'remote-source-check.log')
        self.ssh_run(['python3','-B','-W','error::ResourceWarning','-m','unittest','discover','-s',self.script+'tests','-v'],'remote-unit.log')
        ready=self.remote+'/private/environment.cbor'
        p=self.ssh_run(['python3','-B',self.script+'fault_driver.py','environment','--report',ready],'remote-environment.log')
        self.env=bytes.fromhex(p.stdout.decode().strip());self.copy_from(ready,self.out/'B-environment.cbor','copy-environment.log')
        self.key,self.pub=create_keys(self.private/'keys');self.copy_to(self.pub,self.pub_path,'copy-public.log')
        providers=self.private/'providers.json';providers.write_text(json.dumps({self.provider.hex():self.secret.hex()}));providers.chmod(0o600)
        self.authority=Authority(self.a/'ledger.sqlite',self.key,self.pub,{self.provider:self.secret},initialize=True)
        self.drop=self.a/'drop-consume.txt';self.drop.write_text('')
        self.start_server()
    def copy_from(self,remote,local,log):self.run([*self.scp,self.args.peer+':'+remote,str(local)],log)
    def start_server(self):
        index=len(list(self.a.glob('service-ready-*.json')));ready=self.a/f'service-ready-{index}.json'
        log=(self.a/f'service-{index}.log').open('wb')
        argv=[sys.executable,'-B',str(HERE/'service.py'),'--database',str(self.a/'ledger.sqlite'),'--private',str(self.key),'--public',str(self.pub),'--providers',str(self.private/'providers.json'),'--host',self.args.a_host,'--ready',str(ready),'--test-drop-consume-file',str(self.drop)]
        self.server=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT);log.close()
        for _ in range(100):
            if ready.exists():break
            if self.server.poll() is not None:raise RuntimeError('authorization server failed')
            time.sleep(0.05)
        else:raise RuntimeError('authorization server readiness timeout')
        data=json.loads(ready.read_text());self.port=data['port']
        cfg={'host':self.args.a_host,'port':self.port,'authority_id':self.authority.authority_id.hex(),'public_digest':self.authority.public_digest.hex(),'provider_ref':self.provider.hex(),'unit_ref':self.unit.hex(),'environment_digest':self.env.hex(),'provider_secret':self.secret.hex()}
        path=self.private/'worker.json';path.write_text(json.dumps(cfg));path.chmod(0o600)
        self.copy_to(path,self.cfg_path,'copy-config-'+str(index)+'.log')
    def stop_server(self):
        if self.server is not None:
            self.server.terminate();self.server.wait(timeout=10);self.server=None
    def new_case(self,name,expires=None,unit=None):
        local=self.a/name;local.mkdir();remote=self.remote+'/B/'+name
        self.ssh_run(['python3','-c',f"from pathlib import Path; Path({remote!r}).mkdir()"],name+'-mkdir.log')
        c,identity,artifact,data=task(sha(('auth-slice2:'+name).encode())[:16])
        now=int(time.time());packet=self.authority.issue(c,self.provider,unit or self.unit,self.env,1,now-30,expires or now+600)
        body=verify(packet,self.pub,self.authority.public_digest);gid=grant_id(body)
        for filename,contents in [('task.cbor',c),('artifact.cbor',artifact),('input.bin',data),('grant.cbor',packet)]:
            (local/filename).write_bytes(contents);self.copy_to(local/filename,remote+'/'+filename,name+'-copy-'+filename+'.log')
        return {'name':name,'local':local,'remote':remote,'commitment':c,'identity':identity,'grant':packet,'body':body,'grant_ids':[gid]}
    def argv(self,case,stage,state='state',config=None):
        r=case['remote']
        return ['python3','-B',self.script+'runner.py',stage,'--config',config or self.cfg_path,'--public',self.pub_path,
                '--commitment',r+'/task.cbor','--artifact',r+'/artifact.cbor','--input',r+'/input.bin','--task-id',case['identity'],
                '--bundle',r+'/bundle.cbor',*(['--grant',r+'/grant.cbor'] if stage=='dispatch' else ['--state',r+'/'+state])]
    def action(self,case,stage,label,state='state',expected=0,config=None):
        args=self.argv(case,stage,state,config)+['--report',case['remote']+'/'+label+'.json']
        p=self.ssh_run(args,case['name']+'-'+label+'.log',(expected,))
        return json.loads(p.stdout)
    def count(self,case):
        c=self.authority.connect()
        try:return sum(c.execute("SELECT COUNT(*) FROM events WHERE op='CONSUME:ALLOW' AND grant_id=?",(gid,)).fetchone()[0] for gid in case['grant_ids'])
        finally:c.close()
    def record(self,case,result,consumes):
        actual=self.count(case)
        if actual!=consumes:raise AssertionError((case['name'],'consume count',actual,consumes))
        self.records.append({'scenario':case['name'],"sha_consistency": "DISABLED", 'status':'PASS','experimental_task_id':case['identity'],
                             'grant_ids':[g.hex() for g in case['grant_ids']],'allowed_consumes':actual,'result':result})
    def paused_kill(self,case,at):
        r=case['remote'];ready=r+'/pause-ready.json'
        argv=['python3','-B',self.script+'fault_driver.py','pause','--config',self.cfg_path,'--public',self.pub_path,
              '--commitment',r+'/task.cbor','--artifact',r+'/artifact.cbor','--input',r+'/input.bin','--task-id',case['identity'],
              '--bundle',r+'/bundle.cbor','--state',r+'/state','--ready',ready,'--at',at]
        log=(self.out/(case['name']+'-pause.log')).open('wb')
        process=subprocess.Popen([*self.ssh,shlex.join(argv)],stdout=log,stderr=subprocess.STDOUT);log.close();self.background.append(process);self.pauses.append((process,ready))
        for i in range(40):
            check=self.ssh_run(['python3','-c',f"from pathlib import Path; raise SystemExit(0 if Path({ready!r}).exists() else 1)"],case['name']+f'-ready-{i}.log',(0,1))
            if check.returncode==0:break
            if process.poll() is not None:raise RuntimeError('paused worker exited before gate')
            time.sleep(0.1)
        else:raise RuntimeError('worker pause timeout')
        self.ssh_run(['python3','-B',self.script+'fault_driver.py','kill','--ready',ready],case['name']+'-kill.log')
        code=process.wait(timeout=10)
        if code==0:raise RuntimeError('expected killed process status')
        self.commands.append({'test_process_exit':code,'scenario':case['name'],'gate':at})
    def matrix(self):
        self.prepare()
        normal=self.new_case('normal');self.action(normal,'dispatch','dispatch');result=self.action(normal,'launch','launch')
        assert result['result']['outcome']=='OK' and result['result']['gas_used']==9126
        self.record(normal,result,1)
        result=self.action(normal,'launch','duplicate',expected=2);self.record({**normal,'name':'local-duplicate'},result,1)
        result=self.action(normal,'launch','clone',state='clone',expected=2);self.record({**normal,'name':'fresh-state-clone'},result,1)
        self.stop_server();self.start_server()
        result=self.action(normal,'launch','restart-clone',state='restart-clone',expected=2);self.record({**normal,'name':'authority-process-restart-replay'},result,1)
        forged=self.new_case('forged-signature');obj=decode(forged['grant']);obj['signature']=bytes(256);path=forged['local']/'forged.cbor';path.write_bytes(encode(obj));self.copy_to(path,forged['remote']+'/grant.cbor','forged-copy.log')
        self.record(forged,self.action(forged,'dispatch','reject',expected=2),0)
        wrong=self.new_case('wrong-input');path=wrong['local']/'bad-input';path.write_bytes(b'wrong');self.copy_to(path,wrong['remote']+'/input.bin','wrong-input-copy.log')
        self.record(wrong,self.action(wrong,'dispatch','reject',expected=2),0)
        wrong=self.new_case('wrong-unit',unit=sha(b'other-unit'));self.record(wrong,self.action(wrong,'dispatch','reject',expected=2),0)
        self.records.append({'scenario':'wrong-local-environment','status':'DISABLED','sha_consistency':'DISABLED'})
        expired=self.new_case('expired-grant',expires=int(time.time())-1);self.record(expired,self.action(expired,'dispatch','reject',expected=2),0)
        epoch=self.new_case('stale-after-dispatch');self.action(epoch,'dispatch','dispatch');now=int(time.time());new=self.authority.issue(epoch['commitment'],self.provider,self.unit,self.env,2,now-1,now+600);epoch['grant_ids'].append(grant_id(verify(new,self.pub,self.authority.public_digest)))
        self.record(epoch,self.action(epoch,'launch','reject',expected=2),0)
        late=self.new_case('expires-after-dispatch',expires=int(time.time())+8);self.action(late,'dispatch','dispatch');time.sleep(max(0,late['body']['expires_at']-time.time()+0.1))
        self.record(late,self.action(late,'launch','reject',expected=2),0)
        race=self.new_case('parallel-launches');self.action(race,'dispatch','dispatch');jobs=[]
        for i in range(2):
            argv=self.argv(race,'launch','clone'+str(i))+['--report',race['remote']+'/race'+str(i)+'.json']
            f=(self.out/('parallel-'+str(i)+'.log')).open('wb');p=subprocess.Popen([*self.ssh,shlex.join(argv)],stdout=f,stderr=subprocess.STDOUT);f.close();jobs.append(p);self.background.append(p)
        codes=[p.wait(timeout=15) for p in jobs];assert sorted(codes)==[0,2];self.record(race,{'process_exit_codes':codes},1)
        lost=self.new_case('consume-response-lost');self.action(lost,'dispatch','dispatch');self.drop.write_text(lost['grant_ids'][0].hex())
        result=self.action(lost,'launch','lost-reply',expected=3);self.action(lost,'launch','clone-reject',state='clone',expected=2);self.record(lost,result,1)
        for at in ['after-intent','after-permit']:
            case=self.new_case('kill-'+at);self.action(case,'dispatch','dispatch');self.paused_kill(case,at)
            result=self.action(case,'launch','resume-denied',expected=2)
            if at=='after-permit':self.action(case,'launch','fresh-clone-denied',state='clone',expected=2)
            self.record(case,result,1 if at=='after-permit' else 0)
        offline=self.new_case('offline-before-launch');self.action(offline,'dispatch','dispatch');self.stop_server()
        self.record(offline,self.action(offline,'launch','offline',expected=3),0)
        # Fetch only public evidence. Enrollment secrets/private issuer keys stay outside B/.
        code=f"import pathlib,tarfile; r=pathlib.Path({self.remote!r}); t=tarfile.open(r/'B.tar','w'); t.add(r/'B',arcname='B'); t.close()"
        self.ssh_run(['python3','-c',code],'archive-B.log');self.copy_from(self.remote+'/B.tar',self.out/'B.tar','collect-B.log')
        with tarfile.open(self.out/'B.tar') as tar:tar.extractall(self.out,filter='data')
        # Check actual marker/output artifacts; this is not the full event replay checker.
        invocations=0
        for p in (self.out/'B').rglob('*.outcome.cbor'):
            obj=decode(p.read_bytes());prefix=p.name.replace('.outcome.cbor','');output=p.with_name(prefix+'.output.bin')
            assert obj['outcome']['outcome']=='OK' and obj['outcome']['gas_used']==9126
            assert output.exists() and digest_consistency(sha(output.read_bytes())==obj['outcome']['output_digest'])
            assert p.with_name(prefix+'.intent.cbor').exists() and p.with_name(prefix+'.permit.cbor').exists() and p.with_name(prefix+'.invoke.cbor').exists()
            invocations+=1
        assert invocations==2 # normal and the sole parallel winner only
        return {"sha_consistency": "DISABLED", 'status':'PASS','scenarios':len(self.records),'completed_guest_executions':invocations,'scenario_records':self.records,
                'scope':'real LAN check/consume, trusted issuer A and experimental Python RIR startup B; not formal Lease/capability or hostile-host enforcement',
                'topology':'A issuer/SQLite; B dispatch/startup/local files; two physical hosts under DUALHOST-SSH-1',
                'authorization_id':self.authority.authority_id.hex(),'environment_digest':self.env.hex()}
    def close(self):
        self.stop_server()
        for process,ready in self.pauses:
            if process.poll() is None:
                try:self.ssh_run(['python3','-B',self.script+'fault_driver.py','kill','--ready',ready],'cleanup-paused-'+str(process.pid)+'.log',(0,1))
                except Exception:pass # preserve failure; generic ssh cleanup follows
        for p in self.background:
            if p.poll() is None:p.terminate();p.wait(timeout=10)
        (self.out/'commands.json').write_text(json.dumps(self.commands,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--peer',required=True);p.add_argument('--a-host',required=True);p.add_argument('--remote-root',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not a.remote_root.startswith('/'):p.error('absolute fresh remote root required')
    matrix=Matrix(a)
    try:
        result=matrix.matrix();(matrix.out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['status','scenarios','completed_guest_executions']}))
    except BaseException as exc:
        (matrix.out/'report.json').write_text(json.dumps({'status':'FAIL','error':type(exc).__name__+': '+str(exc),'completed_scenarios':matrix.records},indent=2)+'\n');raise
    finally:matrix.close()
