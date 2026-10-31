# SPDX-License-Identifier: Apache-2.0
import copy
import json
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import tempfile
import unittest
from tools.formal_migration import s2,policy as p,foundation as f,s2_fixture as fixture,s2_evidence as evidence
from tools.verification_profile import codec as c
ROOT=Path(__file__).resolve().parents[2]
class S2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.keydir=Path(cls.temp.name)/'keys';cls.cfg,cls.bundles=fixture.build(ROOT,cls.keydir,b'x'*32)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.now=3000
        self.db=Path(self.tmp.name)/'state.db';self.cfg=copy.deepcopy(type(self).cfg)
        self.ledger=s2.Ledger(self.db,self.cfg,self.keydir/'issuer.pem',clock=lambda:self.now,create=True)
    def req(self,op,body,actor='requester',nonce=None):
        rec=self.cfg['requester'] if actor=='requester' else self.cfg['providers'][actor.upper()]
        return s2.request(self.cfg,self.keydir/(actor+'.pem'),f.principal_digest(rec),op,body,self.now,nonce)
    def call(self,req):return s2.check_response(self.cfg,req,self.ledger.handle(c.encode(req)))
    def create(self,i=0):
        b=self.bundles[i];req=self.req('CREATE',dict(bundle=b,receipt_signature=fixture.receipt_sign(self.keydir/'requester.pem',b)))
        return req,self.call(req)['result']
    def activate(self,t,role='EXECUTOR',**kw):
        body=dict(receipt=t['receipt'],assignment=t['leases'][role]['proposal']['assignment'],epoch=1);body.update(kw)
        return self.req('ACTIVATE',body,role.lower())
    def consume(self,t,l,role='EXECUTOR',**kw):
        b=dict(receipt=t['receipt'],assignment=l['proposal']['assignment'],epoch=1,capability=l['capability'],intent=b'i'*32);b.update(kw)
        return self.req('CONSUME',b,role.lower())
    def rejected_unchanged(self,req):
        before=self.ledger.state();head=self.ledger.replay()
        with self.assertRaises((c.CodecError,ValueError)):self.call(req)
        self.assertEqual(before,self.ledger.state());self.assertEqual(head,self.ledger.replay())
    def test_public_frozen_transition_and_rejection_vectors(self):
        v=json.loads((ROOT/'tests/formal_migration/execution-vectors.json').read_text());cfg=c.decode(bytes.fromhex(v['config_hex']));state=s2.initial(cfg)
        for row in v['vectors']:
            with self.subTest(vector=row['id']):
                raw=bytes.fromhex(row['raw_hex'])
                if row['valid']:
                    state,result=s2.reduce(cfg,state,c.decode(raw),v['now']);self.assertEqual(s2.h(result).hex(),row['result_digest'])
                else:
                    with self.assertRaises(c.CodecError) as got:s2.reduce(cfg,state,c.decode(raw),v['now'])
                    self.assertEqual(str(got.exception),row['error'])
                self.assertEqual(s2.h(state).hex(),row['state_digest'])
    def test_issuer_key_pin_and_response_time_are_enforced(self):
        with self.assertRaises(c.CodecError):s2.Ledger(Path(self.tmp.name)/'wrong.db',self.cfg,self.keydir/'executor.pem',create=True)
        _,t=self.create();r=self.activate(t);raw=self.ledger.handle(c.encode(r));v=c.decode(raw);v['payload']['now']=r['expires_at'];v['signature']=s2.sign(self.keydir/'issuer.pem','RESPONSE',v['payload'])
        with self.assertRaises(c.CodecError):s2.check_response(self.cfg,r,c.encode(v))
    def test_public_snapshot_replays_without_private_key(self):
        _,t=self.create();self.call(self.activate(t));snapshot=evidence.export(self.ledger)
        self.assertEqual(evidence.verify(self.cfg,snapshot)['events'],2)
        evidence.verify(self.cfg,snapshot,snapshot['checkpoint'])
        altered=copy.deepcopy(snapshot);state=c.decode(altered['state']);state['free']+=1;altered['state']=c.encode(state)
        with self.assertRaises(c.CodecError):evidence.verify(self.cfg,altered)
    def test_snapshot_missing_event_and_wrong_anchor_refused(self):
        _,t=self.create();self.call(self.activate(t));snapshot=evidence.export(self.ledger);altered=copy.deepcopy(snapshot);altered['events'].pop()
        with self.assertRaises(c.CodecError):evidence.verify(self.cfg,altered)
        wrong=dict(snapshot['checkpoint'],head=b'z'*32)
        with self.assertRaises(c.CodecError):evidence.verify(self.cfg,snapshot,wrong)
    def test_malformed_operation_type_is_a_clean_rejection(self):
        for value in ([],{},1,b'QUERY'):
            r=self.req('QUERY',dict(receipt=b'x'*32));r['op']=value;self.rejected_unchanged(r)
    def test_atomic_activation_and_idempotency(self):
        _,t=self.create();self.assertEqual(self.ledger.state()['free'],68)
        req=self.activate(t);a=self.call(req);self.assertEqual(a['result']['state'],'ACTIVE');self.assertEqual(self.ledger.state()['free'],51)
        self.assertEqual(self.call(req)['result'],a['result']);self.assertEqual(self.ledger.replay()['seq'],2)
        self.call(self.activate(t,'AUDITOR'));self.assertEqual(self.ledger.state()['held'],17)
        self.assertEqual(s2.exposure(self.cfg,self.ledger.state())['cluster:UNKNOWN_SHARED']['value'],12)
    def test_all_five_exposure_dimensions_roll_back(self):
        for dimension in self.cfg['caps']:
            with self.subTest(dimension=dimension):
                cfg=copy.deepcopy(self.cfg);cfg['caps'][dimension]['value']=1;path=Path(self.tmp.name)/(dimension+'.db');l=s2.Ledger(path,cfg,self.keydir/'issuer.pem',clock=lambda:self.now,create=True)
                b=self.bundles[0];r=s2.request(cfg,self.keydir/'requester.pem',f.principal_digest(cfg['requester']),'CREATE',dict(bundle=b,receipt_signature=fixture.receipt_sign(self.keydir/'requester.pem',b)),self.now);t=s2.check_response(cfg,r,l.handle(c.encode(r)))['result']
                req=s2.request(cfg,self.keydir/'executor.pem',f.principal_digest(cfg['providers']['EXECUTOR']),'ACTIVATE',dict(receipt=t['receipt'],assignment=t['leases']['EXECUTOR']['proposal']['assignment'],epoch=1),self.now);before=l.state()
                with self.assertRaises(c.CodecError):l.handle(c.encode(req))
                self.assertEqual(l.state(),before)
    def test_insufficient_funds_no_exposure(self):
        self.cfg['balance']=1;self.db=Path(self.tmp.name)/'poor.db';self.ledger=s2.Ledger(self.db,self.cfg,self.keydir/'issuer.pem',clock=lambda:self.now,create=True)
        _,t=self.create();self.rejected_unchanged(self.activate(t))
    def test_concurrent_activate_and_consume_one_winner(self):
        _,t=self.create()
        def attempt(r):
            try:return self.call(r)['result']
            except c.CodecError:return None
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(attempt,[self.activate(t),self.activate(t)]))
        self.assertEqual(sum(x is not None for x in results),1);l=next(x for x in results if x is not None)
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(attempt,[self.consume(t,l,intent=bytes([i])*32) for i in (1,2)]))
        self.assertEqual(sum(x is not None for x in results),1);self.assertEqual(self.ledger.state()['held'],17)
    def test_wrong_actor_epoch_capability_assignment(self):
        _,t=self.create();self.rejected_unchanged(self.activate(t,epoch=0));self.rejected_unchanged(self.activate(t,assignment=b'z'*32))
        r=self.activate(t);r['actor']=f.principal_digest(self.cfg['providers']['AUDITOR']);self.rejected_unchanged(r)
        l=self.call(self.activate(t))['result'];self.rejected_unchanged(self.consume(t,l,capability=b'z'*32));self.rejected_unchanged(self.consume(t,l,epoch=2))
    def test_conflicting_nonce_and_repeat_attempt(self):
        _,t=self.create();act=self.activate(t);l=self.call(act)['result']
        self.rejected_unchanged(self.req('QUERY',dict(receipt=t['receipt']),'executor',act['nonce']))
        req=self.consume(t,l);self.call(req);self.assertEqual(self.call(req)['result']['state'],'CONSUMED')
        self.rejected_unchanged(self.consume(t,l,intent=b'z'*32));self.rejected_unchanged(self.activate(t))
    def test_deadline_fence_exposure_only_funds_pending_s3(self):
        _,t=self.create();l=self.call(self.activate(t))['result'];self.rejected_unchanged(self.req('FENCE',dict(receipt=t['receipt'])))
        self.now=5000;self.rejected_unchanged(self.consume(t,l));r=self.req('FENCE',dict(receipt=t['receipt']));self.call(r);self.call(r)
        self.assertEqual(s2.exposure(self.cfg,self.ledger.state()),{});self.assertEqual(self.ledger.state()['held'],17)
    def test_legacy_unknown_fields_network_and_receipt(self):
        for op in ('CHECK','FUNDED_START','START','RESULT','SETTLE'):
            r=self.req('QUERY',dict(receipt=b'x'*32));r['op']=op;self.rejected_unchanged(r)
        req,t=self.create();r=copy.deepcopy(req);r['body']['receipt_id']='old';self.rejected_unchanged(r)
        r=copy.deepcopy(req);r['genesis']=b'z'*32;self.rejected_unchanged(r)
        r=copy.deepcopy(req);r['body']['bundle']['receipt']['execution']['fuel']-=1;self.rejected_unchanged(r)
    def test_commit_rollback_and_lost_reply(self):
        _,t=self.create();req=self.activate(t)
        def before(point):
            if point=='BEFORE_COMMIT':raise RuntimeError('injected crash')
        self.ledger.hook=before;old=self.ledger.state()
        with self.assertRaises(RuntimeError):self.call(req)
        self.assertEqual(self.ledger.state(),old)
        def after(point):
            if point=='AFTER_COMMIT':raise RuntimeError('lost reply')
        self.ledger.hook=after
        with self.assertRaises(RuntimeError):self.call(req)
        self.ledger.hook=lambda _:None;q=self.call(self.req('QUERY',dict(receipt=t['receipt'])))
        self.assertEqual(q['result']['task']['leases']['EXECUTOR']['state'],'ACTIVE');self.assertEqual(self.call(req)['result']['state'],'ACTIVE')
    def test_reopen_replay_corruption_refused(self):
        _,t=self.create();self.call(self.activate(t));self.assertEqual(s2.Ledger(self.db,self.cfg,self.keydir/'issuer.pem').replay(),self.ledger.replay())
        state=self.ledger.state();state['free']+=1
        with closing(sqlite3.connect(self.db)) as db:
            db.execute('UPDATE meta SET state=?',(c.encode(state),));db.commit()
        with self.assertRaises(c.CodecError):self.ledger.replay()
    def test_checkpoint_challenge_inclusion_consistency(self):
        _,t=self.create();a=self.activate(t);raw=self.ledger.handle(c.encode(a));q=s2.check_response(self.cfg,a,raw)
        r=self.req('QUERY',dict(receipt=t['receipt']))
        with self.assertRaises(c.CodecError):s2.check_response(self.cfg,r,raw)
        next_raw=self.ledger.handle(c.encode(r));s2.check_response(self.cfg,r,next_raw,q['checkpoint']);bad=dict(q['checkpoint'],head=b'z'*32)
        with self.assertRaises(c.CodecError):s2.check_response(self.cfg,r,next_raw,bad)
        changed=c.decode(next_raw);changed['payload']['events'].pop();changed['signature']=s2.sign(self.keydir/'issuer.pem','RESPONSE',changed['payload'])
        with self.assertRaises(c.CodecError):s2.check_response(self.cfg,r,c.encode(changed))
    def test_clock_rollback_config_expiry_query_budget(self):
        _,t=self.create();self.now=2999;self.rejected_unchanged(self.activate(t));self.now=3000
        for _ in range(32):self.call(self.req('QUERY',dict(receipt=t['receipt'])))
        self.rejected_unchanged(self.req('QUERY',dict(receipt=t['receipt'])))
        self.now=9000;self.rejected_unchanged(self.activate(t))
if __name__=='__main__':unittest.main()
