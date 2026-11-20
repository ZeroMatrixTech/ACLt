"""Adversarial tests of implemented bootstrap rules; not full P0-1B conformance."""
import copy, itertools, json, pathlib, subprocess, sys, tempfile, unittest
from fractions import Fraction
from test_validator import bounded_profile, REDUCER_REF
from tools.verification_profile.validator import parse_uint,parse_rational,reduce_causes,validate,validate_assumption_snapshot
ROOT=pathlib.Path(__file__).resolve().parents[2]
CODES=('WINDOW_EXPIRED','OUT_OF_SCOPE','REVOKED')
def snapshot(a=(),b=()):
 return {'reducer_ref':REDUCER_REF,'assumption_states':[{'assumption_id':f'ACL-ASM-000{i+1}','cause_set':[{'cause_code':c} for c in sorted(codes)],'effective_verdict':next((c for c in reversed(CODES) if c in codes),'VALID')} for i,codes in enumerate((a,b))]}
class SingleHostValidationTests(unittest.TestCase):
 def test_uint_boundaries(self):
  for s in ['0','1',str(2**64-1)]:self.assertEqual(parse_uint(s),int(s))
  for v in ['',None,0,True,'00','01','+1','-0','-1','1.0',' 1','1\n','１','١',str(2**64),'9'*5000]:
   with self.subTest(v=str(v)[:30]),self.assertRaises(ValueError):parse_uint(v)
 def test_rational_boundaries(self):
  for value in [['0','1'],['-1','2'],[str(-(2**63)),'1'],[str(2**63-1),'1']]:self.assertEqual(parse_rational(value),Fraction(*map(int,value)))
  for value in [None,{},[],['1'],['1','2','3'],[1,'2'],['1','0'],['2','4'],['0','2'],['-0','1'],['+1','2'],[str(2**63),'1'],[str(-(2**63)-1),'1'],['9'*5000,'1']]:
   with self.subTest(value=str(value)[:40]),self.assertRaises(ValueError):parse_rational(value)
 def test_profile_shape_rejected_without_crash(self):
  for value in [None,[],0,False,'x']:
   self.assertTrue(validate(value))
  for key in ['schema_version','encoding_profile_id','verification_method','assumption_references']:
   for value in [None,[],{},0,True,'unknown']:
    if key=='assumption_references' and value==[]:continue  # SV-38 semantic completeness remains unimplemented.
    p=bounded_profile();p[key]=value
    with self.subTest(key=key,value=value):self.assertTrue(validate(p))
 def test_required_unknown_and_identifier_fields(self):
  base=bounded_profile()
  for key in base:
   if key in ('safety_parameters','liveness_parameters'):continue
   p=copy.deepcopy(base);del p[key];self.assertTrue(validate(p),key)
  p=copy.deepcopy(base);p['unknown']=1;self.assertTrue(validate(p))
  for key in ['profile_id','task_type','profile_digest']:
   for value in ['',None,[],{},'UPPER','x\n']:
    p=copy.deepcopy(base);p[key]=value;self.assertTrue(validate(p),(key,value))
 def test_assumption_rows_and_unique_ids(self):
  for rows in [[7],[None],[[]],[{}],[{'assumption_id':[]}],[{'assumption_id':'ACL-ASM-0001','role':[]}]]:
   p=bounded_profile();p['assumption_references']=rows;self.assertTrue(validate(p))
  p=bounded_profile();p['assumption_references']*=2;self.assertTrue(validate(p))
 def test_method_parameter_matrix(self):
  for method in ['DIRECT_VERIFIED','PROOF_VERIFIED','REEXEC_BOUNDED','REEXEC_AUDIT_ONLY']:
   for safety,live in itertools.product([False,True],repeat=2):
    p=bounded_profile();p['verification_method']=method
    if method=='REEXEC_AUDIT_ONLY':p['verified_claim_spec']='BOTTOM'
    if not safety:del p['safety_parameters']
    if not live:del p['liveness_parameters']
    wanted=safety and live if method=='REEXEC_BOUNDED' else not safety and not live
    self.assertEqual(not validate(p),wanted,(method,safety,live))
  for method in ['DIRECT_VERIFIED','PROOF_VERIFIED','REEXEC_BOUNDED','REEXEC_AUDIT_ONLY']:
   for bottom in [False,True]:
    p=bounded_profile();p['verification_method']=method;p['verified_claim_spec']='BOTTOM' if bottom else {}
    if method!='REEXEC_BOUNDED':del p['safety_parameters'];del p['liveness_parameters']
    self.assertEqual(not validate(p),bottom==(method=='REEXEC_AUDIT_ONLY'))
 def test_exact_bound_grid(self):
  for g in range(1,10):
   for b in range(10):
    for q in range(11):
     p=bounded_profile();p['safety_parameters']={'G':str(g),'B':str(b),'delta_min':['1',str(g)]};p['liveness_parameters']={'Q':str(q)}
     p['method_parameters']['mixture_weights']=[{'m':str(q),'weight':['1','1']}]
     self.assertEqual(not validate(p),0<=b<q<=g,(g,b,q))
 def test_exact_gap_limits(self):
  for delta,ok in [(['2','5'],True),(['1','5'],True),(['3','5'],False),(['0','1'],False),(['-1','5'],False),(['2','10'],False)]:
   p=bounded_profile();p['safety_parameters']['delta_min']=delta;self.assertEqual(not validate(p),ok)
 def test_weight_table_cases(self):
  for weights,ok in [([(4,['1','1'])],True),([(0,['0','1']),(4,['1','1'])],True),([],False),([(4,['1','2'])],False),([(4,['-1','1']),(5,['2','1'])],False),([(4,['1','2']),(4,['1','2'])],False),([(5,['1','2']),(4,['1','2'])],False),([(3,['1','1'])],False)]:
   p=bounded_profile();p['method_parameters']['mixture_weights']=[{'m':str(m),'weight':w} for m,w in weights];self.assertEqual(not validate(p),ok,weights)
 def test_all_cause_sets_and_permutations(self):
  for n in range(4):
   for codes in itertools.permutations(CODES,n):
    original=list(codes);expected=next((c for c in reversed(CODES) if c in codes),'VALID')
    self.assertEqual(reduce_causes(original),expected);self.assertEqual(original,list(codes))
  for codes in [[c,c] for c in CODES]+[['UNKNOWN'],[None],[{}],None,'REVOKED']:
   with self.assertRaises(ValueError):reduce_causes(codes)
 def test_all_snapshot_cause_combinations(self):
  sets=[tuple(c for i,c in enumerate(CODES) if mask>>i&1) for mask in range(8)]
  for a,b in itertools.product(sets,repeat=2):
   s=snapshot(a,b)
   self.assertFalse(validate_assumption_snapshot(bounded_profile(),s,REDUCER_REF,'UNRESOLVED'))
   self.assertEqual(not validate_assumption_snapshot(bounded_profile(),s,REDUCER_REF,'TRUSTED'),not a)
 def test_snapshot_shape_rejected(self):
  for value in [None,[],7,'x']:
   self.assertTrue(validate_assumption_snapshot(bounded_profile(),value,REDUCER_REF,'TRUSTED'))
  for bad in [None,{},7,[7],[{}],[{'assumption_id':[]}]]:
   s=snapshot();s['assumption_states']=bad;self.assertTrue(validate_assumption_snapshot(bounded_profile(),s,REDUCER_REF,'TRUSTED'))
  for bad in [None,{},7,[7],[{}],[{'cause_code':[]}],[{'cause_code':'UNKNOWN'}]]:
   s=snapshot();s['assumption_states'][0]['cause_set']=bad;self.assertTrue(validate_assumption_snapshot(bounded_profile(),s,REDUCER_REF,'TRUSTED'))
 def test_snapshot_coverage_order_duplicates_and_claimed_verdict(self):
  base=snapshot()
  variants=[]
  for rows in [[],base['assumption_states'][:1],base['assumption_states'][::-1],base['assumption_states']*2]:
   s=copy.deepcopy(base);s['assumption_states']=rows;variants.append(s)
  s=snapshot(CODES);s['assumption_states'][0]['cause_set'].reverse();variants.append(s)
  s=snapshot(['REVOKED']);s['assumption_states'][0]['effective_verdict']='VALID';variants.append(s)
  s=snapshot();s['reducer_ref']={};variants.append(s)
  for s in variants:self.assertTrue(validate_assumption_snapshot(bounded_profile(),s,REDUCER_REF,'TRUSTED'))
 def test_cli_production_always_refuses(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td)/'profile.json';p.write_text(json.dumps(bounded_profile()))
   r=subprocess.run([sys.executable,'-B','-m','tools.verification_profile.validator',str(p),'--production'],cwd=ROOT,capture_output=True,text=True)
   self.assertEqual(r.returncode,0);self.assertNotIn('COVERAGE',r.stdout);self.assertNotIn('Traceback',r.stderr)
 def test_cli_malformed_json(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td)/'bad.json'
   for raw in [b'{',b'null',b'[]',b'{"schema_version":"1","schema_version":"2"}',b'NaN',b'\xff']:
    p.write_bytes(raw);r=subprocess.run([sys.executable,'-B','-m','tools.verification_profile.validator',str(p)],cwd=ROOT,capture_output=True,text=True)
    self.assertEqual(r.returncode,1);self.assertTrue(json.loads(r.stdout));self.assertNotIn('Traceback',r.stderr)
