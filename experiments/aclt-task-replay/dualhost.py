# SPDX-License-Identifier: Apache-2.0
"""Opt-in real LAN causal submission/replay matrix, with independent checkpoint reduction."""
import argparse,importlib.util,json,os,secrets,shlex,subprocess,sys,tarfile,time
from context import *
from ledger import Ledger
from offline import reduce
from worker import export_worker
from fixtures import task

spec=importlib.util.spec_from_file_location('authorization_matrix',AUTH/'dualhost.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)

class Matrix(old.Matrix):
    def __init__(self,args):
        need(not args.output.resolve().is_relative_to(HERE),'output must be outside source')
        super().__init__(args);self.script=self.remote+'/experiments/aclt-task-replay/';self.cases=[];self.checkpoints=[]
    def prepare(self):
        self.ssh_run(['python3','-c',f"from pathlib import Path; p=Path({self.remote!r}); p.mkdir(parents=True,exist_ok=False); (p/'private').mkdir(mode=0o700); (p/'B').mkdir()"],'mkdir-remote.log')
        files=[]
        for name in ['aclt-task-replay','aclt-task-authorization','aclt-task-commitment','aclt-rir-stats-probe']:
            files.extend(p for p in (ROOT/'experiments'/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
        lock={p.relative_to(ROOT).as_posix():sha(regular(p)).hex() for p in sorted(files)};(self.out/'source-lock.json').write_text(json.dumps(lock,indent=2)+'\n')
        with tarfile.open(self.out/'source.tar','w') as tar:
            for p in files:tar.add(p,arcname=p.relative_to(ROOT),recursive=False)
            tar.add(self.out/'source-lock.json',arcname='source-lock.json')
        self.copy_to(self.out/'source.tar',self.remote+'/source.tar','copy-source.log')
        code=f"import pathlib,tarfile,json,hashlib; r=pathlib.Path({self.remote!r}); tarfile.open(r/'source.tar').extractall(r,filter='data'); d=json.loads((r/'source-lock.json').read_text()); assert all(hashlib.sha256((r/n).read_bytes()).hexdigest()==s for n,s in d.items()); print('SOURCE_LOCK_OK',len(d))"
        self.ssh_run(['python3','-c',code],'remote-source-check.log')
        self.ssh_run(['python3','-B','-W','error::ResourceWarning','-m','unittest','discover','-s',self.script+'tests','-v'],'remote-unit.log')
        p=self.ssh_run(['python3','-B',self.script+'fault_driver.py','environment','--report',self.remote+'/private/environment.cbor'],'remote-environment.log');self.env=bytes.fromhex(p.stdout.decode().strip())
        self.key,self.pub=create_keys(self.private/'keys');self.copy_to(self.pub,self.pub_path,'copy-public.log')
        path=self.private/'providers.json';path.write_text(json.dumps({self.provider.hex():self.secret.hex()}));path.chmod(0o600)
        self.authority=Ledger(self.a/'ledger.sqlite',self.key,self.pub,{self.provider:self.secret},initialize=True);self.drop=self.a/'drop.txt';self.drop.write_text('');self.start_server()
    def start_server(self):
        index=len(list(self.a.glob('service-ready-*.json')));ready=self.a/f'service-ready-{index}.json';log=(self.a/f'service-{index}.log').open('wb')
        argv=[sys.executable,'-B',str(HERE/'service.py'),'--database',str(self.a/'ledger.sqlite'),'--private',str(self.key),'--public',str(self.pub),'--providers',str(self.private/'providers.json'),'--host',self.args.a_host,'--ready',str(ready),'--test-drop-file',str(self.drop)]
        self.server=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT);log.close()
        for _ in range(100):
            if ready.exists():break
            if self.server.poll() is not None:raise RuntimeError('server failed')
            time.sleep(0.05)
        else:raise RuntimeError('readiness timeout')
        self.port=json.loads(ready.read_text())['port'];cfg={'host':self.args.a_host,'port':self.port,'authority_id':self.authority.authority_id.hex(),'public_digest':self.authority.public_digest.hex(),'provider_ref':self.provider.hex(),'unit_ref':self.unit.hex(),'environment_digest':self.env.hex(),'provider_secret':self.secret.hex()}
        path=self.private/'worker.json';path.write_text(json.dumps(cfg));path.chmod(0o600);self.copy_to(path,self.cfg_path,'copy-config-'+str(index)+'.log')
    def new_case(self,name):
        local=self.a/name;local.mkdir();remote=self.remote+'/B/'+name;self.ssh_run(['python3','-c',f"from pathlib import Path; Path({remote!r}).mkdir()"],name+'-mkdir.log')
        c,identity,artifact,data=task(sha(('replay-slice3:'+name).encode())[:16]);self.authority.register(c,artifact,data);now=int(time.time())
        delivery=self.authority.issue(c,self.provider,self.unit,self.env,1,now-30,now+600);body=verify(decode(delivery)['grant'],self.pub,self.authority.public_digest)
        for name2,b in [('task.cbor',c),('artifact.cbor',artifact),('input.bin',data),('delivery.cbor',delivery)]:
            path=local/name2;path.write_bytes(b);self.copy_to(path,remote+'/'+name2,name+'-copy-'+name2+'.log')
        case={'name':name,'local':local,'remote':remote,'identity':identity,'gid':grant_id(body),'stream':stream_id('worker',self.authority.authority_id,body['experimental_task_id'],body['unit_ref'])};self.cases.append(case);return case
    def argv(self,case,stage,state='state',config=None):
        r=case['remote'];args=['python3','-B',self.script+'worker.py',stage,'--config',config or self.cfg_path,'--public',self.pub_path,'--state',r+'/'+state,'--task-id',case['identity']]
        if stage!='replay':args+=['--commitment',r+'/task.cbor','--artifact',r+'/artifact.cbor','--input',r+'/input.bin']
        if stage=='dispatch':args+=['--delivery',r+'/delivery.cbor']
        return args
    def record_case(self,case,label,result):self.records.append({'scenario':label,'status':'PASS','experimental_task_id':case['identity'],'grant_id':case['gid'].hex(),'result':result})
    def checkpoint(self,label):
        remote=self.remote+'/private/workers-'+label+'.cbor';self.ssh_run(['python3','-B',self.script+'fault_driver.py','export','--root',self.remote+'/B','--report',remote],label+'-worker-export.log')
        path=self.out/(label+'-workers.cbor');self.copy_from(remote,path,label+'-collect.log');workers=decode(regular(path))['workers'];authority,anchor=self.authority.export();bundle={'authority':authority,'workers':workers}
        durable_new(self.out/(label+'-bundle.cbor'),encode(bundle));durable_new(self.out/(label+'-anchor.cbor'),anchor)
        result=reduce(bundle,anchor,self.pub,self.authority.public_digest,sha(anchor));(self.out/(label+'-reduced.json')).write_text(json.dumps(result,indent=2)+'\n')
        self.checkpoints.append({'label':label,'anchor_digest':sha(anchor).hex(),'accepted':result['accepted'],'consumed':result['consumed']});return result,bundle,anchor
    def variant(self,case,label):
        p=self.ssh_run(['python3','-B',self.script+'fault_driver.py','variant','--config',self.cfg_path,'--public',self.pub_path,'--state',case['remote']+'/state','--report',case['remote']+'/'+label+'.json'],case['name']+'-'+label+'.log');return json.loads(p.stdout)
    def matrix(self):
        self.prepare()
        normal=self.new_case('normal');self.action(normal,'dispatch','dispatch');result=self.action(normal,'launch','launch');assert result['status']=='ACCEPTED';self.record_case(normal,'normal-complete-chain',result)
        duplicate=self.action(normal,'replay','duplicate');assert duplicate['status']=='DUPLICATE' and duplicate['receipt_digest']==result['receipt_digest'];self.record_case(normal,'identical-packet-replay',duplicate)
        jobs=[]
        for i in range(2):
            argv=self.argv(normal,'replay')+['--report',normal['remote']+'/parallel-'+str(i)+'.json'];f=(self.out/('parallel-'+str(i)+'.log')).open('wb');p=subprocess.Popen([*self.ssh,shlex.join(argv)],stdout=f,stderr=subprocess.STDOUT);f.close();jobs.append(p);self.background.append(p)
        assert [p.wait(timeout=20) for p in jobs]==[0,0];self.record_case(normal,'concurrent-identical-retransmissions',{'status':'TWO_DUPLICATES'})
        self.stop_server();self.start_server();again=self.action(normal,'replay','restart-replay');assert again['receipt_digest']==result['receipt_digest'];self.record_case(normal,'authority-restart-stable-receipt',again)
        conflict=self.variant(normal,'conflict');assert conflict['status']=='CONFLICT';self.record_case(normal,'conflicting-packet-preserves-original',conflict)
        lost=self.new_case('lost-accept-reply');self.action(lost,'dispatch','dispatch');self.drop.write_text('SUBMIT '+lost['gid'].hex());failure=self.action(lost,'launch','lost-reply',expected=3)
        state,_,_=self.checkpoint('pending-ack');w=next(w for w in state['workers'] if w['stream']==lost['stream'].hex());assert w['accepted'] and not w['acknowledged'];self.record_case(lost,'accepted-without-worker-ack',failure)
        replayed=self.action(lost,'replay','recover-receipt');assert replayed['status']=='DUPLICATE';self.record_case(lost,'lost-reply-recovers-same-receipt',replayed)
        prepared=self.new_case('killed-after-prepared');self.action(prepared,'dispatch','dispatch');self.paused_kill(prepared,'after-prepared');self.stop_server();offline=self.action(prepared,'replay','offline',expected=3);self.record_case(prepared,'offline-replay-does-not-recompute',offline)
        self.start_server();recovered=self.action(prepared,'replay','recovered');assert recovered['status']=='ACCEPTED';self.record_case(prepared,'prepared-process-kill-retransmits-complete-packet',recovered)
        for stage in ['after-intent','after-outcome']:
            case=self.new_case('killed-'+stage);self.action(case,'dispatch','dispatch');self.paused_kill(case,stage)
            result=self.action(case,'replay','incomplete-replay',expected=3);self.action(case,'launch','no-relaunch',expected=2);self.record_case(case,'incomplete-'+stage+'-never-recomputed',result)
        corrupt=self.new_case('corrupt-first-copy');self.action(corrupt,'dispatch','dispatch');self.paused_kill(corrupt,'after-prepared');bad=self.variant(corrupt,'corrupt-copy');assert bad['status']=='REJECTED';good=self.action(corrupt,'replay','original-packet');assert good['status']=='ACCEPTED';self.record_case(corrupt,'corrupt-copy-rejected-original-replayed',good)
        final,bundle,anchor=self.checkpoint('final');assert final['accepted']==4 and final['consumed']==5
        # Tamper controls change only in-memory copies, leaving retained originals intact.
        import copy
        controls=[]
        for name in ['truncate-authority','drop-worker','alter-object','projection','fork-worker','wrong-anchor','wrong-public-pin']:
            bad=copy.deepcopy(bundle);pin=self.authority.public_digest;ad=sha(anchor)
            if name=='truncate-authority':bad['authority']['events'].pop()
            elif name=='drop-worker':bad['workers'].pop(0)
            elif name=='alter-object':key=next(iter(bad['workers'][0]['journal']['objects']));bad['workers'][0]['journal']['objects'][key]+=b'x'
            elif name=='projection':bad['authority']['projection']['tasks']=[]
            elif name=='fork-worker':
                other=copy.deepcopy(bad['workers'][0]);obj=decode(other['journal']['events'][-1]);obj['kind']='SUBMIT_DENIED';other['journal']['events'][-1]=encode(obj);bad['workers'].append(other)
            elif name=='wrong-anchor':ad=ZERO
            else:pin=ZERO
            try:reduce(bad,anchor,self.pub,pin,ad)
            except Rejected as exc:controls.append({'control':name,'status':'REJECTED','reason':str(exc)})
            else:raise AssertionError('tamper accepted: '+name)
        (self.out/'negative-controls.json').write_text(json.dumps(controls,indent=2)+'\n')
        code=f"import pathlib,tarfile; r=pathlib.Path({self.remote!r}); t=tarfile.open(r/'B.tar','w'); t.add(r/'B',arcname='B'); t.close()";self.ssh_run(['python3','-c',code],'archive-B.log');self.copy_from(self.remote+'/B.tar',self.out/'B.tar','collect-B.log')
        with tarfile.open(self.out/'B.tar') as tar:tar.extractall(self.out,filter='data')
        durable_new(self.a/'issuer.pub',regular(self.pub))
        return {'status':'PASS','scenarios':len(self.records),'records':self.records,'negative_controls':controls,'checkpoints':self.checkpoints,
                'final_replay':final,'public_digest':self.authority.public_digest.hex(),'scope':'experimental causal record/acceptance replay, not correctness/TRUSTED or formal EventRecord/Receipt','topology':'A trusted signed journal/acceptance; B authorized reference execution, immutable submissions and worker journal'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['peer','a-host','remote-root']:p.add_argument('--'+name,required=True)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args();m=Matrix(args)
    try:result=m.matrix();(m.out/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':'PASS','scenarios':result['scenarios'],'accepted':result['final_replay']['accepted']}))
    except BaseException as exc:(m.out/'report.json').write_text(json.dumps({'status':'FAIL','error':type(exc).__name__+': '+str(exc),'completed_scenarios':m.records},indent=2)+'\n');raise
    finally:m.close()
