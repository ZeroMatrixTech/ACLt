"""Strict policy tests: execution/receipt evidence, not a distributed vote simulation."""
import hashlib,json,os,pathlib,shutil,subprocess,tempfile,time
E=pathlib.Path(__file__).resolve().parents[1];C=pathlib.Path(os.environ.get('ACLT_COORDINATOR',str(E/'target/debug/coordinator-test-registry')));W=E/'build/worker'
B=pathlib.Path(tempfile.mkdtemp(prefix='strict-'));R=B/'registry';I=B/'input'
I.write_text('3 -1 8 0 -7 12 5 2 -3 9\n');records=[]
def call(args,env=None):
 p=subprocess.run(list(map(str,[C,*args])),capture_output=True,text=True,env=env,timeout=30)
 return {'rc':p.returncode,'out':p.stdout,'err':p.stderr}
def command(run,inp=I,chunk=4,worker=W,scenario='normal',timeout=1000,maximum=1,registry=R):
 return [inp,chunk,worker,run,scenario,timeout,maximum,registry]
def check(name,condition,details=None):
 assert condition,(name,details)
 records.append({'name':name,'passed':True,'details':details})
def manifest(root):
 return {str(p.relative_to(root)):(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns) for p in root.rglob('*') if p.is_file()}
def reject(name,args,run=None,env=None):
 p=call(args,env);check(name,p['rc']!=0 and (run is None or not run.exists()),p);return p
def wait(p,run,point):
 end=time.monotonic()+10
 while time.monotonic()<end:
  if p.poll() is not None:raise AssertionError(p.communicate())
  if (run/'checkpoint.txt').exists() and (run/'checkpoint.txt').read_text()==point+'\n':return
  time.sleep(.005)
 raise AssertionError('checkpoint timeout')
