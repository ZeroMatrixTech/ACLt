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
from wire import *
from ledger import Ledger
from audit import reduce
from fixtures import task
from commitment import freeze

spec=importlib.util.spec_from_file_location('settlement_ssh',AUTH/'dualhost.py'); old=importlib.util.module_from_spec(spec); spec.loader.exec_module(old)


class Matrix(old.Matrix):
    def __init__(self,args):
        need(not args.output.resolve().is_relative_to(ROOT),'output outside source')
        super().__init__(args); self.script=self.remote+'/experiments/aclt-fixed-settlement/'
        self.actorA=sha(b'fixed-witness-A'); self.actorB=sha(b'fixed-witness-B')
        self.credentials={ZERO:secrets.token_bytes(32),self.actorA:secrets.token_bytes(32),self.actorB:secrets.token_bytes(32)}
        self.cases=[]
    def prepare(self):
        self.ssh_run(['python3','-c',f"from pathlib import Path; p=Path({self.remote!r}); p.mkdir(parents=True,exist_ok=False); (p/'private').mkdir(mode=0o700); (p/'B').mkdir()"],'mkdir.log')
        files=[]
        for name in ['aclt-fixed-settlement','aclt-task-authorization','aclt-task-commitment','aclt-rir-stats-probe']:
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
        self.ledger=Ledger(self.a/'ledger.sqlite',self.key,self.pub,self.credentials,{ZERO:1000,self.actorA:0,self.actorB:0},self.witnesses)
        self.start_server()
    def start_server(self):
        n=len(list(self.a.glob('ready-*.json'))); ready=self.a/f'ready-{n}.json'
        with (self.a/f'server-{n}.log').open('xb') as log:
            self.server=subprocess.Popen([sys.executable,'-B',HERE/'service.py','--database',self.a/'ledger.sqlite','--private',self.key,'--public',self.pub,'--enrollment',self.enrollment,'--host',self.args.a_host,'--ready',ready],stdout=log,stderr=subprocess.STDOUT)
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
    def matrix(self):
        self.prepare()
        success=self.case('success',1)
        for role in ['A','B']: self.execute(success,role); self.execute(success,role,'submit')
        self.record('same-frozen-task-funded-once-executed-on-two-hosts')
        first=self.action(success,'settle','settle'); body=verify(first['result']['receipt'],self.pub,self.ledger.pin)
        assert (body['paid'],body['refunded'],body['decision'])==(30,70,'MATCH_OK'); self.record('exact-OK-fixed-fee-and-remainder-refund')
        duplicate=self.action(success,'settle','duplicate'); assert duplicate['status']=='DUPLICATE' and duplicate['result']==first['result']; self.record('same-entitlement-original-receipt')
        jobs=[]
        for n in range(2):
            with (self.out/f'concurrent-{n}.log').open('xb') as log:
                p=subprocess.Popen([*self.ssh,old.shlex.join(self.client_args(success,'settle','concurrent-'+str(n)))],stdout=log,stderr=subprocess.STDOUT)
            self.background.append(p); jobs.append(p)
        assert [p.wait(timeout=20) for p in jobs]==[0,0]; self.record('concurrent-retransmissions-no-extra-payment')
        self.execute(success,'B','submit','saved-outcome-resubmit'); self.record('saved-outcome-retransmission-no-reexecution')
        assert self.action(success,'settle','wrong-payer','B')['status']=='DENIED'; self.record('nonpayer-cannot-settle')
        refund=self.case('closed-no-pay',2,gas=8192)
        for role in ['A','B']: self.execute(refund,role); self.execute(refund,role,'submit')
        r=self.action(refund,'settle','settle'); b=verify(r['result']['receipt'],self.pub,self.ledger.pin)
        assert (b['paid'],b['refunded'],b['decision'])==(0,100,'CLOSED_NO_PAY'); self.record('two-complete-gas-traps-full-refund')
        assert self.action(refund,'settle','duplicate')['result']==r['result']; self.record('refund-idempotence')
        pending=self.case('pending-one-side',3); self.execute(pending,'B'); self.execute(pending,'B','submit')
        assert self.action(pending,'settle','pending')['status']=='PENDING'; self.record('missing-side-holds-full-reservation')
        unfunded=self.case('unfunded',4,reserve=False); self.execute(unfunded,'B',label='unfunded-denied',expected=1); self.record('unreserved-start-no-guest')
        self.execute(pending,'B',label='wrong-task',state='wrong-task-state',taskid=ZERO.hex(),expected=1); self.record('wrong-task-rejected-before-invocation')
        self.stop_server(); self.start_server()
        assert self.action(success,'status','restart-status')['result']==first['result']; assert self.action(success,'settle','restart-duplicate')['result']==first['result']; self.record('restart-query-original-settlement')
        self.stop_server(); bundle,anchor=self.ledger.export(); reduced=reduce(bundle,anchor,self.pub,self.ledger.pin,sha(anchor))
        assert (reduced['reserved'],reduced['paid'],reduced['refunded'],reduced['settlements'],reduced['starts'],reduced['outcomes'])==(100,30,170,2,5,5)
        assert reduced['projection']['accounts'][ZERO.hex()]['available']==870 and reduced['projection']['accounts'][self.actorB.hex()]['available']==30
        (self.out/'ledger-export.json').write_text(json.dumps(bundle,indent=2)+'\n'); (self.out/'checkpoint.cbor').write_bytes(anchor); (self.a/'issuer.pub').write_bytes(regular(self.pub)); (self.out/'reduced.json').write_text(json.dumps(reduced,indent=2)+'\n')
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
        # Validate retained local invocation markers and submitted raw outcomes.
        invoked=list(self.a.rglob('invoke.cbor'))+list((self.out/'B').rglob('invoke.cbor'))
        assert len(invoked)==5
        for case in [success,refund]:
            left=decode(regular(case['local']/'state/outcome.cbor')); right=decode(regular(self.out/'B'/case['name']/'state/outcome.cbor'))
            assert encode(left['result'])==encode(right['result'])
        events={event_id(bytes.fromhex(raw)):decode(bytes.fromhex(raw)) for raw in bundle['events']}; responses=0
        for path in (self.out/'B').rglob('*.json'):
            obj=json.loads(path.read_text())
            if 'signed_response' not in obj: continue
            req=bytes.fromhex(obj['request']); raw=bytes.fromhex(obj['signed_response']); parsed=response(req,raw,{'authority_id':self.ledger.authority,'public_digest':self.ledger.pin},self.pub)
            assert events[parsed['event_ref']]['data']=={'request':req,'status':parsed['status'],'result':parsed['result']}; responses+=1
        return {'status':'PASS','scenarios':len(self.records),'records':self.records,'negative_controls':controls,'public_digest':self.ledger.pin.hex(),'anchor_digest':sha(anchor).hex(),'invocation_markers':len(invoked),'signed_B_client_responses':responses,'reduced':reduced,'scope':'fixed internal test settlement from two authenticated pinned reference outcomes; not TRUSTED or formal settlement','topology':'A trusted ledger/service and role-A reference worker; B requester and role-B reference worker, separate HMAC role enrollment'}


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
