#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Explicit LAN FM-S2 matrix. A authority/auditor; B executor; SSH control only.

Creates new private directories and touches only its own child processes. No
system service/firewall/VM changes, payments, adjudication or automatic guest retry.
"""

if not __debug__:
    raise SystemExit('assert-based validation requires Python without -O/PYTHONOPTIMIZE')

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import socket
import subprocess
import sys
import tarfile
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.formal_migration import s2,s2_fixture as fixture,foundation as f,policy as p
from tools.formal_migration.s2_transport import rpc
from tools.verification_profile import codec as c

def source_files():
    names=['tools/verification_profile/__init__.py','tools/verification_profile/codec.py','tests/formal_migration/policy-vectors.json','experiments/aclt-rir-stats-probe/tests/independent-vectors.json','scripts/fm-s2-client.py','scripts/fm-s2-service.py','scripts/fm-s2-dualhost.py']
    for directory,pattern in [('tools/formal_migration','*.py'),('tools/verification_profile/rust','*.rs'),('experiments/aclt-rir-stats-probe/src','*.rs')]:names += [x.relative_to(ROOT).as_posix() for x in sorted((ROOT/directory).glob(pattern))]
    return sorted(set(names))
def tar_bytes(entries):
    out=io.BytesIO()
    with tarfile.open(fileobj=out,mode='w') as t:
        for name,data in entries.items():
            entry=tarfile.TarInfo(name);entry.size=len(data);entry.mode=0o600;t.addfile(entry,io.BytesIO(data))
    return out.getvalue()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--peer',required=True);ap.add_argument('--a-host',required=True);ap.add_argument('--remote-root',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+',a.peer):ap.error('explicit user@host')
    if not re.fullmatch(r'/[A-Za-z0-9_/.-]+',a.remote_root) or '..' in Path(a.remote_root).parts or a.remote_root in ('/','/tmp','/home'):ap.error('new dedicated remote path')
    if a.output.exists():ap.error('new output required')
    a.output=a.output.resolve();a.output.mkdir(parents=True,mode=0o700);os.chmod(a.output,0o700)
    ssh=['ssh','-F','/dev/null','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10',a.peer]
    calls=[]
    def command(argv,log,expected=0,**kw):
        r=subprocess.run(argv,capture_output=True,timeout=180,**kw);(a.output/log).write_bytes(r.stdout+r.stderr);calls.append(dict(argv=argv,returncode=r.returncode,log=log));(a.output/'commands.json').write_text(json.dumps(calls,indent=2)+'\n')
        if expected is not None:assert r.returncode==expected,(log,r.returncode,r.stdout[-400:],r.stderr[-400:])
        return r
    def remote(cmd,log,**kw):return command(ssh+[cmd],log,**kw)
    rr=shlex.quote(a.remote_root);source={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in source_files()};(a.output/'source-sha256.json').write_text(json.dumps(source,indent=2)+'\n')
    entries={n:(ROOT/n).read_bytes() for n in source};entries['source-sha256.json']=json.dumps(source).encode()
    remote(f'umask 077; mkdir -- {rr} && tar -xf - -C {rr}','deploy.log',input=tar_bytes(entries))
    pre="import pathlib,json,hashlib,socket,platform; p=json.loads(pathlib.Path('source-sha256.json').read_text()); assert all(hashlib.sha256(pathlib.Path(n).read_bytes()).hexdigest()==v for n,v in p.items()); print(json.dumps(dict(hostname=socket.gethostname(),platform=platform.platform(),source_sha256=p)))"
    binfo=json.loads(remote(f'cd {rr} && python3 -c '+shlex.quote(pre),'B-preflight.json').stdout);assert binfo['hostname']!=socket.gethostname();assert binfo['source_sha256']==source
    compile_args=['rustc','--edition=2021','-D','warnings','-C','overflow-checks=yes','-O','experiments/aclt-rir-stats-probe/src/independent_executor.rs','-o']
    exe=a.output/'executor';command(compile_args+[str(exe)],'A-build.log',cwd=ROOT)
    remote(f'cd {rr} && '+shlex.join(compile_args+['executor']),'B-build.log')
    exe_hash=hashlib.sha256(exe.read_bytes()).digest()
    bh=remote(f'cd {rr} && sha256sum executor','B-runtime-hash.txt').stdout.decode().split()[0];assert bh==exe_hash.hex(),'independent binary pin differs'
    outcomes=[]
    scenarios=['normal','duplicate-activation','old-epoch','wrong-capability','bad-signature','legacy-start','concurrent-consume','exposure-reject','drop-activation-reply','drop-consume-reply','before-commit','after-commit','worker-after-intent','worker-after-consume','worker-after-guest','authority-down','deadline-fence']
    for index,name in enumerate(scenarios):
        case=a.output/name;case.mkdir(mode=0o700);private=case/'private';cfg,bundles=fixture.build(ROOT,private,exe_hash,count=3);database=private/'state.db';clock=private/'clock';clock.write_text('3000');fault=private/'fault'
        s2.Ledger(database,cfg,private/'issuer.pem',clock=lambda:3000,create=True)
        bpath=a.remote_root+'/'+name;bp=shlex.quote(bpath)
        bundle_raw=c.encode(bundles)
        remote(f'umask 077; mkdir -- {bp} && tar -xf - -C {bp}',name+'/deploy.log',input=tar_bytes({'config.cbor':c.encode(cfg),'bundles.cbor':bundle_raw,'executor.pem':(private/'executor.pem').read_bytes()}))
        proc=None;server_log=None;ready=None;restart=0
        def start():
            nonlocal proc,server_log,ready,restart
            restart+=1;ready=case/('ready-'+str(restart)+'.json');server_log=(case/('service-'+str(restart)+'.log')).open('wb')
            proc=subprocess.Popen([sys.executable,'-B',str(ROOT/'scripts/fm-s2-service.py'),'--host',a.a_host,'--config',str(private/'config.cbor'),'--private',str(private/'issuer.pem'),'--database',str(database),'--ready',str(ready),'--clock-file',str(clock),'--fault-file',str(fault)],cwd=ROOT,stdout=server_log,stderr=subprocess.STDOUT)
            for _ in range(200):
                if ready.exists():return json.loads(ready.read_text())['port']
                if proc.poll() is not None:raise RuntimeError('service exited: '+str(proc.returncode))
                time.sleep(.05)
            raise RuntimeError('service ready timeout')
        def stop():
            if proc is not None and proc.poll() is None:proc.terminate();proc.wait(timeout=15)
            if server_log:server_log.close()
        counter=0;port=start();notes=[]
        def local(op,i=0,role='REQUESTER',expected=0,**kwargs):
            nonlocal counter
            counter+=1;out=case/('A-call-'+str(counter));args=[sys.executable,'-B',str(ROOT/'scripts/fm-s2-client.py'),'--config',str(private/'config.cbor'),'--bundles',str(private/'bundles.cbor'),'--private',str(private/({'REQUESTER':'requester','EXECUTOR':'executor','AUDITOR':'auditor'}[role]+'.pem')),'--host',a.a_host,'--port',str(port),'--index',str(i),'--role',role,'--op',op,'--output',str(out)]
            for k,v in kwargs.items():
                args+=['--'+k.replace('_','-')]+([] if v is True else [str(v)])
            r=command(args,name+'/A-'+str(counter)+'.log',expected=expected,cwd=ROOT);return out,r
        def bcall(op,i=0,expected=0,**kwargs):
            nonlocal counter
            counter+=1;out=bpath+'/call-'+str(counter);args=['python3','-B','scripts/fm-s2-client.py','--config',bpath+'/config.cbor','--bundles',bpath+'/bundles.cbor','--private',bpath+'/executor.pem','--host',a.a_host,'--port',str(port),'--index',str(i),'--role','EXECUTOR','--op',op,'--output',out]
            for k,v in kwargs.items():args+=['--'+k.replace('_','-')]+([] if v is True else [str(v)])
            r=remote(f'cd {rr} && '+shlex.join(args),name+'/B-'+str(counter)+'.log',expected=expected);return out,r
        def state():return s2.Ledger(database,cfg,private/'issuer.pem',clock=lambda:int(clock.read_text())).state()
        def rejected(op,**kw):
            before=state();bcall(op,expected=2,**kw);assert state()==before,'rejection changed business state';notes.append('rejection projection unchanged')
        try:
            local('CREATE')
            if name in ('before-commit','after-commit'):fault.write_text(name.upper().replace('-','_'))
            if name=='drop-activation-reply':fault.write_text('DROP_REPLY')
            bo,_=bcall('ACTIVATE',expected=2 if name in ('before-commit','after-commit','drop-activation-reply') else 0)
            if name in ('before-commit','after-commit'):
                proc.wait(timeout=10);server_log.close();assert proc.returncode==(71 if name=='before-commit' else 72);port=start()
                held=state()['held'];assert held==(0 if name=='before-commit' else 17)
                # Exact retry queries the same right; cannot activate another Lease.
                bcall('ACTIVATE',reuse=bo+'/request.cbor');assert state()['held']==17;notes.append('real service process COMMIT boundary recovered')
            if name=='drop-activation-reply':
                bcall('QUERY');bcall('ACTIVATE',reuse=bo+'/request.cbor');assert state()['held']==17;notes.append('real TCP reply dropped after COMMIT')
            if name=='duplicate-activation':
                before=state();bcall('ACTIVATE',reuse=bo+'/request.cbor');assert state()==before
            elif name=='old-epoch':rejected('CONSUME',epoch=0)
            elif name=='wrong-capability':rejected('CONSUME',bad_capability=True)
            elif name=='bad-signature':rejected('CONSUME',bad_signature=True)
            elif name=='legacy-start':
                for op in ('CHECK','FUNDED_START','START','SETTLE'):rejected(op)
            elif name=='concurrent-consume':
                # Two distinct Provider-signed intents race over real LAN TCP.
                base=['python3','-B','scripts/fm-s2-client.py','--config',bpath+'/config.cbor','--bundles',bpath+'/bundles.cbor','--private',bpath+'/executor.pem','--host',a.a_host,'--port',str(port),'--role','EXECUTOR','--op','CONSUME']
                script='import subprocess,json; base='+repr(base)+'; ps=[subprocess.Popen(base+["--output",'+repr(bpath) +'+"/race-"+str(i)],stdout=subprocess.PIPE,stderr=subprocess.PIPE) for i in range(2)]; rs=[(p.communicate(),p.returncode) for p in ps]; print(json.dumps([r[1] for r in rs])); assert sorted(r[1] for r in rs)==[0,2]'
                remote(f'cd {rr} && python3 -c '+shlex.quote(script),name+'/race.log');notes.append('two signed concurrent consumes: one winner')
            elif name=='exposure-reject':
                local('ACTIVATE',role='AUDITOR');local('CREATE',i=1);bcall('ACTIVATE',i=1);local('ACTIVATE',i=1,role='AUDITOR')
                # Both assignment slots per Provider are occupied; fresh non-idempotent activation refuses.
                local('CREATE',i=2);rejected('ACTIVATE',i=2);assert state()['held']==34
            elif name=='drop-consume-reply':
                fault.write_text('DROP_CONSUME_REPLY')
                _,lost=bcall('WORK',runtime=a.remote_root+'/executor',directory=bpath+'/worker')
                assert json.loads(lost.stdout)['status']=='UNKNOWN_NO_REEXECUTION'
                bcall('WORK',runtime=a.remote_root+'/executor',directory=bpath+'/worker')
                remote('test -e '+shlex.quote(bpath+'/worker/intent')+' && test ! -e '+shlex.quote(bpath+'/worker/invocation'),name+'/no-unknown-invocation.log')
                assert state()['tasks'][p.bundle(bundles[0]).hex()]['leases']['EXECUTOR']['state']=='CONSUMED'
                notes.append('CONSUME committed but real reply lost; no guest and no restart retry')
            elif name.startswith('worker-'):
                point={'worker-after-intent':'AFTER_INTENT','worker-after-consume':'AFTER_CONSUME','worker-after-guest':'AFTER_GUEST'}[name]
                bcall('WORK',runtime=a.remote_root+'/executor',directory=bpath+'/worker',crash_hook=point,expected=73)
                _,retry=bcall('WORK',runtime=a.remote_root+'/executor',directory=bpath+'/worker');assert json.loads(retry.stdout)['status']=='UNKNOWN_NO_REEXECUTION';notes.append('real worker process exit at '+point+'; restart never invokes guest')
            elif name=='authority-down':
                stop();bcall('WORK',runtime=a.remote_root+'/executor',directory=bpath+'/worker',expected=None)
                # No authority response: the worker must have no invocation marker.
                remote('test ! -e '+shlex.quote(bpath+'/worker/invocation'),name+'/no-offline-invocation.log');port=start();notes.append('authority unavailable: no offline execution')
            elif name=='deadline-fence':
                clock.write_text('5000');before=state();bcall('CONSUME',now=5000,expected=2);assert state()==before
                local('FENCE',now=5000);s=state();assert s['held']==17 and s2.exposure(cfg,s)=={};notes.append('deadline fences start/exposure; funds pending FM-S3')
            else:
                if name=='normal':local('ACTIVATE',role='AUDITOR')
                bcall('WORK',runtime=a.remote_root+'/executor',directory=bpath+'/worker')
                if name=='normal':
                    bcall('WORK',runtime=a.remote_root+'/executor',directory=bpath+'/worker')
                    ao,_=local('WORK',role='AUDITOR',runtime=exe,directory=case/'A-worker')
                    raw=remote('cat '+shlex.quote(bpath+'/worker/observation'),name+'/B-observation.cbor').stdout;bb=c.decode(raw);aa=c.decode((ao/'result.cbor').read_bytes());assert aa['status']==bb['status']=='LOCAL_OBSERVATION_ONLY';ar=c.decode(aa['core']);br=c.decode(bb['core']);assert ar==br and ar['status']=='TASK_OUTCOME';notes.append('A/B exact raw-core outcome bytes/hash equal; no decision/payment')
            head=s2.Ledger(database,cfg,private/'issuer.pem',clock=lambda:int(clock.read_text())).replay()
            public=dict(scenario=name,status='PASS',notes=notes,genesis=s2.h(cfg).hex(),events=head['seq'],head=head['head'].hex(),state_digest=head['state_digest'].hex(),free=state()['free'],held=state()['held'],formal_admission=False)
            (case/'summary.json').write_text(json.dumps(public,indent=2)+'\n');outcomes.append(public)
            print(json.dumps(dict(scenario=name,status='PASS')),flush=True)
        finally:
            stop()
            # Preserve B evidence, excluding only the generated private Provider key.
            pack=remote(f'tar --exclude=executor.pem -cf - -C {bp} .',name+'/B-evidence.tar',expected=None)
    assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==v for n,v in source.items()),'source changed during matrix'
    result=dict(status='PASS',schema='FM-S2-limited-matrix@1',scope='candidate fixed-stats single-authority LAN integration',physical_hosts='DUALHOST-SSH-1 accepted assumption, no independence proof',A_hostname=socket.gethostname(),B_hostname=binfo['hostname'],runtime_sha256=exe_hash.hex(),source_sha256=source,scenarios=outcomes,scenario_count=len(outcomes),formal_admission=False,new_gate_claim=False,settlement=False)
    (a.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(status='PASS',scenarios=len(outcomes))))
if __name__=='__main__':main()
