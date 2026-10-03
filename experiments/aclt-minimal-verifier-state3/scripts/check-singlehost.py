#!/usr/bin/env python3
"""Remaining local scheduler boundaries, quotas and task binding; no network claims."""
import ctypes, hashlib, json, os, pathlib, signal, subprocess, tempfile, time
ROOT=pathlib.Path(__file__).resolve().parents[1];COORD=ROOT/'target/debug/coordinator';WORKER=ROOT/'build/worker'
assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0
records=[];children=[]
def launch(args,pause=None,extra=None):
 env={k:v for k,v in os.environ.items() if not k.startswith('ACLT_TEST_')}
 if pause:env['ACLT_TEST_PAUSE']=pause
 env.update(extra or {})
 p=subprocess.Popen([str(COORD),*map(str,args)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env);children.append(p);return p

def finish(p,ok=True,reason=None):
 out,err=p.communicate(timeout=15)
 assert (p.returncode==0)==ok,(p.returncode,out,err)
 if reason:assert reason in err,(reason,err)
 return out,err

def checkpoint(p,d,point):
 until=time.monotonic()+6
 while time.monotonic()<until:
  if p.poll() is not None:raise AssertionError(p.communicate())
  if (d/'checkpoint.txt').exists() and (d/'checkpoint.txt').read_text()==point+'\n':return
  time.sleep(.005)
 raise AssertionError('checkpoint timeout '+point)

def stop(p,d,point):
 checkpoint(p,d,point);p.kill();p.communicate(timeout=5)
 until=time.monotonic()+5
 while time.monotonic()<until:
  try:
   pid,_=os.waitpid(-1,os.WNOHANG)
   if pid:continue
  except ChildProcessError:return
  time.sleep(.005)
 raise AssertionError('cleanup timeout')

def resume(d,ok=True,reason=None):return finish(launch(['resume',d]),ok,reason)
def state(d):
 raw=(d/'state.txt').read_text();head,digest,body=raw.split('\n',2)
 assert head=='ACLT-STATE-3' and hashlib.sha256(body.encode()).hexdigest()==digest
 lines=body.splitlines();return lines[0].split()[-1],lines[-2].split(),lines

def mutate(d,change):
 lines=(d/'state.txt').read_text().splitlines()[2:];change(lines);body='\n'.join(lines)+'\n'
 (d/'state.txt').write_text('ACLT-STATE-3\n'+hashlib.sha256(body.encode()).hexdigest()+'\n'+body)

def record(name,d,detail):
 records.append({'case':name,'passed':True,'detail':detail,'state':(d/'state.txt').read_text() if (d/'state.txt').exists() else None,'publication':(d/'results.txt').exists(),'logical_bytes':sum(p.stat().st_size for p in d.iterdir() if p.is_file())})
with tempfile.TemporaryDirectory(prefix='aclt-singlehost-') as tmp:
 base=pathlib.Path(tmp);source=base/'source';source.write_text('3 -1 8 0 -7 12 5 2 -3 9\n')
 def new(name,pause=None,units=1000,storage=1000000,log=100000,ttl=30000,attempts=3,worker=WORKER,extra=None,timeout=1000,chunk=4,recoveries=10):
  d=base/name;p=launch([source,chunk,worker,d,'normal',timeout,attempts,ttl,recoveries,units,storage,log],pause,extra);return d,p
 try:
  for units,ok in [(0,False),(19,False),(20,True)]:
   d,p=new('verification-limit-'+str(units),units=units);finish(p,ok,None if ok else 'VERIFY');phase,limits,_=state(d)
   assert int(limits[6])<=units and phase==('DONE' if ok else 'FAILED')
   record(d.name,d,'10 input integers; normal checks need exactly 20 comparison units')

  d,p=new('verification-reservation-survives','verification-reserved');stop(p,d,'verification-reserved');before=int(state(d)[1][6]);assert before>0
  resume(d);assert int(state(d)[1][6])>=before+20;record(d.name,d,'interrupted reserved units are not refunded')

  d,p=new('verification-save-failed',extra={'ACLT_TEST_IO_FAIL':'verification:save:1'});finish(p,False,'injected I/O')
  assert int(state(d)[1][6])==0 and not any('ACCEPT_BLOCK' in p.read_text() for p in d.glob('events.tsv'))
  resume(d);record(d.name,d,'no result validation/acceptance before counter commit')

  d,p=new('recovery-check-is-charged','accepted');stop(p,d,'accepted');before=int(state(d)[1][6]);resume(d)
  assert int(state(d)[1][6])>20 and int(state(d)[1][6])>before;record(d.name,d,'accepted block revalidation consumes units on active recovery')

  d,p=new('published-budget-spent','published',units=20);stop(p,d,'published');resume(d)
  assert state(d)[0]=='DONE' and state(d)[1][6]=='20';resume(d)
  assert state(d)[1][6]=='20';record(d.name,d,'published decisions remain valid; completed read-only audits do not restart work')

  for budget in [0,100]:
   d,p=new('log-limit-'+str(budget),log=budget);finish(p,False,'LOG')
   assert state(d)[0]=='FAILED' and (d/'events.tsv').stat().st_size<=budget
   before=(d/'state.txt').read_bytes();resume(d,False,'terminal FAILED');assert before==(d/'state.txt').read_bytes()
   record(d.name,d,'diagnostic append stops before byte limit and terminal state persists')

  d,p=new('storage-limit','saved',storage=20000);checkpoint(p,d,'saved')
  used=sum(p.stat().st_size for p in d.iterdir() if p.is_file());(d/'occupancy-test').write_bytes(b'x'*(20000-used-2048))
  (d/'checkpoint.release').write_text('saved');finish(p,False,'STORAGE')
  assert state(d)[0]=='FAILED' and sum(p.stat().st_size for p in d.iterdir() if p.is_file())<=20000
  record(d.name,d,'reserve preserves space for terminal snapshot when work capacity is depleted')

  d,p=new('storage-admission-refused',storage=4096);out,err=finish(p,False,'STORAGE')
  assert not list(d.glob('block-*'));record(d.name,d,'insufficient initial space fails before workers')

  for stream in ['stdout','stderr']:
   worker=base/('noisy-'+stream);worker.write_text('#!/usr/bin/python3\nimport sys\ngetattr(sys,"'+stream+'").write("x"*100000)\n');worker.chmod(0o755)
   d,p=new('worker-output-limit-'+stream,worker=worker,attempts=1);finish(p,False,'ATTEMPTS')
   assert all(p.stat().st_size<=256 for p in d.glob('block-*'))
   record(d.name,d,'kernel file size limit bounds each direct worker output and error file')

  d,p=new('source-task');finish(p);foreign=(d/'block-0-attempt-1.txt').read_bytes()
  d,p=new('cross-task-replay','output',attempts=1);checkpoint(p,d,'output')
  (d/'block-0-attempt-1.txt').write_bytes(foreign);(d/'checkpoint.release').write_text('output')
  finish(p,False,'ATTEMPTS');assert not (d/'results.txt').exists();record(d.name,d,'same numeric answer and attempt from a different task ID is rejected')

  for field,index,value in [('chunk',0,'5'),('timeout',1,'999'),('attempts',2,'4'),('scenario',3,'slow')]:
   d,p=new('bound-'+field,'saved');stop(p,d,'saved')
   def change(lines):
    config=lines[0].split();config[index]=value;lines[0]=' '.join(config)
   mutate(d,change);resume(d,False);assert not list(d.glob('block-*'));record(d.name,d,'changing state while recomputing its checksum cannot bypass the frozen contract')

  for field,index in [('deadline',2),('recoveries',4),('verify-budget',7),('storage-budget',8),('log-budget',9)]:
   d,p=new('bound-'+field,'saved');stop(p,d,'saved')
   def change(lines):
    limits=lines[-2].split();limits[index]=str(int(limits[index])+1);lines[-2]=' '.join(limits)
   mutate(d,change);resume(d,False,'contract mismatch');record(d.name,d,'immutable limit changed in state is refused')

  for name,mode in [('missing-contract','missing'),('unknown-contract-version','version'),('contract-rule-change','rule')]:
   d,p=new(name,'saved');stop(p,d,'saved');path=d/'contract.txt'
   if mode=='missing':path.unlink()
   elif mode=='version':path.write_text(path.read_text().replace('CONTRACT-1','CONTRACT-99'))
   else:path.write_text(path.read_text().replace('stats-int-v1','stats-int-v2'))
   resume(d,False);assert not list(d.glob('block-*'));record(d.name,d,'missing or changed frozen contract fails closed')

  d,p=new('deadline-and-verification-empty','saved',units=0,ttl=100);stop(p,d,'saved');time.sleep(.15)
  resume(d,False,'DEADLINE');assert state(d)[0]=='EXPIRED';record(d.name,d,'local deadline is checked before starting new budgeted work; not the funding DAG rule')

  for timeout in [50,5000,5001,10000]:
   d,p=new('timeout-boundary-'+str(timeout),timeout=timeout);finish(p)
   record(d.name,d,'every declared timeout boundary remains usable; worker accepts doubled test delay')
  for chunk in [1,100000]:
   d,p=new('chunk-boundary-'+str(chunk),chunk=chunk);finish(p);record(d.name,d,'declared chunk boundaries')
  for attempts in [1,5]:
   d,p=new('attempt-boundary-'+str(attempts),attempts=attempts);finish(p);record(d.name,d,'declared attempt boundaries')
  d,p=new('maximum-task-ttl',ttl=86400000);finish(p);record(d.name,d,'maximum TTL is accepted')
  d,p=new('maximum-resource-values',units=100000000,storage=268435456,log=16777216,recoveries=100);finish(p)
  record(d.name,d,'declared maximum quota values are accepted')
  d,p=new('minimum-ttl-admission','saved',ttl=50);stop(p,d,'saved');time.sleep(.06);resume(d,False,'DEADLINE')
  record(d.name,d,'minimum TTL is admitted, then expires without being extended')
  invalid=[('timeout',49),('timeout',10001),('chunk',0),('chunk',100001),('attempts',0),('attempts',6),('ttl',49),('ttl',86400001),('recoveries',101),('recoveries',-1),('units',100000001),('units',-1),('storage',4095),('storage',268435457),('log',16777217),('log',-1)]
  for key,value in invalid:
   d,p=new('invalid-'+key+'-'+str(value),**{key:value});finish(p,False)
   assert not list(d.glob('block-*')) and not (d/'results.txt').exists();record(d.name,d,'invalid admission limit refused before execution')

  d,p=new('publication-after-log-failure',extra={'ACLT_TEST_IO_FAIL':'events.tsv:write:7'});finish(p,False,'injected I/O')
  assert state(d)[0]=='DONE';resume(d);assert state(d)[0]=='DONE';record(d.name,d,'post-commit log failure cannot undo published success')
 finally:
  for p in children:
   if p.poll() is None:p.kill();p.communicate(timeout=5)
  while True:
   try:
    pid,_=os.waitpid(-1,os.WNOHANG)
    if not pid:break
   except ChildProcessError:break
(ROOT/'build/singlehost-tests.json').write_text(json.dumps({'passed':len(records),'cases':records},indent=2)+'\n')
print(f'PASS: {len(records)} single-host quota, task-binding and boundary scenarios')
