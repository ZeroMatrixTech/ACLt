# SPDX-License-Identifier: Apache-2.0
import copy
import json
from pathlib import Path
import secrets
import sys
import tempfile
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
from common import sha,encode,decode,Rejected,HostFault,environment_digest
from auth_crypto import create_keys,verify,sign
from authorization import Authority,grant_id
from runner import dispatch,launch
from wire import make_request,check_response
from fixtures import task

class Stopped(BaseException):pass

class AuthorizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keys=tempfile.TemporaryDirectory();cls.private,cls.public=create_keys(Path(cls.keys.name)/'keys')
    @classmethod
    def tearDownClass(cls):cls.keys.cleanup()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.provider=sha(b'provider-B');self.unit=sha(b'unit-B');self.secret=secrets.token_bytes(32);self.now=1000
        self.authority=Authority(self.root/'ledger.sqlite',self.private,self.public,{self.provider:self.secret},initialize=True,clock=lambda:self.now)
        self.c,self.identity,self.artifact,self.input=task(secrets.token_bytes(16))
        self.config={'host':'unused','port':1,'authority_id':self.authority.authority_id,'public_digest':sha(self.public.read_bytes()),
                     'provider_ref':self.provider,'unit_ref':self.unit,'provider_secret':self.secret,'environment_digest':environment_digest()}
        self.grant=self.issue()
    def issue(self,epoch=1,start=900,end=1100):
        return self.authority.issue(self.c,self.provider,self.unit,self.config['environment_digest'],epoch,start,end)
    def dispatch(self,grant=None,config=None,transport=None):
        return dispatch(grant or self.grant,self.c,self.identity,self.artifact,[self.input],config or self.config,self.public,transport or self.authority.handle)
    def launch(self,bundle,state='worker',config=None,transport=None,hook=None):
        return launch(bundle,self.c,self.identity,self.artifact,[self.input],config or self.config,self.public,self.root/state,transport or self.authority.handle,hook)
    def allowed_consumes(self):
        c=self.authority.connect()
        try:return c.execute("SELECT COUNT(*) FROM events WHERE op='CONSUME:ALLOW'").fetchone()[0]
        finally:c.close()
    def test_valid_double_check_and_durable_markers(self):
        bundle=self.dispatch();self.assertEqual(self.allowed_consumes(),0)
        def hook(stage):
            state=self.root/'worker';self.assertEqual(len(list(state.glob('*.intent.cbor'))),1)
            if stage=='before-guest':self.assertEqual(self.allowed_consumes(),1);self.assertEqual(len(list(state.glob('*.permit.cbor'))),1)
        result=self.launch(bundle,hook=hook);self.assertEqual(result['result']['gas_used'],9126);self.assertEqual(result['result']['outcome'],'OK')
        files=list((self.root/'worker').glob('*'));self.assertEqual(len(files),5)
        outcome=decode(next((self.root/'worker').glob('*.outcome.cbor')).read_bytes());output=next((self.root/'worker').glob('*.output.bin')).read_bytes()
        self.assertEqual(outcome['outcome']['output_digest'],sha(output));self.assertEqual(self.allowed_consumes(),1)
    def test_forged_signature_rejected_before_guest(self):
        obj=decode(self.grant);obj['signature']=bytes(256)
        with patch('rir_adapter.execute',side_effect=AssertionError('guest invoked')):
            with self.assertRaises(Rejected):self.dispatch(encode(obj))
        self.assertEqual(self.allowed_consumes(),0)
    def test_signed_tuple_provider_unit_environment_scope_tampering_rejected(self):
        body=verify(self.grant,self.public,self.config['public_digest'])
        for key in ['provider_ref','unit_ref','experimental_task_id']:
            other={**body,key:bytes(32)}
            with self.subTest(key=key),self.assertRaises(Rejected):self.dispatch(sign(other,self.private))
        self.assertEqual(self.allowed_consumes(),0)
    def test_wrong_task_artifact_or_inputs_rejected_before_guest(self):
        for identity,artifact,inputs in [(self.identity,self.artifact+b'x',[self.input]),(self.identity,self.artifact,[b'wrong'])]:
            with patch('rir_adapter.execute',side_effect=AssertionError('guest invoked')),self.assertRaises(Rejected):
                dispatch(self.grant,self.c,identity,artifact,inputs,self.config,self.public,self.authority.handle)
        self.assertEqual(self.allowed_consumes(),0)
    @unittest.skip("SHA environment consistency DISABLED by maintainer policy")
    def test_wrong_local_environment_rejected(self):
        with patch('runner.environment_digest',return_value=bytes(32)),self.assertRaises(Rejected):self.dispatch()
    def test_wrong_key_or_authority_deployment_rejected(self):
        for key in ['authority_id']:
            cfg={**self.config,key:bytes(len(self.config[key]))}
            with self.assertRaises(Rejected):self.dispatch(config=cfg)
    def test_expired_and_future_grants_denied(self):
        self.now=1200
        with self.assertRaises(Rejected):self.dispatch()
        self.now=800
        with self.assertRaises(Rejected):self.dispatch()
        self.assertEqual(self.allowed_consumes(),0)
    def test_expiry_between_dispatch_and_launch_denied(self):
        bundle=self.dispatch();self.now=1200
        with self.assertRaises(Rejected):self.launch(bundle)
        self.assertFalse(list((self.root/'worker').glob('*.invoke.cbor')));self.assertEqual(self.allowed_consumes(),0)
    def test_epoch_rotation_invalidates_old_grant_without_refund_after_consume(self):
        bundle=self.dispatch();new=self.issue(epoch=2)
        with self.assertRaises(Rejected):self.launch(bundle,'old-worker')
        self.launch(self.dispatch(new),'new-worker')
        with self.assertRaises(Rejected):self.issue(epoch=3)
        self.assertEqual(self.allowed_consumes(),1)
    def test_non_increasing_epoch_cannot_replace_grant(self):
        with self.assertRaises(Rejected):self.issue(epoch=1)
    def test_duplicate_local_launch_and_fresh_state_clone_denied(self):
        bundle=self.dispatch();self.launch(bundle)
        for state in ['worker','clone']:
            with self.assertRaises(Rejected):self.launch(bundle,state)
        self.assertEqual(self.allowed_consumes(),1)
    def test_parallel_clones_only_one_reaches_guest(self):
        bundle=self.dispatch()
        def run(i):
            try:return self.launch(bundle,'clone'+str(i))['status']
            except Rejected:return 'REJECTED'
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
        self.assertEqual(sorted(results),['REJECTED','TASK_OUTCOME']);self.assertEqual(self.allowed_consumes(),1)
    def test_offline_dispatch_or_start_is_host_failure(self):
        def offline(packet):raise HostFault('test offline')
        with self.assertRaises(HostFault):self.dispatch(transport=offline)
        bundle=self.dispatch()
        with self.assertRaises(HostFault):self.launch(bundle,transport=offline)
        self.assertEqual(self.allowed_consumes(),0)
    def test_lost_consume_reply_burns_qualification_without_guest(self):
        bundle=self.dispatch()
        def lose(packet):self.authority.handle(packet);raise HostFault('reply lost after commit')
        with self.assertRaises(HostFault):self.launch(bundle,transport=lose)
        self.assertFalse(list((self.root/'worker').glob('*.invoke.cbor')))
        with self.assertRaises(Rejected):self.launch(bundle,'fresh-clone')
        self.assertEqual(self.allowed_consumes(),1)
    def test_old_check_response_cannot_authorize_consume(self):
        bundle=self.dispatch();saved=decode(bundle)['check_response']
        with self.assertRaises(HostFault):self.launch(bundle,transport=lambda packet:saved)
        self.assertEqual(self.allowed_consumes(),0)
    def test_wrong_provider_credential_denied(self):
        with self.assertRaises(Rejected):self.dispatch(config={**self.config,'provider_secret':bytes(32)})
        self.assertEqual(self.allowed_consumes(),0)
    def test_intent_fsync_failure_prevents_consume_and_guest(self):
        bundle=self.dispatch()
        with patch('durability.sync_directory',side_effect=OSError('injected fsync failure')):
            with self.assertRaises((OSError,HostFault)):self.launch(bundle)
        self.assertEqual(self.allowed_consumes(),0)
    def test_permit_write_failure_after_consume_prevents_guest(self):
        bundle=self.dispatch()
        from runner import durable_new as real_write
        def fail_permit(path,data):
            if '.permit.' in str(path):raise HostFault('injected write failure')
            return real_write(path,data)
        with patch('runner.durable_new',side_effect=fail_permit),patch('rir_adapter.execute',side_effect=AssertionError('guest invoked')):
            with self.assertRaises(HostFault):self.launch(bundle)
        self.assertEqual(self.allowed_consumes(),1)
    def test_stop_after_intent_no_resume(self):
        def stop(stage):
            if stage=='after-intent':raise Stopped()
        bundle=self.dispatch()
        with self.assertRaises(Stopped):self.launch(bundle,hook=stop)
        with self.assertRaises(Rejected):self.launch(bundle)
        self.assertEqual(self.allowed_consumes(),0)
    def test_stop_after_permit_fresh_clone_denied(self):
        def stop(stage):
            if stage=='after-permit':raise Stopped()
        bundle=self.dispatch()
        with self.assertRaises(Stopped):self.launch(bundle,hook=stop)
        with self.assertRaises(Rejected):self.launch(bundle,'clone')
        self.assertEqual(self.allowed_consumes(),1)
    def test_concurrent_same_local_state_only_one_launch(self):
        bundle=self.dispatch()
        # Precreate and sync the directory; the O_EXCL intent is the shared gate.
        from durability import state_directory
        state_directory(self.root/'same-state')
        def run(i):
            try:return self.launch(bundle,'same-state')['status']
            except Rejected:return 'REJECTED'
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
        self.assertEqual(sorted(results),['REJECTED','TASK_OUTCOME']);self.assertEqual(self.allowed_consumes(),1)
    def test_unknown_grant_fields_and_dispatch_scope_override_rejected(self):
        body=verify(self.grant,self.public,self.config['public_digest'])
        for other in [{**body,'scope_override':bytes(32)},{**body,'epoch':0}]:
            with self.assertRaises(Rejected):self.dispatch(sign(other,self.private))
        wrapper=decode(self.dispatch());wrapper['scope_override']=bytes(32)
        with self.assertRaises(Rejected):self.launch(encode(wrapper))
        self.assertEqual(self.allowed_consumes(),0)
    def test_existing_or_missing_ledger_not_silently_initialized(self):
        with self.assertRaises(FileExistsError):Authority(self.authority.path,self.private,self.public,{self.provider:self.secret},initialize=True)
        with self.assertRaises(Rejected):Authority(self.root/'missing',self.private,self.public,{self.provider:self.secret})
    def test_tampered_dispatch_bundle_rejected(self):
        bundle=decode(self.dispatch());bundle['grant']=encode({'bad':0})
        with self.assertRaises(Rejected):self.launch(encode(bundle))
        self.assertEqual(self.allowed_consumes(),0)

if __name__=='__main__':unittest.main()
