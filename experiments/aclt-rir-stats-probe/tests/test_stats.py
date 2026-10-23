# SPDX-License-Identifier: Apache-2.0
import json
import struct
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from wasm import Module,Reject,artifact,normalize,decode_artifact
from runtime import Runner,load_candidate,HostFault,Trap,integer,Host
from cases import encode,rows,binary_rows,decode_output,text_rows,outcome_digest,LIMITS
RAW=bytes.fromhex(json.loads((ROOT/'tests/fixture.json').read_text())['raw_hex'])
BODY=normalize(RAW)[0]

class StatsTests(unittest.TestCase):
    def run_stats(self,values,chunk,**limits):return load_candidate(artifact(BODY),[encode(chunk,values)],**{**LIMITS,**limits}).run()
    def test_wire_golden(self):
        self.assertEqual(encode(1,[-1]),bytes.fromhex('01000000000000000100000000000000ffffffffffffffff'))
        self.assertEqual(rows([3,-1,5,8],2),[(0,0,2,2,-1,3),(1,2,2,13,5,8)])
        self.assertEqual(text_rows(rows([3,-1,5,8],2)),b'0 0 2 2 -1 3\n1 2 2 13 5 8\n')
    def test_stats_signed_and_partial(self):
        for values,chunk in [([-10**9,10**9,-1,7,0],2),([0],100000),([10**9]*100,100),([-10**9]*100,100)]:
            r=self.run_stats(values,chunk);self.assertEqual(r['outcome'],'OK');self.assertEqual(decode_output(bytes.fromhex(r['output_hex'])),rows(values,chunk))
    def test_abort_validation(self):
        for v,c,code in [([],1,4),([3],0,3),([3],100001,3),([2**63-1],1,5),([-2**63],1,5),([1,2,10**9+1],1,5)]:
            r=self.run_stats(v,c);self.assertEqual((r['outcome'],r['abort_code']),('ABORT',code));self.assertNotIn('output_hex',r)
    def test_size_arithmetic_is_bounded_before_read(self):
        for b in [b'',encode(1,[0])+b'x',struct.pack('<QQ',1,2**64-1)]:
            r=load_candidate(artifact(BODY),[b],**LIMITS).run();self.assertEqual(r['outcome'],'ABORT')
    def test_partial_output_discard(self):
        runner=load_candidate(artifact(BODY),[encode(1,[1,2])],**{**LIMITS,'output_limit':49})
        r=runner.run();self.assertEqual(r['outcome'],'TRAP_OUTPUT_LIMIT');self.assertEqual(len(runner.host.output),48);self.assertNotIn('output_hex',r)
    def test_gas_exact_and_short(self):
        a=self.run_stats([3,-1,5,8],2);self.assertEqual(a['gas_used'],9126)
        self.assertEqual(self.run_stats([3,-1,5,8],2,gas_limit=9126),a)
        self.assertEqual(self.run_stats([3,-1,5,8],2,gas_limit=9125)['outcome'],'TRAP_GAS_EXHAUSTED')
    def test_fault_not_outcome(self):
        with self.assertRaises(HostFault):self.run_stats([0],1,max_steps=1)
    def test_candidate_binding_and_encoding(self):
        self.assertEqual(normalize(BODY)[0],BODY)
        for blob in [artifact(BODY)+b'0',artifact(RAW)]:
            with self.assertRaises(Reject):decode_artifact(blob)
        with self.assertRaises(Reject):load_candidate(artifact(BODY),[])
        with self.assertRaises(Reject):load_candidate(artifact(BODY),[encode(1,[0])],input_arity=None)
    def test_integer_signed_comparison_and_wrapping(self):
        self.assertEqual(integer(0x53,2**64-1,0),1)
        self.assertEqual(integer(0x54,2**64-1,0),0)
        self.assertEqual(integer(0x6a,2**32-1,1),0)
        self.assertEqual(integer(0x7e,2**64-1,2),2**64-2)
        self.assertEqual(integer(0x86,1,64),1)
        self.assertEqual(integer(0x87,2**64-1,63),2**64-1)
    def test_integer_division_traps_and_remainder(self):
        for op,left,right,code in [(0x7f,1,0,'TRAP_INTEGER_DIVIDE_BY_ZERO'),(0x7f,2**63,2**64-1,'TRAP_INTEGER_OVERFLOW')]:
            with self.assertRaises(Trap) as e:integer(op,left,right)
            self.assertEqual(e.exception.code,code)
        self.assertEqual(integer(0x81,2**63,2**64-1),0)
        self.assertEqual(integer(0x7f,2**64-7,3),2**64-2)
    def test_host_argument_math_and_gas_priority(self):
        for args,gas,code in [([0,2**64-1,0,1],17,'TRAP_HOST_ARGUMENT'),([0,2**64-1,0,1],16,'TRAP_GAS_EXHAUSTED')]:
            host=Host([b'x'],131072,gas,48)
            with self.assertRaises(Trap) as e:host.call('input_read',args)
            self.assertEqual(e.exception.code,code);self.assertEqual(host.memory,bytes(131072))
    def test_parser_rejects_unknown_op_and_bad_types(self):
        for node in [{'op':0xc0,'args':[]},{'op':0x20,'args':[4096]},{'op':0x42,'args':[1]},{'op':0x54,'args':[]}]:
            m=Module(BODY);m.code[0]=([], [node])
            with self.assertRaises(Reject):Module(m.canonical())
    def test_outcome_digest_includes_exact_output(self):
        r=self.run_stats([0],1);self.assertEqual(outcome_digest(r),r['outcome_digest'])
        other={**r,'output_hex':'01'+r['output_hex'][2:]};self.assertNotEqual(outcome_digest(other),r['outcome_digest'])
    def test_malformed_rows(self):
        with self.assertRaises(ValueError):decode_output(bytes(47))

if __name__=='__main__':unittest.main()
