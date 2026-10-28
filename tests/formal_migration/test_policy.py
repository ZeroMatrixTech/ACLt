# SPDX-License-Identifier: Apache-2.0
import copy
import hashlib
import json
from pathlib import Path
import unittest
from tools.formal_migration import policy as p
from tools.formal_migration import foundation as f
from tools.verification_profile import codec as c
ROOT=Path(__file__).resolve().parents[2]
ROWS=json.loads((ROOT/'tests/formal_migration/policy-vectors.json').read_text())['vectors']
def native(name):return c.decode(bytes.fromhex(next(r['cbor_hex'] for r in ROWS if r['id']==name)))
def rebind(b):
    r=b['receipt'];r['funding_ref']=p.ref('FUNDING',b['funding']);r['settlement_ref']=p.ref('SETTLEMENT',b['settlement']);r['input_refs']=[p.ref('LOGICAL',x) for x in b['inputs']];r['component_refs']=[p.ref(x['kind'],x) for x in b['components']];return b
class PolicyTests(unittest.TestCase):
    def test_frozen_raw_bytes_views_and_hashes(self):
        for row in ROWS:
            with self.subTest(row=row['id']):
                raw=bytes.fromhex(row['cbor_hex'])
                if row['valid']:self.assertEqual(p.inspect(row['kind'],raw),row['expected'])
                else:self.assertRaises(c.CodecError,p.inspect,row['kind'],raw)
    def test_all_cells_are_conservative_and_do_not_mutate_input(self):
        b=native('bundle');before=copy.deepcopy(b);self.assertEqual(len(p.matrix_keys()),111)
        for cell in p.matrix_keys():
            q=dict(bundle=b,**dict(zip(('terminal','executor','auditor','storage'),cell)));result=p.quote(q);paid=sum(int(x) for x in result['amounts'].values());self.assertEqual(paid+int(result['refund']),17);self.assertGreaterEqual(int(result['refund']),2);self.assertEqual(result['scope'],'HYPOTHETICAL_ONLY_NO_ENTITLEMENT')
            for status,fee,limit in zip(cell[1:],('execution_fee','verification_fee','storage_fee'),(7,5,3)):self.assertEqual(int(result['amounts'][fee]),limit if status=='COMPLETE' else 0)
        self.assertEqual(b,before)
    def test_matrix_completeness_order_and_nonfulfillment(self):
        b=native('bundle')
        for edit in [lambda x:x['rows'].pop(),lambda x:x['rows'].reverse(),lambda x:x['rows'].__setitem__(1,x['rows'][0]),lambda x:next(r for r in x['rows'] if r['executor']=='HOST_FAULT').update(execution_fee=1)]:
            v=copy.deepcopy(b);edit(v['settlement']);rebind(v);self.assertRaises(c.CodecError,p.bundle,v)
    def test_budget_sums_overflow_and_bucket_limits(self):
        for edit in [lambda b:b['funding'].update(total_limit=16),lambda b:b['funding'].update(refund_reserve=2**64-1),lambda b:next(r for r in b['settlement']['rows'] if r['executor']=='COMPLETE').update(execution_fee=8)]:
            b=native('bundle');edit(b);rebind(b);self.assertRaises(c.CodecError,p.bundle,b)
    def test_scope_context_and_unavailable_components(self):
        for edit in [lambda b:b['funding']['scope'].update(nonce=b'z'*32),lambda b:b['settlement'].update(network_id=b'z'*32),lambda b:b.update(inputs=[]),lambda b:b['components'].pop(),lambda b:b['components'][0].update(version=[2,0,0])]:
            b=native('bundle');edit(b);rebind(b);self.assertRaises(c.CodecError,p.bundle,b)
    def test_closed_reference_dag_rejects_receipt_backedges(self):
        for edit in [lambda b:b['funding'].update(receipt_ref=p.ref('RECEIPT',b['receipt'])),lambda b:b['funding']['scope'].update(receipt_id=b'\0'*32),lambda b:b['inputs'][0].update(parents=[p.ref('RECEIPT',b['receipt'])])]:
            b=native('bundle');edit(b);rebind(b);self.assertRaises(c.CodecError,p.bundle,b)
    def test_immutable_input_schema_and_availability(self):
        for edit in [lambda b:b['inputs'][0].update(content=c.encode([2**31])),lambda b:b['inputs'][0].update(available_until=4999),lambda b:b['receipt']['execution'].update(input_bytes_limit=1)]:
            b=native('bundle');edit(b);rebind(b);self.assertRaises(c.CodecError,p.bundle,b)
    def test_policy_changes_require_new_commitment_without_changing_rir(self):
        b=native('bundle');old=p.bundle(b);rir=b['receipt']['component_refs'][0]
        for name,edit in [('funding',lambda b:b['funding'].update(refund_reserve=3,total_limit=18)),('settlement',lambda b:next(r for r in b['settlement']['rows'] if r['executor']=='COMPLETE').update(execution_fee=6)),('input',lambda b:b['inputs'][0].update(content=c.encode([1,2,3]))),('resource',lambda b:b['receipt']['execution'].update(fuel=10001))]:
            v=copy.deepcopy(b);edit(v)
            if name!='resource':self.assertRaises(c.CodecError,p.bundle,v)
            rebind(v);self.assertNotEqual(old,p.bundle(v));self.assertEqual(rir,v['receipt']['component_refs'][0])
    def test_all_execution_component_refs_are_bound(self):
        b=native('bundle');old=p.bundle(b)
        for i in range(len(p.COMPONENTS)):
            v=copy.deepcopy(b);v['components'][i]['content']=b'changed';self.assertRaises(c.CodecError,p.bundle,v);rebind(v);self.assertNotEqual(old,p.bundle(v))
    def test_receipt_signatures_require_caller_pins_and_finite_validity(self):
        v=native('signed-receipt');self.assertTrue(p.verify(v)['valid'])
        for field,val in [('expected_receipt',b'z'*32),('expected_requester',b'z'*32),('signature',b'\0'*256),('now',5000),('now',3000.5)]:
            changed=copy.deepcopy(v);changed[field]=val;self.assertRaises(c.CodecError,p.verify,changed)
        tag=bytes([len(p.SIGN_TAG)])+p.SIGN_TAG.encode();self.assertEqual(p.signing_input(v['bundle']),tag+c.encode(v['bundle']['receipt']))
    def test_prestart_has_no_fulfillment_and_never_trusted(self):
        b=native('bundle')
        for terminal in p.PRESTART_TERMINALS:
            q=dict(bundle=b,terminal=terminal,executor='MISSING',auditor='MISSING',storage='MISSING');self.assertEqual(p.quote(q)['refund'],'17');q['executor']='COMPLETE';self.assertRaises(c.CodecError,p.quote,q)
        self.assertRaises(c.CodecError,p.quote,dict(bundle=b,terminal='TRUSTED',executor='COMPLETE',auditor='COMPLETE',storage='COMPLETE'))
    def test_candidate_schema_and_typed_view_contract(self):
        d=json.loads((ROOT/'schemas/formal-migration/policy.json').read_text());self.assertEqual(d['types'],p.SCHEMAS);self.assertEqual(d['domain_tags'],p.TAGS);self.assertEqual(d['matrix']['cells'],111);self.assertFalse(d['protocol_admission'])
        for row in ROWS:
            if row['valid'] and row['kind']!='fm2-verify':self.assertEqual(p.from_view_json(row['kind'],json.dumps(row['expected']['schema_view'])).hex(),row['cbor_hex'])
        for source in ['null','NaN','{"scope":"a","scope":"b"}']:self.assertRaises(c.CodecError,p.from_view_json,'fm2-receipt',source)
if __name__=='__main__':unittest.main()
