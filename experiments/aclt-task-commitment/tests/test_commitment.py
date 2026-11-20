# SPDX-License-Identifier: Apache-2.0
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from cbor_codec import encode,decode,Rejected
from commitment import freeze,load,bind,task_id,execute_probe,view,FIELDS,profile
from probe import fixture,LIMITS

class CommitmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profile();cls.artifact,cls.input=fixture()
        cls.raw,cls.identity=freeze(cls.artifact,[cls.input],bytes(32),bytes(range(16)),LIMITS)
        cls.obj=load(cls.raw)
    def test_hand_cbor_vector(self):
        raw=bytes.fromhex('a261610161624200ff')
        self.assertEqual(encode({'b':b'\0\xff','a':1}),raw);self.assertEqual(decode(raw),{'a':1,'b':b'\0\xff'})
    def test_closed_cbor_types(self):
        for value in [True,-1,1.0,None,'é',{1:2}]:
            with self.assertRaises(Rejected):encode(value)
        for raw in [b'\xf4',b'\xc0\x00',b'\x20',b'\x9f\xff',b'\x61\xff']:
            with self.assertRaises(Rejected):decode(raw)
    def test_nonminimal_duplicate_and_order(self):
        for raw in [bytes.fromhex('1801'),bytes.fromhex('a2616101616102'),bytes.fromhex('a2616201616102')]:
            with self.assertRaises(Rejected):decode(raw)
    def test_all_truncated_prefixes_rejected(self):
        for length in range(len(self.raw)):
            with self.assertRaises(Rejected):load(self.raw[:length])
    def test_golden_identity_and_view_schema(self):
        golden=json.loads((HERE/'tests/golden.json').read_text())
        self.assertEqual(self.raw.hex(),golden['commitment_hex']);self.assertEqual(self.identity,golden['experimental_task_id'])
        schema=json.loads((HERE/'schema.json').read_text());self.assertEqual(set(schema['required']),FIELDS);self.assertFalse(schema['additionalProperties'])
        self.assertEqual(view(self.obj)['rir_digest'],golden['rir_digest'])
    def test_map_order_does_not_change_identity(self):
        raw,identity=freeze(self.artifact,[self.input],bytes(32),bytes(range(16)),dict(reversed(list(LIMITS.items()))))
        self.assertEqual((raw,identity),(self.raw,self.identity))
    def test_input_changes_task_not_rir_identity(self):
        other,identity=freeze(self.artifact,[self.input[:-1]+b'1'],bytes(32),bytes(range(16)),LIMITS)
        self.assertNotEqual(identity,self.identity);self.assertEqual(load(other)['rir_digest'],self.obj['rir_digest'])
    def test_all_execution_limits_bound_to_identity(self):
        for key,value in [('gas_limit',9125),('output_limit',95),('call_depth_limit',1)]:
            other,identity=freeze(self.artifact,[self.input],bytes(32),bytes(range(16)),{**LIMITS,key:value})
            self.assertNotEqual(identity,self.identity);self.assertEqual(load(other)['rir_digest'],self.obj['rir_digest'])
        # Fixed-memory profile supports exactly two pages; a different limit is rejected.
        with self.assertRaises(Rejected):freeze(self.artifact,[self.input],bytes(32),bytes(range(16)),{**LIMITS,'memory_pages_limit':1})
    def test_nonce_and_requester_bind_identity_without_authentication_claim(self):
        for owner,nonce in [(bytes([1])*32,bytes(range(16))),(bytes(32),bytes(16))]:
            _,identity=freeze(self.artifact,[self.input],owner,nonce,LIMITS);self.assertNotEqual(identity,self.identity)
    def test_caller_mutation_does_not_change_frozen_bytes(self):
        limits=dict(LIMITS);inputs=[self.input];raw,identity=freeze(self.artifact,inputs,bytes(32),bytes(range(16)),limits)
        limits['gas_limit']=1;inputs[0]=b'changed';self.assertEqual((raw,identity),(self.raw,self.identity))
    def test_wrong_binding_rejected_before_execute(self):
        with patch('rir_adapter.execute',side_effect=AssertionError('execution must not start')):
            for identity,artifact,inputs in [(self.identity,self.artifact+b'0',[self.input]),(self.identity,self.artifact,[b'wrong']),(self.identity,self.artifact,[])]:
                with self.assertRaises(Rejected):execute_probe(self.raw,identity,artifact,inputs)
    def test_task_digest_comparison_is_disabled(self):
        other,identity=freeze(self.artifact,[self.input],bytes(32),bytes(16),LIMITS)
        self.assertEqual(task_id(other),identity)
        self.assertEqual(bind(other,self.identity,self.artifact,[self.input])[1], (self.input,))
    def test_unknown_or_missing_fields_and_wrong_types(self):
        for key,value in [('ReceiptID','x'),('schema_version',True),('rir_version',[False,1,0]),('nonce','00'*16),('requester_ref',bytes(31))]:
            obj=copy.deepcopy(self.obj);obj[key]=value
            with self.assertRaises(Rejected):load(encode(obj))
        obj=copy.deepcopy(self.obj);obj.pop('context_id')
        with self.assertRaises(Rejected):load(encode(obj))
    def test_profile_and_equivalence_fail_closed(self):
        for key,value in [('execution_profile_id','unknown'),('result_equivalence','unknown'),('rir_version',[1,0,0])]:
            obj=copy.deepcopy(self.obj);obj[key]=value
            with self.assertRaises(Rejected):load(encode(obj))
    def test_limit_boundaries(self):
        for key,value in [('gas_limit',8191),('gas_limit',50000001),('gas_limit',True),('output_limit',4800001),('output_limit',-1),('call_depth_limit',0),('call_depth_limit',65)]:
            obj=copy.deepcopy(self.obj);obj['execution_limits'][key]=value
            with self.assertRaises(Rejected):load(encode(obj))
    def test_input_reference_length_and_arity(self):
        for refs in [[],self.obj['inputs']*2,[{**self.obj['inputs'][0],'object_digest':bytes(31)}],[{**self.obj['inputs'][0],'byte_length':True}]]:
            obj=copy.deepcopy(self.obj);obj['inputs']=refs
            with self.assertRaises(Rejected):load(encode(obj))
    def test_bound_execution_and_traps(self):
        r=execute_probe(self.raw,self.identity,self.artifact,[self.input]);self.assertEqual(r['result']['gas_used'],9126)
        self.assertEqual(r['result']['outcome'],'OK');self.assertIn('without-authorization',r['execution_mode'])
        for limit,expected in [({'gas_limit':9125},'TRAP_GAS_EXHAUSTED'),({'output_limit':95},'TRAP_OUTPUT_LIMIT')]:
            raw,identity=freeze(self.artifact,[self.input],bytes(32),bytes(range(16)),{**LIMITS,**limit})
            r=execute_probe(raw,identity,self.artifact,[self.input]);self.assertEqual(r['result']['outcome'],expected);self.assertNotIn('output_hex',r['result'])
    def test_cli_refuses_override_and_preserves_report(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'artifact').write_bytes(self.artifact);(p/'input').write_bytes(self.input);(p/'commitment').write_bytes(self.raw)
            argv=[sys.executable,'-B',str(HERE/'cli.py'),'execute-probe','--artifact',str(p/'artifact'),'--input',str(p/'input'),'--commitment',str(p/'commitment'),'--task-id',self.identity,'--report',str(p/'result')]
            r=subprocess.run(argv,capture_output=True);self.assertEqual(r.returncode,0);before=(p/'result').read_bytes()
            self.assertEqual(subprocess.run(argv,capture_output=True).returncode,2);self.assertEqual((p/'result').read_bytes(),before)
            (p/'result').unlink();self.assertEqual(subprocess.run(argv+['--gas-limit','1'],capture_output=True).returncode,2);self.assertFalse((p/'result').exists())
    def test_host_failure_is_not_task_outcome(self):
        with patch('rir_adapter.execute',side_effect=MemoryError('local failure')):
            with self.assertRaises(MemoryError):execute_probe(self.raw,self.identity,self.artifact,[self.input])

if __name__=='__main__':unittest.main()
