import importlib.util,json,os,pathlib,subprocess,sys,tempfile,time,unittest
SCRIPT=pathlib.Path(__file__).resolve().parents[2]/'scripts/aclt-flow.py'
class FlowTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);(self.root/'.aclt-flow').mkdir();(self.root/'source').write_text('v1')
  self.config={'version':1,'coverage':'coverage.json','rules':'rules.json','jobs':[{'id':'test','title':'Test','command':[sys.executable,'-c','print("OK")'],'timeout_seconds':5,'inputs':['source'],'required_output':['OK'],'evidence':[]}],'decisions':[]};self.save()
 def tearDown(self):self.tmp.cleanup()
 def save(self):(self.root/'.aclt-flow/template.json').write_text(json.dumps(self.config))
 def runflow(self,action='run'):
  return subprocess.run([sys.executable,str(SCRIPT),action,'--root',str(self.root)],capture_output=True,text=True,timeout=20)
 def state(self):return json.loads((self.root/'.aclt-flow/state.json').read_text())['test']
 def test_pass_reused(self):
  self.assertEqual(self.runflow().returncode,0);first=self.state()['log'];self.assertEqual(self.runflow().returncode,0);self.assertEqual(self.state()['log'],first)
 def test_source_change_marks_stale(self):
  self.runflow();(self.root/'source').write_text('v2');self.runflow('status');self.assertEqual(self.state()['status'],'STALE')
 def test_fail_not_promoted_by_ok_text(self):
  self.config['jobs'][0]['command']=[sys.executable,'-c','print("OK");raise SystemExit(1)'];self.save();self.assertEqual(self.runflow().returncode,1);self.assertEqual(self.state()['status'],'FAIL')
 def test_missing_summary(self):
  self.config['jobs'][0]['command']=[sys.executable,'-c','print("nothing")'];self.save();self.runflow();self.assertEqual(self.state()['status'],'INCOMPLETE_OUTPUT')
 def test_timeout(self):
  self.config['jobs'][0].update(command=[sys.executable,'-c','import time;time.sleep(20)'],timeout_seconds=.1);self.save();self.runflow();self.assertEqual(self.state()['status'],'TIMEOUT')
 def test_midrun_source_mutation(self):
  self.config['jobs'][0]['command']=[sys.executable,'-c','from pathlib import Path;Path("source").write_text("v2");print("OK")'];self.save();self.runflow();self.assertEqual(self.state()['status'],'SOURCE_CHANGED')
 def test_tampered_evidence(self):
  self.runflow();(self.root/self.state()['log']).write_text('forged OK');self.runflow('status');self.assertEqual(self.state()['status'],'EVIDENCE_INVALID')
 def test_no_automatic_decision(self):
  self.config['decisions']=[{'id':'d','title':'Decision','status':'OPEN','owner':'A','basis':'rule','decision':''}];self.save();self.runflow();self.assertIn('需要决定',(self.root/'ACLT-PROGRESS.md').read_text());self.assertEqual(json.loads((self.root/'.aclt-flow/template.json').read_text())['decisions'][0]['status'],'OPEN')
 def test_missing_decision_rejected(self):
  self.config['decisions']=[{'id':'d','title':'Decision','status':'DECIDED','owner':'A','basis':'rule','decision':''}];self.save();self.assertEqual(self.runflow().returncode,2)
 def test_concurrent_run_excluded(self):
  self.config['jobs'][0]['command']=[sys.executable,'-c','import time;print("OK");time.sleep(2)'];self.save()
  p=subprocess.Popen([sys.executable,str(SCRIPT),'run','--root',str(self.root)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  try:
   until=time.monotonic()+5
   while time.monotonic()<until:
    path=self.root/'.aclt-flow/state.json'
    if path.exists() and json.loads(path.read_text()).get('test',{}).get('status')=='RUNNING':break
    time.sleep(.01)
   self.assertEqual(self.runflow().returncode,2)
  finally:p.communicate(timeout=10)
 def test_decision_edit_does_not_rerun_tests(self):
  self.runflow();first=self.state()['log'];self.config['decisions']=[{'id':'d','title':'D','status':'DECIDED','owner':'A','basis':'rule','decision':'documented choice'}];self.save();self.runflow();self.assertEqual(self.state()['log'],first)
 def test_rule_coverage_not_closed_by_pass(self):
  (self.root/'coverage.json').write_text(json.dumps({'implemented':{},'partial':{}}));(self.root/'rules.json').write_text(json.dumps({'rules':[{'rule':'SV-02','kind':'A'}]}));self.runflow();self.assertEqual(json.loads((self.root/'.aclt-flow/rules-status.json').read_text())[0]['implementation'],'NOT_IMPLEMENTED')
 def test_dependency_failure_blocks_following_job(self):
  self.config['jobs'][0]['command']=[sys.executable,'-c','raise SystemExit(1)']
  child=dict(self.config['jobs'][0]);child.update(id='child',needs=['test'],command=[sys.executable,'-c','print("OK")']);self.config['jobs'].append(child);self.save();self.runflow()
  state=json.loads((self.root/'.aclt-flow/state.json').read_text());self.assertEqual(state['child']['status'],'BLOCKED_DEPENDENCY');self.assertNotIn('log',state['child'])
 def test_open_decision_blocks_execution(self):
  self.config['decisions']=[{'id':'d','title':'D','status':'OPEN','owner':'A','basis':'rule','decision':''}];self.config['jobs'][0]['requires_decisions']=['d'];self.save();self.runflow();self.assertEqual(self.state()['status'],'BLOCKED_DECISION')
 def test_orphaned_running_record_is_interrupted(self):
  (self.root/'.aclt-flow/state.json').write_text(json.dumps({'test':{'status':'RUNNING'}}));self.runflow('status');self.assertEqual(self.state()['status'],'INTERRUPTED')
 def test_deleted_artifact_invalidates_pass(self):
  (self.root/'evidence.json').write_text('{}');self.config['jobs'][0]['evidence']=['evidence.json'];self.save();self.runflow()
  artifact=(self.root/self.state()['log']).parent/'artifacts/evidence.json';artifact.unlink();self.runflow('status');self.assertEqual(self.state()['status'],'EVIDENCE_INVALID')
 def test_bound_decision_change_invalidates_result(self):
  self.config['decisions']=[{'id':'d','title':'D','status':'DECIDED','owner':'A','basis':'rule','decision':'first rule'}];self.config['jobs'][0]['requires_decisions']=['d'];self.save();self.runflow()
  self.config['decisions'][0]['decision']='changed rule';self.save();self.runflow('status');self.assertEqual(self.state()['status'],'STALE')
 def test_duplicate_decision_id_rejected(self):
  self.config['decisions']=[{'id':'d','title':'D','status':'OPEN','owner':'A','basis':'rule','decision':''}]*2;self.save();self.assertEqual(self.runflow().returncode,2)
 def test_build_environment_change_invalidates_result(self):
  from unittest.mock import patch
  self.runflow()
  with patch.dict(os.environ,{'RUSTFLAGS':'--cfg workflow_environment_test'}):self.runflow('status')
  self.assertEqual(self.state()['status'],'STALE')
if __name__=='__main__':unittest.main()
