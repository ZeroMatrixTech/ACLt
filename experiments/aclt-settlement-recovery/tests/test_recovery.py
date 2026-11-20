# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from context import *
from recovery import RecoveryLedger
from client import recover,checked_settlement
from fault_driver import FaultGate,DropReply
from executor import execute_once,submit_saved
from audit import reduce
from fixtures import task


class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(); cls.key,cls.pub=create_keys(Path(cls.tmp.name)/'keys')
    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    def setUp(self):
        self.tmpdir=tempfile.TemporaryDirectory(); self.addCleanup(self.tmpdir.cleanup); self.root=Path(self.tmpdir.name)
        self.a=sha(b'recovery-A'); self.b=sha(b'recovery-B'); self.secrets={ZERO:b'p'*32,self.a:b'a'*32,self.b:b'b'*32}
        self.witnesses={'A':{'actor':self.a,'environment':environment()},'B':{'actor':self.b,'environment':sha(b'model-B-env')}}
        self.ledger=RecoveryLedger(self.root/'ledger.sqlite',self.key,self.pub,self.secrets,{ZERO:1000,self.a:0,self.b:0},self.witnesses)
        self.cfgs={role:{'authority_id':self.ledger.authority,'requester':actor,'secret':self.secrets[actor],'public_digest':self.ledger.pin,'role':role,'environment':self.witnesses[role]['environment'] if role in self.witnesses else ZERO} for role,actor in [('PAYER',ZERO),('A',self.a),('B',self.b)]}
        c,_,art,inp=task(bytes(16)); p=policy(c,self.b,100,30); self.pid=policy_id(p)
        self.binding=encode({'policy':p,'commitment':c,'artifact':art,'input':inp}); self.call('FREEZE',decode(self.binding)); self.call('RESERVE',{'policy_id':self.pid})
    def call(self,op,data,role='PAYER'):
        cfg=self.cfgs[role]; packet=request(cfg,op,data); return response(packet,self.ledger.handle(packet),cfg,self.pub)
    def ready(self):
        for role in ['A','B']:
            permit=self.call('START',{'policy_id':self.pid,'role':role},role)['result']['permit']; body=verify(permit,self.pub,self.ledger.pin)
            result={'outcome':'OK','gas_used':9126,'output':b'model'}
            report=encode({'schema_id':'aclt.exp.compared-outcome@1','permit_digest':sha(permit),'task':body['task'],'role':role,'environment':body['environment'],'result':result,'outcome_digest':tagged('ACLt/RIR-0/ExecutionOutcome/1',encode(result))})
            self.call('SUBMIT',{'policy_id':self.pid,'role':role,'report':report},role)
    def settle(self): return self.call('SETTLE',{'policy_id':self.pid})
    def audit(self):
        b,a=self.ledger.export(); return reduce(b,a,self.pub,self.ledger.pin,sha(a))
    def recovery(self,record=None):
        cfg=self.cfgs['PAYER']
        def transport(packet):
            if record is not None: record.append(decode(decode(packet)['payload'])['op'])
            raw=self.ledger.handle(packet); return response(packet,raw,cfg,self.pub),raw
        return recover(cfg,self.pub,self.pid,transport)
    def test_no_hook_uses_original_transition_and_receipt(self):
        self.ready(); r=self.settle(); self.assertEqual(verify(r['result']['receipt'],self.pub,self.ledger.pin)['paid'],30); self.assertEqual(self.audit()['settlements'],1)
    def test_before_commit_failure_rolls_back_entitlement_money_and_event(self):
        self.ready(); previous=self.audit()
        def hook(point,info):
            if point=='before_commit' and info['op']=='SETTLE': raise OSError('before COMMIT')
        self.ledger.test_hook=hook
        with self.assertRaises(OSError): self.settle()
        self.ledger.test_hook=None; self.assertEqual(self.audit(),previous)
        self.assertEqual(self.recovery()['recovery_status'],'HELD'); self.assertEqual(self.settle()['status'],'SETTLED'); self.assertEqual(self.audit()['paid'],30)
    def test_after_commit_failure_keeps_exact_original_entitlement(self):
        self.ready(); observed=[]
        def hook(point,info):
            if point=='after_commit' and info['op']=='SETTLE': observed.append(info); raise HostFault('after COMMIT')
        self.ledger.test_hook=hook
        with self.assertRaises(HostFault): self.settle()
        self.ledger.test_hook=None; recovered=self.recovery(); receipt=recovered['response']['result']['receipt']
        self.assertEqual(recovered['recovery_status'],'RECOVERED'); self.assertEqual(sha(receipt).hex(),observed[0]['receipt_digest']); self.assertEqual(self.settle()['result']['receipt'],receipt)
        self.assertEqual((self.audit()['settlements'],self.audit()['paid']),(1,30))
    def test_held_recovery_only_queries_even_when_results_complete(self):
        self.ready(); ops=[]; r=self.recovery(ops); self.assertEqual(ops,['STATUS']); self.assertEqual(r['recovery_status'],'HELD'); self.assertEqual(self.audit()['reserved'],100)
    def test_settled_recovery_only_queries(self):
        self.ready(); self.settle(); ops=[]; self.assertEqual(self.recovery(ops)['recovery_status'],'RECOVERED'); self.assertEqual(ops,['STATUS']); self.assertEqual(self.audit()['paid'],30)
    def test_unfunded_recovery_does_not_reserve_or_pay(self):
        c,_,art,inp=task(bytes([1])*16); p=policy(c,self.b,100,30); self.pid=policy_id(p)
        self.call('FREEZE',{'policy':p,'commitment':c,'artifact':art,'input':inp}); ops=[]
        self.assertEqual(self.recovery(ops)['recovery_status'],'UNFUNDED'); self.assertEqual(ops,['STATUS']); self.assertEqual(self.audit()['reserved'],100)
    def test_offline_recovery_no_guessed_payment_or_refund(self):
        previous=self.audit(); ops=[]
        def offline(packet):
            ops.append(decode(decode(packet)['payload'])['op']); raise HostFault('offline')
        with self.assertRaises(HostFault): recover(self.cfgs['PAYER'],self.pub,self.pid,offline)
        self.assertEqual(ops,['STATUS']); self.assertEqual(previous,self.audit())
    def test_recovery_uses_signed_bytes_not_untrusted_decoded_view(self):
        cfg=self.cfgs['PAYER']
        def transport(packet):
            raw=self.ledger.handle(packet); return {'status':'SETTLED'},raw
        self.assertEqual(recover(cfg,self.pub,self.pid,transport)['recovery_status'],'HELD')
    def test_wrong_nonce_signed_query_reply_rejected(self):
        cfg=self.cfgs['PAYER']; wrong=request(cfg,'STATUS',{'policy_id':self.pid}); raw=self.ledger.handle(wrong)
        with self.assertRaises(Rejected): recover(cfg,self.pub,self.pid,lambda packet:({},raw))
    def test_recovered_receipt_cannot_belong_to_other_policy(self):
        self.ready(); receipt=self.settle()['result']['receipt']
        with self.assertRaises(Rejected): checked_settlement(receipt,self.cfgs['PAYER'],self.pub,ZERO)
    def test_drop_gate_after_commit_keeps_money_and_marker(self):
        self.ready(); ready=self.root/'drop-ready.json'; control=self.root/'control.json'
        control.write_text(json.dumps({'point':'after_commit','mode':'drop','op':'SETTLE','policy_id':self.pid.hex(),'ready':str(ready),'token':'test-token'}))
        self.ledger.test_hook=FaultGate(control)
        with self.assertRaises(DropReply): self.settle()
        observed=json.loads(ready.read_text()); self.assertEqual(observed['token'],'test-token'); self.ledger.test_hook=None
        self.assertEqual(sha(self.recovery()['response']['result']['receipt']).hex(),observed['receipt_digest']); self.assertEqual(self.audit()['paid'],30)
    def test_drop_gate_cannot_fake_precommit_response_loss(self):
        control=self.root/'control.json'; control.write_text(json.dumps({'point':'before_commit','mode':'drop','op':'SETTLE','policy_id':self.pid.hex(),'ready':str(self.root/'ready'),'token':'invalid'}))
        with self.assertRaises(Rejected): FaultGate(control)('before_commit',{'op':'SETTLE','policy_id':self.pid.hex(),'status':'SETTLED'})
    def test_permission_only_interruption_never_recomputes_or_refunds(self):
        cfg=self.cfgs['A']; tid=decode(decode(self.binding)['policy'])['task'].hex(); transport=lambda p:response(p,self.ledger.handle(p),cfg,self.pub)
        def stop(point):
            if point=='after_permit': raise HostFault('interrupted after permit')
        with patch('rir_adapter.execute',side_effect=AssertionError('must not run')):
            with self.assertRaises(HostFault): execute_once(cfg,self.pub,self.root/'state',self.binding,tid,transport,stop)
            with self.assertRaises(Rejected): execute_once(cfg,self.pub,self.root/'clone',self.binding,tid,transport)
        self.assertFalse((self.root/'state/invoke.cbor').exists()); self.assertEqual(self.settle()['status'],'PENDING'); a=self.audit(); self.assertEqual((a['starts'],a['outcomes'],a['reserved']),(1,0,100))
    def test_saved_outcome_interruption_can_submit_without_guest(self):
        cfg=self.cfgs['A']; tid=decode(decode(self.binding)['policy'])['task'].hex(); transport=lambda p:response(p,self.ledger.handle(p),cfg,self.pub)
        def stop(point):
            if point=='after_outcome': raise HostFault('interrupted after outcome')
        with self.assertRaises(HostFault): execute_once(cfg,self.pub,self.root/'state',self.binding,tid,transport,stop)
        with patch('rir_adapter.execute',side_effect=AssertionError('must not recompute')):
            self.assertEqual(submit_saved(cfg,self.pub,self.root/'state',self.pid,transport)['status'],'RECORDED')
            self.assertEqual(submit_saved(cfg,self.pub,self.root/'state',self.pid,transport)['status'],'DUPLICATE')
        self.assertEqual(self.audit()['outcomes'],1)
    def test_rolled_back_operation_does_not_extend_checkpoint(self):
        self.ready(); bundle,anchor=self.ledger.export()
        self.ledger.test_hook=lambda p,i: (_ for _ in ()).throw(OSError('stop')) if p=='before_commit' and i['op']=='SETTLE' else None
        with self.assertRaises(OSError): self.settle()
        self.ledger.test_hook=None; newer,new_anchor=self.ledger.export(); self.assertEqual(bundle,newer); self.assertEqual(anchor,new_anchor)
        self.settle(); latest,latest_anchor=self.ledger.export()
        self.assertEqual(reduce(latest,latest_anchor,self.pub,self.ledger.pin,sha(anchor))['sha_consistency'],'DISABLED')
    def test_held_reservation_and_settled_money_are_distinct(self):
        self.ready(); self.settle(); c,_,art,inp=task(bytes([2])*16); p=policy(c,self.b,100,30); self.pid=policy_id(p)
        self.call('FREEZE',{'policy':p,'commitment':c,'artifact':art,'input':inp}); self.call('RESERVE',{'policy_id':self.pid}); self.assertEqual(self.settle()['status'],'PENDING')
        a=self.audit(); self.assertEqual((a['paid'],a['refunded'],a['reserved'],a['available']),(30,70,100,900))
