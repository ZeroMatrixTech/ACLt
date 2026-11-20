# SPDX-License-Identifier: Apache-2.0
import copy
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT.parents[1]),str(ROOT)]
from independent import execute,validate,CoreReject
from tools.verification_profile import codec as c
from wasm import artifact,Module
ROWS=json.loads((ROOT/'tests/independent-vectors.json').read_text())['vectors']
def case(name):return copy.deepcopy(next(r for r in ROWS if r['id']==name))
def run(row):return execute(bytes.fromhex(row['artifact_hex']),bytes.fromhex(row['input_hex']),row['limits'],row['expected_rir'],row.get('hook',''))
class IndependenceTests(unittest.TestCase):
    def test_frozen_vectors(self):
        for row in ROWS:
            with self.subTest(vector=row['id']):
                actual=run(row);actual.pop('sha_consistency',None)
                self.assertEqual(actual,row['expected'])
    def test_rejection_classes_have_no_task_bytes(self):
        codes=set()
        for row in ROWS:
            r=run(row)
            if r['status']=='REJECTED':
                codes.add(r['code']);self.assertNotIn('outcome_digest',r);self.assertNotIn('canonical_outcome_hex',r)
        self.assertEqual(codes,{'RIR_REJECT_ENCODING','RIR_REJECT_UNSUPPORTED','RIR_REJECT_INVALID','RIR_REJECT_LIMITS'})
    def test_host_failures_are_not_task_traps(self):
        for name in ['local-step-host-fault','memory-fault-injection']:
            r=run(case(name));self.assertEqual(r['status'],'HOST_FAULT');self.assertNotIn('result',r);self.assertNotIn('outcome_digest',r)
    def test_revalidation_digest_check_is_disabled(self):
        row=case('stats');row['expected_rir']='00'*32;result=run(row);self.assertEqual(result['status'],'TASK_OUTCOME');self.assertEqual(result['sha_consistency'],'DISABLED')
    def test_result_hash_uses_raw_output_not_json_hex(self):
        r=run(case('stats'));v=c.decode(bytes.fromhex(r['canonical_outcome_hex']));self.assertIsInstance(v['output'],bytes);self.assertNotIn('output_hex',v);self.assertEqual(c.domain_hash('ACLt/RIR-0/ExecutionOutcome/1',bytes.fromhex(r['canonical_outcome_hex'])).hex(),r['outcome_digest'])
    def test_limits_do_not_change_artifact_digest(self):
        first=run(case('stats'));other=run(case('gas-exact'));self.assertEqual(first['rir_digest'],other['rir_digest']);self.assertEqual(first['outcome_digest'],other['outcome_digest']);self.assertNotEqual(first['rir_digest'],run(case('empty'))['rir_digest'])
    def test_input_count_binding_and_overflow(self):
        for name,code in [('arity-0','RIR_REJECT_INVALID'),('arity-2','RIR_REJECT_INVALID'),('arity-4294967296','RIR_REJECT_LIMITS')]:self.assertEqual(run(case(name))['code'],code)
    def test_gas_boundary_and_partial_output_discard(self):
        self.assertEqual(run(case('gas-exact'))['result']['outcome'],'OK');self.assertEqual(run(case('gas-short'))['result']['outcome'],'TRAP_GAS_EXHAUSTED');v=c.decode(bytes.fromhex(run(case('output-partial-discard'))['canonical_outcome_hex']));self.assertNotIn('output',v)
    def test_type_validator_rejects_unsafe_indices_and_stack(self):
        for name in ['local-index','wrong-type','operand-underflow','branch-depth','memory-alignment']:self.assertEqual(run(case(name))['code'],'RIR_REJECT_INVALID')
    def test_rejection_does_not_mutate_caller_limits(self):
        row=case('gas-below-instantiate');saved=copy.deepcopy(row['limits']);run(row);self.assertEqual(row['limits'],saved)
    def test_integer_edge_traps_are_distinct(self):
        self.assertEqual(run(case('divzero'))['result']['outcome'],'TRAP_INTEGER_DIVIDE_BY_ZERO');self.assertEqual(run(case('divoverflow'))['result']['outcome'],'TRAP_INTEGER_OVERFLOW');self.assertEqual(run(case('remainder-min'))['result']['outcome'],'OK')
    def test_contract_stays_a_restricted_candidate(self):
        d=json.loads((ROOT/'independent-contract.json').read_text());self.assertFalse(d['full_ADR_0006_conformance']);self.assertFalse(d['production_admission']);self.assertEqual(d['scope'],'RIR_STATS_INDEPENDENT_CORE_1');self.assertEqual(d['artifact_digest_tag'],'ACLt/RIR-0/Artifact/1')
if __name__=='__main__':unittest.main()
