# SPDX-License-Identifier: Apache-2.0
import json
import subprocess
import tempfile
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from wasm import Module,Reject,normalize,artifact,cbor,decode_artifact,Reader,decode_seq,encode_seq
from runtime import Host,Trap,HostFault,Runner,load_candidate
from cases import run
RAW=bytes.fromhex(json.loads((ROOT/'tests/fixture.json').read_text())['raw_hex'])
NORMAL=normalize(RAW)[0]

class IOTests(unittest.TestCase):
    def test_canonical_calls_and_roundtrip(self):
        self.assertLess(len(NORMAL),len(RAW))
        self.assertEqual(normalize(NORMAL)[0],NORMAL)
        self.assertEqual(decode_artifact(artifact(NORMAL)).canonical(),NORMAL)
        self.assertEqual({n for n,_ in Module(NORMAL).imports},{'input_count','input_len','input_read','output_write','abort'})
    def test_fixture_suite(self):
        result=run(NORMAL)
        self.assertEqual(result['count'],55)
        self.assertEqual(result['status'],'PASS')
    def test_direct_abi_priority_vectors(self):
        for args,gas,code,used in [([65536,1],17,'TRAP_HOST_ARGUMENT',17),([65536,1],16,'TRAP_GAS_EXHAUSTED',0),([0,1],17,'TRAP_OUTPUT_LIMIT',17),([65537,0],16,'TRAP_HOST_ARGUMENT',16),([2**32-1,1],17,'TRAP_HOST_ARGUMENT',17)]:
            with self.subTest(args=args,gas=gas):
                host=Host([b'x'],65536,gas,0)
                with self.assertRaises(Trap) as caught:host.call('output_write',args)
                self.assertEqual(caught.exception.code,code);self.assertEqual(host.gas_used,used);self.assertEqual(host.output,b'')
        host=Host([b'x'],65536,16,0);host.call('output_write',[65536,0]);self.assertEqual(host.output,b'')
    def test_input_read_is_atomic_and_does_not_wrap(self):
        for args in [[0,2**64-1,0,1],[1,0,0,0],[0,0,65536,1]]:
            host=Host([b'x'],65536,100,16);before=bytes(host.memory)
            with self.assertRaises(Trap) as caught:host.call('input_read',args)
            self.assertEqual(caught.exception.code,'TRAP_HOST_ARGUMENT');self.assertEqual(bytes(host.memory),before)
    def test_observable_copy_and_output(self):
        data=bytes(range(16));runner=load_candidate(artifact(NORMAL),[data]);result=runner.run()
        self.assertEqual(result['output_hex'],data.hex());self.assertEqual(result['gas_used'],8271)
        self.assertEqual([x['name'] for x in runner.host.trace],['input_count','input_len','input_read','output_write'])
    def test_missing_binding_and_override_rejected(self):
        with self.assertRaises(Reject):load_candidate(artifact(NORMAL),[])
        with self.assertRaises(Reject):load_candidate(artifact(NORMAL),[bytes(16)],input_arity=None)
    def test_outer_fields_and_trailing_bytes_rejected(self):
        obj={'schema_version':1,'encoding_profile_id':'acl.enc.rir-0@1','rir_version':[0,1,0],'entry':'run','input_arity':1,'body':NORMAL}
        for key,value in [('input_arity',2),('entry','other'),('schema_version',2)]:
            other={**obj,key:value}
            with self.assertRaises(Reject):decode_artifact(cbor(other))
        with self.assertRaises(Reject):decode_artifact(artifact(NORMAL)+b'\x00')
    def test_noncanonical_wasm_not_executed(self):
        with self.assertRaises(Reject):decode_artifact(artifact(RAW))
        with self.assertRaises(Reject):Runner(Module(RAW),[bytes(16)])
    def test_unsupported_import_and_opcode_rejected(self):
        with self.assertRaises(Reject):normalize(RAW.replace(b'aclt',b'evil',1))
        m=Module(NORMAL);m.code[0][1].insert(0,{'op':0xc0,'args':[]})
        with self.assertRaises(Reject):Module(m.canonical())
    def test_bad_local_and_immutable_global_rejected(self):
        for node in [{'op':0x20,'args':[4096]},{'op':0x24,'args':[1]}]:
            m=Module(NORMAL);m.code[0][1].insert(0,node)
            with self.assertRaises(Reject):Module(m.canonical())
    def test_wasm_oob_is_task_trap(self):
        m=Module(NORMAL);m.globals[0]=(0x7f,1,0)
        runner=load_candidate(artifact(m.canonical()),[bytes(16)]);r=runner.run()
        self.assertEqual(r['outcome'],'TRAP_MEMORY_OOB');self.assertNotIn('output_hex',r)
    def test_host_fault_is_not_task_outcome(self):
        runner=load_candidate(artifact(NORMAL),[bytes(16)],max_steps=1)
        with self.assertRaises(HostFault):runner.run()
    def test_empty_else_canonicalization(self):
        tree,end=decode_seq(Reader(b'\x04\x40\x05\x0b\x0b'))
        self.assertEqual(end,0x0b);self.assertEqual(encode_seq(tree),b'\x04\x40\x0b')
    def test_input_read_gas_precedes_parameter_error(self):
        host=Host([],65536,15,16)
        with self.assertRaises(Trap) as caught:host.call('input_read',[99,0,65536,0])
        self.assertEqual(caught.exception.code,'TRAP_GAS_EXHAUSTED');self.assertEqual(host.gas_used,0)
    def test_non_ok_discards_already_written_output(self):
        runner=load_candidate(artifact(NORMAL),[bytes(range(16))],gas_limit=8270)
        result=runner.run()
        self.assertEqual(len(runner.host.output),16);self.assertEqual(result['outcome'],'TRAP_GAS_EXHAUSTED');self.assertNotIn('output_hex',result)
    def test_malformed_typed_host_values_are_internal_fault(self):
        host=Host([b'x'],65536,100,16)
        with self.assertRaises(HostFault):host.call('output_write',[-1,1])
    def test_truncated_envelope_rejected(self):
        data=artifact(NORMAL)
        for i in range(len(data)):
            with self.subTest(prefix=i),self.assertRaises(Reject):decode_artifact(data[:i])

    def test_python_stack_exhaustion_is_host_fault(self):
        m=Module(NORMAL);m.code[0]=(m.code[0][0],[{'op':0x10,'args':[m.run]}])
        runner=load_candidate(artifact(m.canonical()),[bytes(16)],gas_limit=1000000,call_depth_limit=4096)
        with self.assertRaises(HostFault):runner.run()

    def test_cli_status_and_report_preservation(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t);blob=path/'artifact.cbor';blob.write_bytes(artifact(NORMAL))
            src=path/'input.bin';src.write_bytes(bytes(range(16)));report=path/'report.json'
            command=[sys.executable,'-B',str(ROOT/'execute.py'),'--artifact',str(blob),'--input',str(src),'--report',str(report)]
            p=subprocess.run(command,capture_output=True)
            self.assertEqual(p.returncode,0);before=report.read_bytes()
            self.assertEqual(json.loads(before)['status'],'TASK_OUTCOME')
            self.assertNotEqual(subprocess.run(command,capture_output=True).returncode,0)
            self.assertEqual(report.read_bytes(),before)
            rejected=path/'rejected.json'
            p=subprocess.run([sys.executable,'-B',str(ROOT/'execute.py'),'--artifact',str(blob),'--report',str(rejected)],capture_output=True)
            self.assertEqual(p.returncode,2);self.assertEqual(json.loads(rejected.read_text())['status'],'REJECTED')

if __name__=='__main__':unittest.main()