try:
 check('init',call(['init-registry',R])['rc']==0)
 reject('existing-registry-never-reset',['init-registry',R])
 p=call(command(B/'normal'));check('normal-complete',p['rc']==0,p)
 claims=list(R.glob('*.claim'));receipts=list(R.glob('*.receipt'))
 check('one-whole-task-receipt',len(claims)==len(receipts)==1 and len(list((B/'normal').glob('block-*-attempt-1.txt')))==3)
 before=manifest(R)
 for n in range(3):check('audit-idempotent-'+str(n),call(['audit',R,I])['out'].count('local_contributions=1')==1)
 check('audit-no-mutations',manifest(R)==before)
 alt=B/'whitespace';alt.write_text('  03\t-1 8\n0 -7 12 5 2 -3 9  \n')
 worker=B/'worker-copy';shutil.copy2(W,worker)
 for name,kwargs in [('directory',{}),('canonical-input',{'inp':alt}),('chunk',{'chunk':2}),('timeout',{'timeout':2000}),('worker-path',{'worker':worker}),('scenario',{'scenario':'wrong'})]:
  run=B/('duplicate-'+name);reject('duplicate-'+name,command(run,**kwargs),run)
 check('duplicates-no-new-records',manifest(R)==before)
 shutil.rmtree(B/'normal');reject('deleted-run-still-consumed',command(B/'after-deletion'),B/'after-deletion')
 reject('resume-no-files',['resume',B/'absent'])
 check('resume-no-registry-mutation',manifest(R)==before)
 reject('missing-registry',command(B/'no-registry',registry=B/'missing'),B/'no-registry')
 check('missing-registry-not-recreated',not (B/'missing').exists())
 reject('legacy-entry-disabled',[I,4,W,B/'legacy','normal',1000,1],B/'legacy')
 reject('retry-budget-disabled',command(B/'retry',maximum=2),B/'retry')
 reject('recovery-budget-disabled',[I,4,W,B/'recovery','normal',1000,1,600000,1,R],B/'recovery')
 other=B/'other';other.write_text('1 2 3\n');check('different-input-allowed',call(command(B/'different',inp=other))['rc']==0)
 for scenario in ['wrong','crash','hang','malformed','duplicate','wrong-attempt']:
  reg=B/('reg-'+scenario);call(['init-registry',reg]);run=B/('failed-'+scenario)
  p=call(command(run,scenario=scenario,timeout=100,registry=reg))
  check('failed-zero-contribution-'+scenario,p['rc']!=0 and not list(reg.glob('*.receipt')) and not list(run.glob('*attempt-2*')),p)
  reject('failed-no-resubmit-'+scenario,command(B/('again-'+scenario),registry=reg),B/('again-'+scenario))
  m=manifest(reg);reject('same-boot-no-resume-'+scenario,['resume',run]);check('no-resume-mutation-'+scenario,manifest(reg)==m)
 # Concurrent duplicate and read-only audit must not observe a live commit.
 reg=B/'concurrent';call(['init-registry',reg]);run=B/'paused'
 env=dict(os.environ,ACLT_TEST_PAUSE='saved');p=subprocess.Popen(list(map(str,[C,*command(run,registry=reg)])),env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 wait(p,run,'saved');reject('concurrent-duplicate',command(B/'competitor',registry=reg),B/'competitor')
 reject('audit-live-reservation',['audit',reg,I]);p.kill();p.communicate(timeout=5)
 reject('killed-attempt-no-resubmit',command(B/'after-kill',registry=reg),B/'after-kill')
 check('killed-zero-contribution',not list(reg.glob('*.receipt')))
 # Faults at each admission/acceptance I/O boundary. Real kernel faults are separate VM cases.
 for obj,stage in [('claim','write'),('claim','file_sync'),('claim','dir_sync'),('receipt','write'),('receipt','file_sync'),('receipt','publish'),('receipt','dir_sync')]:
  for errno in [5,28,30]:
   name=f'{obj}-{stage}-{errno}';reg=B/name;call(['init-registry',reg]);run=B/('run-'+name)
   env=dict(os.environ,ACLT_TEST_IO_FAIL=f'{obj}:{stage}:1',ACLT_TEST_IO_ERRNO=str(errno))
   p=call(command(run,registry=reg),env)
   check('injected-failure-'+name,p['rc']!=0 and 'injected I/O failure' in p['err'],p)
   n=len(list(reg.glob('*.receipt')))
   check('receipt-boundary-'+name,n==(1 if (obj,stage)==('receipt','dir_sync') else 0))
   if n:check('ambiguous-ack-auditable-'+name,call(['audit',reg,I])['rc']==0)
   reject('fault-no-resubmit-'+name,command(B/('again-'+name),registry=reg),B/('again-'+name))
   if obj=='claim':check('no-worker-before-durable-claim-'+name,not run.exists())
 # Corruption/redirect cases use independent registries, never reset live eligibility.
 for target in ['unit.txt','registry.lock']:
  reg=B/('link-'+target);call(['init-registry',reg]);(reg/target).unlink();(reg/target).symlink_to(I)
  reject('symlink-'+target,command(B/('run-link-'+target),registry=reg),B/('run-link-'+target))
 reg=B/'bad-unit';call(['init-registry',reg]);(reg/'unit.txt').write_text('broken\n')
 reject('corrupt-registry',command(B/'bad-unit-run',registry=reg),B/'bad-unit-run')
 # Tampering is detected on audit; disk ownership is nevertheless trusted.
 receipt=receipts[0];data=receipt.read_bytes();receipt.write_bytes(data[:-3]+b'999')
 reject('corrupt-receipt-audit',['audit',R,I]);receipt.write_bytes(data)
 claim=claims[0];data=claim.read_bytes();claim.write_bytes(b'')
 reject('truncated-claim-consumed',command(B/'truncated-run'),B/'truncated-run')
 reject('receipt-claim-binding-audit',['audit',R,I]);claim.write_bytes(data)
 result={'passed':True,'cases':len(records),'records':records,'scope':'trusted local registry, no distributed identity/voting'}
 output=pathlib.Path(os.environ.get('ACLT_STRICT_TEST_REPORT',str(E/'build/strict-tests.json')))
 output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'passed':True,'cases':len(records),'report':str(output)}))
finally:
 shutil.rmtree(B)
