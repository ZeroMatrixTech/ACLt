# SPDX-License-Identifier: Apache-2.0
"""Real two-host same-task outcomes and fixed internal test-asset settlement."""

if not __debug__:
    raise SystemExit('assert-based validation requires Python without -O/PYTHONOPTIMIZE')

import argparse
import copy
import importlib.util
import subprocess
import tarfile
import time
from context import *
from recovery import RecoveryLedger
from audit import reduce
from fixtures import task
from commitment import freeze

spec=importlib.util.spec_from_file_location('settlement_ssh',AUTH/'dualhost.py'); old=importlib.util.module_from_spec(spec); spec.loader.exec_module(old)


class Matrix(old.Matrix):
    def __init__(self,args):
        need(not args.output.resolve().is_relative_to(ROOT),'output outside source')
        super().__init__(args); self.script=self.remote+'/experiments/aclt-settlement-recovery/'; self.checkpoints=[]; self.worker_gates=[]
        self.actorA=sha(b'fixed-witness-A'); self.actorB=sha(b'fixed-witness-B')
        self.credentials={ZERO:secrets.token_bytes(32),self.actorA:secrets.token_bytes(32),self.actorB:secrets.token_bytes(32)}
        self.cases=[]
    def prepare(self):
        self.ssh_run(['python3','-c',f"from pathlib import Path; p=Path({self.remote!r}); p.mkdir(parents=True,exist_ok=False); (p/'private').mkdir(mode=0o700); (p/'B').mkdir()"],'mkdir.log')
        files=[]
        for name in ['aclt-settlement-recovery','aclt-fixed-settlement','aclt-task-authorization','aclt-task-commitment','aclt-rir-stats-probe']:
            files += [p for p in (ROOT/'experiments'/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
        lock={p.relative_to(ROOT).as_posix():sha(regular(p)).hex() for p in sorted(files)}
        (self.out/'source-lock.json').write_text(json.dumps(lock,indent=2)+'\n')
        with tarfile.open(self.out/'source.tar','w') as tar:
            for p in files: tar.add(p,arcname=p.relative_to(ROOT),recursive=False)
            tar.add(self.out/'source-lock.json',arcname='source-lock.json')
        self.copy_to(self.out/'source.tar',self.remote+'/source.tar','source-copy.log')
        code=f"import pathlib,tarfile,json,hashlib; r=pathlib.Path({self.remote!r}); tarfile.open(r/'source.tar').extractall(r,filter='data'); d=json.loads((r/'source-lock.json').read_text()); assert all(hashlib.sha256((r/n).read_bytes()).hexdigest()==h for n,h in d.items()); print('SOURCE_LOCK_OK',len(d))"
        self.ssh_run(['python3','-c',code],'source-check.log')
        self.ssh_run(['python3','-B','-W','error::ResourceWarning','-m','unittest','discover','-s',self.script+'tests','-v'],'remote-unit.log')
        benv=self.ssh_run(['python3','-B',self.script+'executor.py','environment'],'environment-B-digest.log')
        self.witnesses={'A':{'actor':self.actorA,'environment':environment()},'B':{'actor':self.actorB,'environment':bytes.fromhex(benv.stdout.decode().strip())}}
        check_witnesses(self.witnesses)
        env="import json,platform,sqlite3,ssl; print(json.dumps({'hostname':platform.node(),'python':platform.python_version(),'kernel':platform.release(),'sqlite':sqlite3.sqlite_version,'openssl':ssl.OPENSSL_VERSION}))"
        self.run([sys.executable,'-c',env],'environment-A.log'); self.ssh_run(['python3','-c',env],'environment-B.log')
        self.key,self.pub=create_keys(self.private/'keys'); self.copy_to(self.pub,self.pub_path,'public-copy.log')
        self.enrollment=self.private/'enrollment.json'; self.enrollment.write_text(json.dumps({k.hex():v.hex() for k,v in self.credentials.items()})); self.enrollment.chmod(0o600)
        self.ledger=RecoveryLedger(self.a/'ledger.sqlite',self.key,self.pub,self.credentials,{ZERO:1000,self.actorA:0,self.actorB:0},self.witnesses)
        self.control=self.private/'fault-control.json'; self.control.write_text('{}')
        self.start_server()
    def start_server(self):
        n=len(list(self.a.glob('ready-*.json'))); ready=self.a/f'ready-{n}.json'
        with (self.a/f'server-{n}.log').open('xb') as log:
            self.server=subprocess.Popen([sys.executable,'-B',HERE/'service.py','--database',self.a/'ledger.sqlite','--private',self.key,'--public',self.pub,'--enrollment',self.enrollment,'--host',self.args.a_host,'--ready',ready,'--test-control',self.control],stdout=log,stderr=subprocess.STDOUT)
        for _ in range(100):
            if ready.exists(): break
            if self.server.poll() is not None: raise RuntimeError('settlement service exited')
            time.sleep(.05)
        else: raise RuntimeError('settlement readiness timeout')
        port=json.loads(ready.read_text())['port']
        for role,actor in [('PAYER',ZERO),('A',self.actorA),('B',self.actorB)]:
            cfg={'host':self.args.a_host,'port':port,'authority_id':self.ledger.authority.hex(),'requester':actor.hex(),'secret':self.credentials[actor].hex(),'public_digest':self.ledger.pin.hex(),'role':role,'environment':(self.witnesses[role]['environment'] if role!='PAYER' else ZERO).hex()}
            path=self.private/(role+'.json'); path.write_text(json.dumps(cfg)); path.chmod(0o600)
            if role!='A': self.copy_to(path,self.remote+'/private/'+role+'.json',f'config-{role}-{n}.log')
    def case(self,name,nonce,gas=50000000,reserve=True):
        local=self.a/name; local.mkdir(); remote=self.remote+'/B/'+name
        self.ssh_run(['python3','-c',f"from pathlib import Path; Path({remote!r}).mkdir()"],name+'-mkdir.log')
        c,tid,art,inp=task(bytes([nonce])*16)
        if gas!=50000000:
            limits={**load(c)['execution_limits'],'gas_limit':gas}; c,tid=freeze(art,[inp],ZERO,bytes([nonce])*16,limits)
        p=policy(c,self.actorB,100,30); binding=encode({'policy':p,'commitment':c,'artifact':art,'input':inp})
        for filename,data in [('policy.cbor',p),('task.cbor',c),('artifact.cbor',art),('input.bin',inp),('binding.cbor',binding)]:
            (local/filename).write_bytes(data); self.copy_to(local/filename,remote+'/'+filename,name+'-copy-'+filename+'.log')
        case={'name':name,'local':local,'remote':remote,'pid':policy_id(p),'task':tid}; self.cases.append(case)
        assert self.action(case,'freeze','freeze')['status']=='FROZEN'
        if reserve: assert self.action(case,'reserve','reserve')['status']=='RESERVED'
        return case
    def client_args(self,case,op,label,role='PAYER'):
        args=['python3','-B',self.script+'client.py',op,'--config',self.remote+'/private/'+role+'.json','--public',self.pub_path,'--report',case['remote']+'/'+label+'.json']
        if op=='freeze':
            for k,n in [('policy','policy.cbor'),('commitment','task.cbor'),('artifact','artifact.cbor'),('input','input.bin')]: args+=['--'+k,case['remote']+'/'+n]
        elif op!='balance': args+=['--policy-id',case['pid'].hex()]
        return args
    def action(self,case,op,label,role='PAYER'):
        self.ssh_run(self.client_args(case,op,label,role),case['name']+'-'+label+'.log')
        path=self.out/(case['name']+'-'+label+'-reply.json'); self.copy_from(case['remote']+'/'+label+'.json',path,case['name']+'-'+label+'-copy.log')
        obj=json.loads(path.read_text())
        return response(bytes.fromhex(obj['request']),bytes.fromhex(obj['signed_response']),{'authority_id':self.ledger.authority,'public_digest':self.ledger.pin},self.pub)
    def execute(self,case,role,mode='execute',label=None,expected=0,state='state',taskid=None):
        label=label or role+'-'+mode; root=case['local'] if role=='A' else case['remote']
        if role=='A':
            args=[sys.executable,'-B',HERE/'executor.py',mode,'--config',self.private/'A.json','--public',self.pub,'--state',case['local']/state,'--report',case['local']/(label+'.json')]
        else:
            args=['python3','-B',self.script+'executor.py',mode,'--config',self.remote+'/private/B.json','--public',self.pub_path,'--state',case['remote']+'/'+state,'--report',case['remote']+'/'+label+'.json']
        if mode=='execute': args+=['--binding',str(root)+'/binding.cbor','--task-id',taskid or case['task']]
        else: args+=['--policy-id',case['pid'].hex()]
        if role=='A': self.run(args,case['name']+'-'+label+'.log',(expected,))
        else: self.ssh_run(args,case['name']+'-'+label+'.log',(expected,))
    def record(self,name): self.records.append({'scenario':name,'status':'PASS'})
    def checkpoint(self,label):
        bundle,anchor=self.ledger.export(); result=reduce(bundle,anchor,self.pub,self.ledger.pin,sha(anchor))
        (self.out/(label+'-export.json')).write_text(json.dumps(bundle,indent=2)+'\n')
        (self.out/(label+'-anchor.cbor')).write_bytes(anchor); (self.out/(label+'-reduced.json')).write_text(json.dumps(result,indent=2)+'\n')
        self.checkpoints.append({'label':label,'anchor_digest':sha(anchor).hex(),'settlements':result['settlements'],'paid':result['paid'],'refunded':result['refunded'],'reserved':result['reserved']})
        return result,bundle,anchor
    def complete(self,case):
        for role in ['A','B']: self.execute(case,role); self.execute(case,role,'submit')
    def arm(self,case,label,point,mode):
        ready=self.a/(label+'-ready.json'); control={'point':point,'mode':mode,'op':'SETTLE','policy_id':case['pid'].hex(),'ready':str(ready),'token':secrets.token_hex(16)}
        temp=self.private/'next-control.json'; temp.write_text(json.dumps(control)); temp.replace(self.control)
        return ready,control['token']
    def disarm(self):
        temp=self.private/'next-control.json'; temp.write_text('{}'); temp.replace(self.control)
    def wait_local(self,path):
        for _ in range(150):
            if path.exists(): return json.loads(path.read_text())
            if self.server.poll() is not None: raise RuntimeError('server exited before gate')
            time.sleep(.05)
        raise RuntimeError('fault gate timeout')
    def begin_settle(self,case,label):
        with (self.out/(label+'.log')).open('xb') as log:
            process=subprocess.Popen([*self.ssh,old.shlex.join(self.client_args(case,'settle',label))],stdout=log,stderr=subprocess.STDOUT)
        self.background.append(process); return process
    def finish_failed(self,process,label):
        code=process.wait(timeout=20); assert code==1,(label,code)
        self.commands.append({'label':label,'expected_client_exit':code})
    def kill_owned_server(self,observed,token):
        assert observed['pid']==self.server.pid and observed['token']==token
        pid=self.server.pid; self.server.kill(); code=self.server.wait(timeout=10); self.server=None
        assert code==-9; self.commands.append({'owned_service_pid':pid,'exit_code':code,'gate':observed['point']})
    def wait_remote(self,path,label):
        for n in range(60):
            p=self.ssh_run(['python3','-c',f"from pathlib import Path; raise SystemExit(0 if Path({path!r}).exists() else 1)"],f'{label}-ready-{n}.log',(0,1))
            if p.returncode==0: return
            time.sleep(.05)
        raise RuntimeError('remote gate timeout')
    def pause_worker(self,case,point):
        r=case['remote']; ready=r+'/'+point+'-ready.json'
        argv=['python3','-B',self.script+'fault_driver.py','pause-execute','--config',self.remote+'/private/B.json','--public',self.pub_path,'--state',r+'/state','--binding',r+'/binding.cbor','--task-id',case['task'],'--ready',ready,'--point',point]
        with (self.out/(case['name']+'-paused.log')).open('xb') as log: process=subprocess.Popen([*self.ssh,old.shlex.join(argv)],stdout=log,stderr=subprocess.STDOUT)
        self.background.append(process); self.worker_gates.append((process,ready)); self.wait_remote(ready,case['name'])
        self.ssh_run(['python3','-B',self.script+'fault_driver.py','kill','--ready',ready],case['name']+'-kill.log')
        code=process.wait(timeout=10); assert code!=0; self.commands.append({'worker_case':case['name'],'gate':point,'exit_code':code})
    def race(self,case):
        jobs=[]; release=case['remote']+'/release-race'
        for n in range(2):
            ready=case['remote']+f'/race-ready-{n}.json'
            argv=['python3','-B',self.script+'fault_driver.py','race-settle','--config',self.remote+'/private/PAYER.json','--public',self.pub_path,'--policy-id',case['pid'].hex(),'--report',case['remote']+f'/race-{n}.json','--ready',ready,'--release',release]
            with (self.out/f'first-race-{n}.log').open('xb') as log: process=subprocess.Popen([*self.ssh,old.shlex.join(argv)],stdout=log,stderr=subprocess.STDOUT)
            self.background.append(process); self.worker_gates.append((process,ready)); jobs.append(process)
        for n in range(2): self.wait_remote(case['remote']+f'/race-ready-{n}.json',f'race-{n}')
        before,_,_=self.checkpoint('race-before-release'); assert case['pid'].hex() not in before['projection']['settlements']
        self.ssh_run(['python3','-c',f"from pathlib import Path; Path({release!r}).write_bytes(b'release')"],'release-race.log')
        assert [p.wait(timeout=20) for p in jobs]==[0,0]
        results=[]
        for n in range(2):
            path=self.out/f'first-race-{n}-response.json'; self.copy_from(case['remote']+f'/race-{n}.json',path,f'race-{n}-copy.log'); obj=json.loads(path.read_text())
            results.append(response(bytes.fromhex(obj['request']),bytes.fromhex(obj['signed_response']),{'authority_id':self.ledger.authority,'public_digest':self.ledger.pin},self.pub))
        assert sorted(r['status'] for r in results)==['DUPLICATE','SETTLED'] and results[0]['result']==results[1]['result']
    def matrix(self):
        self.prepare()
        for index,(name,gas,paid,refund) in enumerate([('lost-pay',50000000,30,70),('lost-refund',8192,0,100)],1):
            case=self.case(name,index,gas=gas); self.complete(case); ready,token=self.arm(case,name,'after_commit','drop')
            self.ssh_run(self.client_args(case,'settle',name),name+'-failed-client.log',(1,)); observed=self.wait_local(ready); assert observed['token']==token
            self.disarm(); state,_,_=self.checkpoint(name+'-without-reply'); assert case['pid'].hex() in state['projection']['settlements']
            self.record(name+'-committed-without-TCP-reply')
            recovered=self.action(case,'recover','recover'); raw=recovered['result']['receipt']; body=verify(raw,self.pub,self.ledger.pin)
            assert recovered['status']=='SETTLED' and sha(raw).hex()==observed['receipt_digest'] and (body['paid'],body['refunded'])==(paid,refund)
            assert self.action(case,'settle','duplicate')['result']==recovered['result']; self.record(name+'-query-original-no-repeat-allocation')
        before=self.case('kill-before-commit',3); self.complete(before); _,prior,prior_anchor=self.checkpoint('before-commit-baseline')
        ready,token=self.arm(before,'kill-before','before_commit','pause'); process=self.begin_settle(before,'killed-before')
        observed=self.wait_local(ready); self.kill_owned_server(observed,token); self.finish_failed(process,'killed-before'); self.disarm()
        state,rolled,anchor=self.checkpoint('before-commit-rolled-back')
        assert rolled==prior and anchor==prior_anchor and observed['event_ref'] not in {event_id(bytes.fromhex(x)).hex() for x in rolled['events']}
        self.record('SIGKILL-before-COMMIT-rolls-back-money-entitlement-event')
        self.start_server(); held=self.action(before,'recover','recover-held'); assert held['status']=='RESERVED'
        assert self.action(before,'settle','explicit-settle')['status']=='SETTLED'; self.record('query-unsettled-then-explicit-one-settlement')
        after=self.case('kill-after-commit',4); self.complete(after); ready,token=self.arm(after,'kill-after','after_commit','pause')
        process=self.begin_settle(after,'killed-after'); observed=self.wait_local(ready); self.kill_owned_server(observed,token); self.finish_failed(process,'killed-after'); self.disarm()
        _,committed,_=self.checkpoint('after-commit-before-recovery'); assert observed['event_ref'] in {event_id(bytes.fromhex(x)).hex() for x in committed['events']}
        self.record('SIGKILL-after-COMMIT-retains-original-allocation')
        self.start_server(); recovered=self.action(after,'recover','recover-original'); assert recovered['status']=='SETTLED' and sha(recovered['result']['receipt']).hex()==observed['receipt_digest']
        assert self.action(after,'settle','duplicate')['result']==recovered['result']; self.record('restart-query-original-receipt-after-committed-kill')
        race=self.case('first-race',5); self.complete(race); self.race(race); self.record('two-barrier-released-B-clients-first-settlement-one-entitlement')
        saved=self.case('saved-outcome',6); self.execute(saved,'A'); self.execute(saved,'A','submit'); self.pause_worker(saved,'after_outcome')
        assert self.action(saved,'settle','pending')['status']=='PENDING'; self.checkpoint('saved-outcome-not-submitted'); self.record('worker-SIGKILL-after-fsync-outcome-still-pending')
        self.execute(saved,'B',label='clone-denied',state='clone',expected=1)
        self.execute(saved,'B','submit','saved-submit'); assert self.action(saved,'settle','settle')['status']=='SETTLED'; self.record('saved-outcome-retransmit-without-new-invocation')
        incomplete=self.case('permit-only',7); self.execute(incomplete,'A'); self.execute(incomplete,'A','submit'); self.pause_worker(incomplete,'after_permit')
        self.execute(incomplete,'B','submit','incomplete-submit-denied',expected=1); self.execute(incomplete,'B',label='clone-denied',state='clone',expected=1)
        assert self.action(incomplete,'settle','pending')['status']=='PENDING'; state,_,_=self.checkpoint('permit-only-held'); assert incomplete['pid'].hex() not in state['projection']['settlements']
        self.record('worker-SIGKILL-after-permit-no-recompute-no-refund')
        self.stop_server(); self.ssh_run(self.client_args(incomplete,'recover','offline-recovery'),'offline-recovery.log',(1,)); self.record('unavailable-authority-no-guessed-payment-refund')
        self.start_server(); assert self.action(incomplete,'recover','recover-held')['status']=='RESERVED'; self.record('incomplete-evidence-retains-full-reservation-after-restart')
        self.stop_server(); final,bundle,anchor=self.checkpoint('final')
        assert (final['initial_total'],final['reserved'],final['paid'],final['refunded'],final['settlements'],final['starts'],final['outcomes'])==(1000,100,150,450,6,14,13)
        assert final['projection']['accounts'][ZERO.hex()]['available']==750 and final['projection']['accounts'][self.actorB.hex()]['available']==150
        controls=[]
        for name in ['truncate','projection','event-bytes','wrong-key','wrong-anchor','comparison']:
            bad=copy.deepcopy(bundle); pin=self.ledger.pin; ad=sha(anchor)
            if name=='truncate': bad['events'].pop()
            elif name=='projection': bad['projection']['accounts'][ZERO.hex()]['available']+=1
            elif name=='event-bytes':
                e=decode(bytes.fromhex(bad['events'][1])); e['prev']=bytes([1])*32; bad['events'][1]=encode(e).hex()
            elif name=='comparison':
                key=next(iter(bad['projection']['settlements'])); bad['projection']['settlements'][key]['comparison']='00'
            elif name=='wrong-key': pin=ZERO
            else: ad=ZERO
            try: reduce(bad,anchor,self.pub,pin,ad)
            except Rejected as exc: controls.append({'control':name,'status':'REJECTED','reason':str(exc)})
            else: raise AssertionError('tamper accepted '+name)
        code=f"import tarfile; t=tarfile.open({(self.remote+'/B.tar')!r},'w'); t.add({(self.remote+'/B')!r},arcname='B'); t.close()"
        self.ssh_run(['python3','-c',code],'archive-B.log'); self.copy_from(self.remote+'/B.tar',self.out/'B.tar','collect-B.log')
        with tarfile.open(self.out/'B.tar') as tar: tar.extractall(self.out,filter='data')
        (self.a/'issuer.pub').write_bytes(regular(self.pub))
        invocations=list(self.a.rglob('invoke.cbor'))+list((self.out/'B').rglob('invoke.cbor')); assert len(invocations)==13
        for case in self.cases:
            bstate=self.out/'B'/case['name']/'state'
            if case['name']=='permit-only': assert not (bstate/'outcome.cbor').exists() and not (bstate/'invoke.cbor').exists()
            else:
                left=decode(regular(case['local']/'state/outcome.cbor')); right=decode(regular(bstate/'outcome.cbor')); assert encode(left['result'])==encode(right['result'])
        for name,label in [('lost-pay','lost-pay'),('lost-refund','lost-refund'),('kill-before-commit','killed-before'),('kill-after-commit','killed-after')]:
            assert not (self.out/'B'/name/(label+'.json')).exists()
        events={event_id(bytes.fromhex(x)):decode(bytes.fromhex(x)) for x in bundle['events']}; responses=0; recover_queries=0
        for path in (self.out/'B').rglob('*.json'):
            obj=json.loads(path.read_text())
            if 'signed_response' not in obj: continue
            req=bytes.fromhex(obj['request']); raw=bytes.fromhex(obj['signed_response']); parsed=response(req,raw,{'authority_id':self.ledger.authority,'public_digest':self.ledger.pin},self.pub)
            assert events[parsed['event_ref']]['data']=={'request':req,'status':parsed['status'],'result':parsed['result']}; responses+=1
            if 'recovery_status' in obj:
                assert decode(decode(req)['payload'])['op']=='STATUS'; recover_queries+=1
        return {'status':'PASS','scenarios':len(self.records),'records':self.records,'negative_controls':controls,'checkpoints':self.checkpoints,'public_digest':self.ledger.pin.hex(),'invocation_markers':len(invocations),'signed_B_client_responses':responses,'read_only_recovery_queries':recover_queries,'reduced':final,'scope':'v2 test settlement recovery under actual TCP reply loss and owned process SIGKILL; no physical power-cut or external-payment guarantee','topology':'A trusted ledger/service + A worker; B requester + B worker, separate role credentials and persistent directories'}
    def close(self):
        for process,ready in self.worker_gates:
            if process.poll() is None:
                try: self.ssh_run(['python3','-B',self.script+'fault_driver.py','kill','--ready',ready],'cleanup-worker-'+str(process.pid)+'.log',(0,1))
                except Exception: pass
        super().close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['peer','a-host','remote-root']: p.add_argument('--'+n,required=True)
    p.add_argument('--output',type=Path,required=True); a=p.parse_args(); need(a.remote_root.startswith('/') and a.remote_root.rstrip('/')!='/' and '..' not in Path(a.remote_root).parts,'absolute fresh remote root')
    m=Matrix(a)
    try:
        result=m.matrix(); (m.out/'report.json').write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps({'status':'PASS','scenarios':result['scenarios'],'paid':result['reduced']['paid'],'refunded':result['reduced']['refunded']}))
    except BaseException as exc:
        (m.out/'report.json').write_text(json.dumps({'status':'FAIL','error':type(exc).__name__+': '+str(exc),'completed_scenarios':m.records},indent=2)+'\n'); raise
    finally: m.close()
