# SPDX-License-Identifier: Apache-2.0
from concurrent.futures import ThreadPoolExecutor
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from wire import *
import ledger as writer
from ledger import Ledger
from audit import reduce
from executor import execute_once, submit_saved
from fixtures import task


class SettlementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(); cls.key,cls.pub=create_keys(Path(cls.tmp.name)/'keys')
    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    def setUp(self):
        self.tmpdir=tempfile.TemporaryDirectory(); self.addCleanup(self.tmpdir.cleanup); self.root=Path(self.tmpdir.name)
        self.a=sha(b'witness-A'); self.b=sha(b'witness-B'); self.secrets={ZERO:b'p'*32,self.a:b'a'*32,self.b:b'b'*32}
        self.witnesses={'A':{'actor':self.a,'environment':environment()},'B':{'actor':self.b,'environment':sha(b'unit-model-B')}}
        self.ledger=Ledger(self.root/'ledger.sqlite',self.key,self.pub,self.secrets,{ZERO:1000,self.a:0,self.b:0},self.witnesses)
        self.cfgs={role:{'authority_id':self.ledger.authority,'requester':actor,'secret':self.secrets[actor],'public_digest':self.ledger.pin,'role':role,'environment':self.witnesses[role]['environment'] if role in self.witnesses else ZERO} for role,actor in [('PAYER',ZERO),('A',self.a),('B',self.b)]}
        c,_,art,inp=task(bytes(16)); raw=policy(c,self.b,100,30)
        self.binding=encode({'policy':raw,'commitment':c,'artifact':art,'input':inp}); self.pid=policy_id(raw)
        self.call('FREEZE',decode(self.binding))
    def call(self,op,data,role='PAYER'):
        cfg=self.cfgs[role]; packet=request(cfg,op,data); return response(packet,self.ledger.handle(packet),cfg,self.pub)
    def reserve(self): return self.call('RESERVE',{'policy_id':self.pid})
    def start(self,role): return self.call('START',{'policy_id':self.pid,'role':role},role)
    def report(self,role,result=None):
        permit=self.start(role)['result']['permit']; body=verify(permit,self.pub,self.ledger.pin)
        result=result or {'outcome':'OK','gas_used':9126,'output':b'model-output'}
        return encode({'schema_id':'aclt.exp.compared-outcome@1','permit_digest':sha(permit),'task':body['task'],'role':role,'environment':body['environment'],'result':result,'outcome_digest':tagged('ACLt/RIR-0/ExecutionOutcome/1',encode(result))})
    def submit(self,role,raw): return self.call('SUBMIT',{'policy_id':self.pid,'role':role,'report':raw},role)
    def ready(self,left=None,right=None):
        self.reserve(); a=self.report('A',left); b=self.report('B',right); self.submit('A',a); self.submit('B',b); return a,b
    def settle(self): return self.call('SETTLE',{'policy_id':self.pid})
    def audit(self):
        bundle,anchor=self.ledger.export(); return reduce(bundle,anchor,self.pub,self.ledger.pin,sha(anchor))
    def test_matching_OK_pays_fixed_fee_refunds_remainder(self):
        self.ready(); r=self.settle(); s=verify(r['result']['receipt'],self.pub,self.ledger.pin)
        self.assertEqual((s['paid'],s['refunded'],s['decision']),(30,70,'MATCH_OK'))
        a=self.audit(); self.assertEqual((a['available'],a['reserved'],a['settlements']),(1000,0,1))
        self.assertEqual(a['projection']['accounts'][ZERO.hex()]['available'],970)
        self.assertEqual(a['projection']['accounts'][self.b.hex()]['available'],30)
    def test_matching_trap_closes_no_pay_full_refund(self):
        trap={'outcome':'TRAP_UNREACHABLE','gas_used':8200}; self.ready(trap,trap); self.settle()
        a=self.audit(); self.assertEqual((a['paid'],a['refunded'],a['reserved']),(0,100,0))
    def test_complete_mismatch_is_frozen_no_pay_case(self):
        self.ready(right={'outcome':'OK','gas_used':9126,'output':b'different'}); self.settle()
        self.assertEqual(self.audit()['paid'],0); self.assertEqual(self.audit()['refunded'],100)
    def test_missing_both_outcomes_pending_holds(self):
        self.reserve(); self.assertEqual(self.settle()['status'],'PENDING'); a=self.audit()
        self.assertEqual((a['reserved'],a['settlements']),(100,0))
    def test_missing_one_outcome_pending_holds(self):
        self.reserve(); self.submit('A',self.report('A')); self.assertEqual(self.settle()['status'],'PENDING'); self.assertEqual(self.audit()['reserved'],100)
    def test_exact_and_new_nonce_settlement_return_original(self):
        self.ready(); first=self.settle(); second=self.settle(); self.assertEqual(second['status'],'DUPLICATE'); self.assertEqual(first['result'],second['result'])
        packet=request(self.cfgs['PAYER'],'SETTLE',{'policy_id':self.pid}); self.ledger.handle(packet); self.ledger.handle(packet)
        self.assertEqual((self.audit()['paid'],self.audit()['settlements']),(30,1))
    def test_concurrent_settlement_one_entitlement(self):
        self.ready()
        with ThreadPoolExecutor(3) as pool: results=list(pool.map(lambda _:self.settle(),range(3)))
        self.assertEqual(sum(r['status']=='SETTLED' for r in results),1); self.assertEqual(len({r['result']['receipt'] for r in results}),1); self.assertEqual(self.audit()['paid'],30)
    def test_wrong_payer_cannot_settle(self):
        self.ready(); self.assertEqual(self.call('SETTLE',{'policy_id':self.pid},'B')['status'],'DENIED'); self.assertEqual(self.audit()['reserved'],100)
    def test_client_cannot_choose_amount_or_refund_branch(self):
        self.ready()
        for extra in [{'paid':0},{'decision':'CLOSED_NO_PAY'},{'entitlement_id':ZERO}]:
            with self.assertRaises(Rejected): self.call('SETTLE',{'policy_id':self.pid,**extra})
        self.assertEqual(self.settle()['status'],'SETTLED')
    def test_accepted_only_OR_HostFault_never_evidence(self):
        self.reserve(); raw=self.report('A'); obj=decode(raw); obj['result']={'outcome':'HOST_FAULT','gas_used':9126}
        with self.assertRaises(Rejected): self.submit('A',encode(obj))
        self.assertEqual(self.settle()['status'],'PENDING')
    def test_start_requires_reservation(self):
        self.assertEqual(self.start('A')['status'],'DENIED'); self.assertEqual(self.audit()['starts'],0)
    def test_start_once_even_new_nonce_or_clone(self):
        self.reserve(); self.assertEqual(self.start('A')['status'],'STARTED'); self.assertEqual(self.start('A')['status'],'DENIED'); self.assertEqual(self.audit()['starts'],1)
    def test_witness_cannot_impersonate_other_role(self):
        self.reserve(); self.assertEqual(self.call('START',{'policy_id':self.pid,'role':'A'},'B')['status'],'DENIED')
        self.assertEqual(self.call('START',{'policy_id':self.pid,'role':'A'})['status'],'DENIED')
    def test_wrong_task_role_environment_or_outcome_hash_rejected(self):
        self.reserve(); raw=self.report('A')
        for key,value in [('task',ZERO),('role','B'),('environment',ZERO),('outcome_digest',ZERO),('permit_digest',ZERO)]:
            with self.assertRaises(Rejected): self.submit('A',encode({**decode(raw),key:value}))
        self.assertEqual(self.audit()['outcomes'],0)
    def test_partial_output_and_resource_mismatch_rejected(self):
        self.reserve(); raw=self.report('A'); obj=decode(raw)
        for result in [{'outcome':'OK','gas_used':9126},{'outcome':'TRAP_UNREACHABLE','gas_used':9126,'output':b'partial'},{'outcome':'OK','gas_used':50000001,'output':b''}]:
            with self.assertRaises(Rejected): self.submit('A',encode({**obj,'result':result,'outcome_digest':tagged('ACLt/RIR-0/ExecutionOutcome/1',encode(result))}))
    def test_outcome_immutable_duplicate_and_conflict(self):
        self.reserve(); raw=self.report('A'); self.submit('A',raw); self.assertEqual(self.submit('A',raw)['status'],'DUPLICATE')
        obj=decode(raw); obj['result']['output']=b'changed'; obj['outcome_digest']=tagged('ACLt/RIR-0/ExecutionOutcome/1',encode(obj['result']))
        self.assertEqual(self.submit('A',encode(obj))['status'],'CONFLICT'); self.assertEqual(self.audit()['outcomes'],1)
    def test_signature_or_event_failure_rolls_back_settlement(self):
        self.ready()
        with patch.object(writer,'sign',side_effect=HostFault('signer')):
            with self.assertRaises(HostFault): self.settle()
        self.assertEqual(self.audit()['reserved'],100)
        with patch.object(self.ledger,'append',side_effect=OSError('event')):
            with self.assertRaises(OSError): self.settle()
        self.assertEqual(self.audit()['settlements'],0); self.settle(); self.assertEqual(self.audit()['paid'],30)
    def test_reply_failure_after_commit_query_original(self):
        self.ready(); real=writer.sign
        def fault(p,key):
            if p['schema_id']=='aclt.exp.funding-response@2': raise HostFault('lost reply')
            return real(p,key)
        with patch.object(writer,'sign',side_effect=fault):
            with self.assertRaises(HostFault): self.settle()
        status=self.call('STATUS',{'policy_id':self.pid}); self.assertEqual(status['status'],'SETTLED'); self.assertEqual(status['result'],self.settle()['result']); self.assertEqual(self.audit()['paid'],30)
    def test_restart_duplicate_and_no_rereservation(self):
        self.ready(); first=self.settle(); self.ledger=Ledger(self.root/'ledger.sqlite',self.key,self.pub,self.secrets)
        self.assertEqual(first['result'],self.settle()['result']); self.assertEqual(self.reserve()['status'],'DUPLICATE'); self.assertEqual(self.audit()['reserved'],0)
    def test_real_executor_gated_and_saved_resubmit_never_reexecutes(self):
        cfg=self.cfgs['A']; transport=lambda p:response(p,self.ledger.handle(p),cfg,self.pub); tid=decode(decode(self.binding)['policy'])['task'].hex()
        self.reserve(); pid,raw=execute_once(cfg,self.pub,self.root/'state',self.binding,tid,transport)
        self.assertEqual(decode(raw)['result']['gas_used'],9126)
        with patch('rir_adapter.execute',side_effect=AssertionError('must not execute')):
            self.assertEqual(submit_saved(cfg,self.pub,self.root/'state',pid,transport)['status'],'RECORDED')
            self.assertEqual(submit_saved(cfg,self.pub,self.root/'state',pid,transport)['status'],'DUPLICATE')
            with self.assertRaises(Rejected): execute_once(cfg,self.pub,self.root/'clone',self.binding,tid,transport)
        self.audit()
    def test_stale_environment_or_unfunded_executor_never_guest(self):
        cfg=self.cfgs['A']; tid=decode(decode(self.binding)['policy'])['task'].hex(); transport=lambda p:response(p,self.ledger.handle(p),cfg,self.pub)
        with patch('rir_adapter.execute',side_effect=AssertionError('must not execute')):
            with self.assertRaises(Rejected): execute_once({**cfg,'environment':ZERO},self.pub,self.root/'bad-env',self.binding,tid,transport)
            with self.assertRaises(Rejected): execute_once(cfg,self.pub,self.root/'unfunded',self.binding,tid,transport)
        self.assertEqual(self.audit()['starts'],0)
    def test_policy_v2_is_closed_and_frozen(self):
        obj=decode(decode(self.binding)['policy']); self.assertEqual(obj['schema_id'],'aclt.exp.funding-policy@2')
        with self.assertRaises(Rejected): validate_policy({**obj,'comparison_rule':'manual'})
        changed=decode(self.binding); changed['policy']=encode({**obj,'success_fee':1}); self.assertEqual(self.call('FREEZE',changed)['status'],'CONFLICT')
    def test_offline_tamper_and_wrong_pins(self):
        self.ready(); self.settle(); bundle,anchor=self.ledger.export()
        bad=copy.deepcopy(bundle); bad['events'].pop()
        with self.assertRaises(Rejected): reduce(bad,anchor,self.pub,self.ledger.pin,sha(anchor))
        bad=copy.deepcopy(bundle); bad['projection']['accounts'][ZERO.hex()]['available']+=1
        with self.assertRaises(Rejected): reduce(bad,anchor,self.pub,self.ledger.pin,sha(anchor))
        for pin,ad in [(ZERO,sha(anchor)),(self.ledger.pin,ZERO)]:
            with self.assertRaises(Rejected): reduce(bundle,anchor,self.pub,pin,ad)

    def test_zero_and_full_fee_integer_splits(self):
        for nonce,fee in [(1,0),(2,100)]:
            c,_,art,inp=task(bytes([nonce])*16); raw=policy(c,self.b,100,fee)
            self.binding=encode({'policy':raw,'commitment':c,'artifact':art,'input':inp}); self.pid=policy_id(raw)
            self.call('FREEZE',decode(self.binding)); self.ready(); body=verify(self.settle()['result']['receipt'],self.pub,self.ledger.pin)
            self.assertEqual((body['paid'],body['refunded']),(fee,100-fee))
        self.assertEqual((self.audit()['paid'],self.audit()['refunded']),(100,100))
    def test_integer_max_settlement_no_float_or_overflow(self):
        self.ledger=Ledger(self.root/'max.sqlite',self.key,self.pub,self.secrets,{ZERO:MAX,self.a:0,self.b:0},self.witnesses)
        for cfg in self.cfgs.values(): cfg['authority_id']=self.ledger.authority
        data=decode(self.binding); data['policy']=policy(data['commitment'],self.b,MAX,MAX); self.binding=encode(data); self.pid=policy_id(data['policy'])
        self.call('FREEZE',data); self.ready(); self.settle(); a=self.audit()
        self.assertEqual((a['paid'],a['reserved'],a['initial_total']),(MAX,0,MAX))
    def test_start_reply_loss_consumes_permission_without_execution(self):
        self.reserve(); cfg=self.cfgs['A']; tid=decode(decode(self.binding)['policy'])['task'].hex(); real=writer.sign
        def fault(p,key):
            if p['schema_id']=='aclt.exp.funding-response@2': raise HostFault('start reply lost')
            return real(p,key)
        transport=lambda p:response(p,self.ledger.handle(p),cfg,self.pub)
        with patch('rir_adapter.execute',side_effect=AssertionError('must not execute')):
            with patch.object(writer,'sign',side_effect=fault):
                with self.assertRaises(HostFault): execute_once(cfg,self.pub,self.root/'lost-start',self.binding,tid,transport)
            with self.assertRaises(Rejected): execute_once(cfg,self.pub,self.root/'clone-start',self.binding,tid,transport)
        a=self.audit(); self.assertEqual((a['starts'],a['outcomes'],a['reserved']),(1,0,100))
