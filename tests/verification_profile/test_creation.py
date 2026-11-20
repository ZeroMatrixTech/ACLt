# SPDX-License-Identifier: Apache-2.0
import copy,hashlib,json,runpy,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
from tools.verification_profile import codec as c,creation as r,validator
DRIVER=runpy.run_path(str(ROOT/'scripts/check-creation-bindings.py'))


class CreationTests(unittest.TestCase):
    def setUp(self):
        self.value,self.lock,self.contract=DRIVER['fixture']();self.t,self.e,self.o=DRIVER['parts'](self.value)

    def test_frozen_vectors(self):
        rows=json.loads(DRIVER['VECTOR'].read_text())['vectors']
        self.assertEqual(rows,DRIVER['vectors']())
        for row in rows:
            with self.subTest(id=row['id']):
                args=(row['mode'],bytes.fromhex(row['cbor_hex']),bytes.fromhex(row['lock_pin']),bytes.fromhex(row['contract_pin']))
                if row['id'] in DRIVER['SHA_RECORD_ONLY_CASES']:
                    DRIVER['evaluate'](*args)
                elif row['valid']:self.assertEqual(DRIVER['evaluate'](*args),row['expected'])
                else:
                    with self.assertRaises((c.CodecError,KeyError,TypeError)):DRIVER['evaluate'](*args)

    def test_three_domain_hashes_against_independent_projection(self):
        for kind,value,tag in [('CreationContext',self.e['creation_context'],'CreationContext'),('PhaseIRecord',self.o,'PhaseIValidationRecord'),('ReceiptIntent',self.e['intent'],'ReceiptIntent')]:
            if kind=='ReceiptIntent':projection=copy.deepcopy(value)
            else:projection={k:v for k,v in value['header'].items() if k!='digest'}|{k:v for k,v in value.items() if k!='header'}
            prefix=('ACLt/P0-1/'+tag+'/1').encode()
            self.assertEqual(r.object_digest(value,kind),hashlib.sha256(bytes([len(prefix)])+prefix+c.encode(projection)).digest())

    def test_runtime_ids_are_hashed_digest_field_is_excluded(self):
        for kind,value in [('CreationContext',self.e['creation_context']),('PhaseIRecord',self.o)]:
            old=r.object_digest(value,kind);value['header']['digest']=b'x'*32;self.assertEqual(old,r.object_digest(value,kind))
            value['header']['id']=value['header']['id'][:-1]+'1';self.assertNotEqual(old,r.object_digest(value,kind))

    def test_intent_order_and_duplicates_are_semantic(self):
        value=self.e['intent'];original=r.object_digest(value,'ReceiptIntent')
        value['input_refs']=[b'input-A',b'input-B',b'input-B'];self.assertNotEqual(original,r.object_digest(value,'ReceiptIntent'))
        value['input_refs']=[b'input-B',b'input-A'];self.assertNotEqual(original,r.object_digest(value,'ReceiptIntent'))

    def test_unknown_intent_fields_and_selector_xor_fail_closed(self):
        for mutate in (lambda v:v.update(comment='display'),lambda v:v.update(selection_policy_ref=v['profile_ref']),lambda v:v.pop('profile_ref')):
            v=copy.deepcopy(self.e['intent']);mutate(v)
            with self.assertRaises(c.CodecError):r.object_digest(v,'ReceiptIntent')

    def test_optional_fields_are_omitted_and_hashed_when_present(self):
        value=self.e['intent'];old=r.object_digest(value,'ReceiptIntent');value['deadline']=0
        self.assertNotEqual(old,r.object_digest(value,'ReceiptIntent'));value['deadline']=None
        with self.assertRaises(c.CodecError):r.object_digest(value,'ReceiptIntent')

    def test_all_frozen_context_and_record_fields_are_hashed(self):
        for kind,original in [('CreationContext',self.e['creation_context']),('PhaseIRecord',self.o)]:
            old=r.object_digest(original,kind)
            for key,value in original.items():
                if key=='header':continue
                changed=copy.deepcopy(original)
                if isinstance(value,bytes):changed[key]=value+b'x'
                elif isinstance(value,list):changed[key]=value+[b'x']
                elif isinstance(value,dict):changed[key]=value|{'digest':b'x'*32}
                elif isinstance(value,int):changed[key]=value+1
                else:changed[key]='REJECTED'
                self.assertNotEqual(old,r.object_digest(changed,kind),key)

    def test_context_registry_and_instant_have_one_owner(self):
        v=self.e['creation_context'];imports=r.references.Imports(self.value['schema_lock'],self.value['schema_documents'],self.lock)
        for field in ('evaluation_instant','registry_snapshot_ref'):
            b=copy.deepcopy(self.e['bundle']);b['context'][field]=0 if field=='evaluation_instant' else dict(id='acl.rs.'+'1'*26,version=[1,0,0],digest=b'x'*32)
            with self.assertRaisesRegex(c.CodecError,'SV-101'):r.check_context(v,b,imports)

    def test_progressive_frontiers_and_transitive_ancestry(self):
        rows=DRIVER['vectors']()
        for name in ('valid-progressive-frontiers-F','transitive-precedence'):
            row=next(x for x in rows if x['id']==name);self.assertTrue(row['valid'])
        self.assertNotEqual(self.e['bundle']['context']['event_frontier_ref'],self.value['envelope']['bundle']['context']['event_frontier_ref'])

    def test_equal_or_disconnected_events_fail(self):
        frontier=self.value['envelope']['bundle']['event_frontier_snapshot']
        with self.assertRaises(c.CodecError):r.check_causal(self.o,b'I-event',frontier)
        row=next(x for x in frontier['event_records'] if x['event_ref']==b'F-event');row['parent_refs']=[]
        with self.assertRaises(c.CodecError):r.check_causal(self.o,b'F-event',frontier)

    def test_forged_self_consistent_record_is_replayed(self):
        self.o.update(outcome='REJECTED',failure_reasons=[b'CONTRACT_MISMATCH']);DRIVER['reseal'](self.value)
        issues=validator.validate_creation_cbor(c.encode(self.value),self.lock,self.contract,phase='F')
        self.assertTrue(issues);self.assertIn('replay',issues[0].message)

    def test_contract_contents_checked_with_digest_pin_record(self):
        out=r.inspect(c.encode(self.value),self.lock,self.contract,phase='F')
        for key in ('full_schema_valid','full_phase_i_replay','source_authentication','production_admission','receipt_created'):self.assertFalse(out[key])
        self.value['test_contract']['contract_tuple']=b'changed'
        with self.assertRaisesRegex(c.CodecError,'SV-102'):r.inspect(c.encode(self.value),self.lock,self.contract,phase='F')

    def test_cli_accepts_optional_pin_records_and_compatibility_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'if.cbor';p.write_bytes(c.encode(self.value));cmd=[sys.executable,'-B','-m','tools.verification_profile.validator',str(p),'--creation-f-cbor']
            self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,0)
            cmd+=['--schema-lock-sha256',self.lock.hex(),'--test-contract-sha256',self.contract.hex()]
            result=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr+result.stdout)
            self.assertEqual(subprocess.run(cmd+['--production'],capture_output=True).returncode,0)

    def test_no_hidden_clock_or_network_in_test_replay(self):
        a=r.replay_fixed_audit_test(self.e,self.value['test_contract']);self.assertEqual(a,r.replay_fixed_audit_test(copy.deepcopy(self.e),copy.deepcopy(self.value['test_contract'])))
        self.e['intent']['contract_tuple']=b'bad';self.assertEqual(r.replay_fixed_audit_test(self.e,self.value['test_contract']),('REJECTED',[b'CONTRACT_MISMATCH']))

if __name__=='__main__':unittest.main()
