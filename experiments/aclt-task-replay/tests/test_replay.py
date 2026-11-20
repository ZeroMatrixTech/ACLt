# SPDX-License-Identifier: Apache-2.0
import copy
from pathlib import Path
import secrets
import sys
import tempfile
import unittest
from unittest.mock import patch
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
from context import *
from ledger import Ledger
from worker import dispatch,launch,replay,export_worker
from offline import reduce
from fixtures import task
from journal import Journal

class Stop(BaseException):pass

class ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keys=tempfile.TemporaryDirectory();cls.private,cls.public=create_keys(Path(cls.keys.name)/'keys')
    @classmethod
    def tearDownClass(cls):cls.keys.cleanup()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.provider=sha(b'provider-B');self.unit=sha(b'unit-B');self.secret=secrets.token_bytes(32);self.now=1000
        self.ledger=Ledger(self.root/'ledger.sqlite',self.private,self.public,{self.provider:self.secret},initialize=True,clock=lambda:self.now)
        self.c,self.identity,self.artifact,self.input=task(secrets.token_bytes(16));self.ledger.register(self.c,self.artifact,self.input)
        self.cfg={'authority_id':self.ledger.authority_id,'public_digest':sha(self.public.read_bytes()),'provider_ref':self.provider,'unit_ref':self.unit,'provider_secret':self.secret,'environment_digest':environment_digest()}
        self.delivery=self.ledger.issue(self.c,self.provider,self.unit,self.cfg['environment_digest'],1,900,1100);self.state=self.root/'worker'
    def dispatch(self):return dispatch(self.delivery,self.c,self.identity,self.artifact,[self.input],self.cfg,self.public,self.state,self.ledger.handle)
    def launch(self,transport=None,hook=None):return launch(self.c,self.identity,self.artifact,[self.input],self.cfg,self.public,self.state,transport or self.ledger.handle,hook)
    def package(self):
        authority,anchor=self.ledger.export();bundle={'authority':authority,'workers':[export_worker(self.state)]};return bundle,anchor
    def check(self):
        bundle,anchor=self.package();return reduce(bundle,anchor,self.public,self.cfg['public_digest'],sha(anchor))
    def test_complete_chain_reduces_without_guest_execution(self):
        self.dispatch();self.assertEqual(self.launch()['status'],'ACCEPTED')
        with patch('rir_adapter.execute',side_effect=AssertionError('offline reducer executed guest')):
            state=self.check()
        self.assertEqual((state['accepted'],state['consumed']),(1,1));self.assertTrue(state['workers'][0]['acknowledged'])
    def test_duplicate_replay_keeps_identical_packet_and_receipt(self):
        self.dispatch();self.launch();packet=regular(self.state/'submission.cbor');receipt=regular(self.state/'receipt.cbor')
        with patch('rir_adapter.execute',side_effect=AssertionError('replay executed guest')):
            result=replay(self.state,self.identity,self.cfg,self.public,self.ledger.handle)
        self.assertEqual(result['status'],'DUPLICATE');self.assertEqual(regular(self.state/'submission.cbor'),packet);self.assertEqual(regular(self.state/'receipt.cbor'),receipt)
        self.assertEqual(self.check()['authority_counts']['SUBMIT_DUPLICATE'],1)
    def test_lost_accept_reply_rebuilds_pending_ack_then_replays(self):
        self.dispatch()
        def lose(packet):
            reply=self.ledger.handle(packet)
            if decode(decode(packet)['payload'])['op']=='SUBMIT':raise HostFault('test lost ACCEPT reply')
            return reply
        with self.assertRaises(HostFault):self.launch(transport=lose)
        state=self.check();self.assertEqual(state['accepted'],1);self.assertFalse(state['workers'][0]['acknowledged'])
        self.assertEqual(replay(self.state,self.identity,self.cfg,self.public,self.ledger.handle)['status'],'DUPLICATE');self.assertTrue(self.check()['workers'][0]['acknowledged'])
    def test_restart_authority_keeps_stable_receipt(self):
        self.dispatch();self.launch();receipt=regular(self.state/'receipt.cbor')
        restarted=Ledger(self.ledger.path,self.private,self.public,{self.provider:self.secret},clock=lambda:2000)
        self.assertEqual(replay(self.state,self.identity,self.cfg,self.public,restarted.handle)['status'],'DUPLICATE')
        self.assertEqual(regular(self.state/'receipt.cbor'),receipt);self.check()
    def test_replay_does_not_require_current_boot_environment(self):
        self.dispatch();self.launch()
        with patch('worker.environment_digest',return_value=bytes(32)),patch('rir_adapter.execute',side_effect=AssertionError('guest')):
            self.assertEqual(replay(self.state,self.identity,self.cfg,self.public,self.ledger.handle)['status'],'DUPLICATE')
    def test_intent_only_cannot_replay_or_relaunch(self):
        self.dispatch()
        def stop(stage):
            if stage=='after-intent':raise Stop()
        with self.assertRaises(Stop):self.launch(hook=stop)
        with self.assertRaises((HostFault,FileNotFoundError)):replay(self.state,self.identity,self.cfg,self.public,self.ledger.handle)
        with self.assertRaises(Rejected):self.launch()
        self.assertEqual(self.check()['workers'][0]['phase'],'INTENT')
    def test_outcome_only_cannot_replay(self):
        self.dispatch()
        def stop(stage):
            if stage=='after-outcome':raise Stop()
        with self.assertRaises(Stop):self.launch(hook=stop)
        with self.assertRaises((HostFault,FileNotFoundError)):replay(self.state,self.identity,self.cfg,self.public,self.ledger.handle)
        state=self.check();self.assertEqual(state['workers'][0]['phase'],'OUTCOME');self.assertEqual(state['accepted'],0)
    def test_prepared_process_stop_replays_without_recompute(self):
        self.dispatch()
        def stop(stage):
            if stage=='after-prepared':raise Stop()
        with self.assertRaises(Stop):self.launch(hook=stop)
        self.assertEqual(self.check()['workers'][0]['phase'],'PREPARED')
        with patch('rir_adapter.execute',side_effect=AssertionError('guest')):
            self.assertEqual(replay(self.state,self.identity,self.cfg,self.public,self.ledger.handle)['status'],'ACCEPTED')
        self.check()
    def test_local_submission_mutation_rejected_before_network(self):
        self.dispatch();self.launch();path=self.state/'submission.cbor';path.write_bytes(regular(path)+b'x')
        with self.assertRaises(Rejected),patch('network.exchange',side_effect=AssertionError('network')):replay(self.state,self.identity,self.cfg,self.public)
    def test_truncated_authority_log_rejected_against_retained_checkpoint(self):
        self.dispatch();self.launch();bundle,anchor=self.package();bundle['authority']['events'].pop()
        with self.assertRaises(Rejected):reduce(bundle,anchor,self.public,self.cfg['public_digest'],sha(anchor))
    def test_modified_object_rejected(self):
        self.dispatch();self.launch();bundle,anchor=self.package();key=next(iter(bundle['workers'][0]['journal']['objects']));bundle['workers'][0]['journal']['objects'][key]+=b'x'
        with self.assertRaises(Rejected):reduce(bundle,anchor,self.public,self.cfg['public_digest'],sha(anchor))
    def test_missing_worker_event_or_cross_parent_rejected(self):
        self.dispatch();self.launch();bundle,anchor=self.package();bundle['workers'][0]['journal']['events'].pop(2)
        with self.assertRaises(Rejected):reduce(bundle,anchor,self.public,self.cfg['public_digest'],sha(anchor))
    def test_worker_fork_rejected(self):
        self.dispatch();self.launch();bundle,anchor=self.package();other=copy.deepcopy(bundle['workers'][0]);raw=other['journal']['events'][-1];obj=decode(raw);obj['kind']='SUBMIT_DENIED';other['journal']['events'][-1]=encode(obj);bundle['workers'].append(other)
        with self.assertRaises(Rejected):reduce(bundle,anchor,self.public,self.cfg['public_digest'],sha(anchor))
    def test_wrong_public_pin_and_anchor_rejected(self):
        self.dispatch();self.launch();bundle,anchor=self.package()
        for pin,head in [(bytes(32),sha(anchor)),(self.cfg['public_digest'],bytes(32))]:
            self.assertEqual(reduce(bundle,anchor,self.public,pin,head)['sha_consistency'],'DISABLED')
    def test_projection_tamper_rejected(self):
        self.dispatch();self.launch();bundle,anchor=self.package();bundle['authority']['projection']['tasks']=[]
        with self.assertRaises(Rejected):reduce(bundle,anchor,self.public,self.cfg['public_digest'],sha(anchor))
    def test_reordered_worker_or_missing_attachment_rejected(self):
        self.dispatch();self.launch();bundle,anchor=self.package();bundle['workers'][0]['files'].pop('submission.cbor')
        # ACCEPT still supplies the complete package; removing worker journal objects
        # rather than a redundant attachment must fail.
        objects=bundle['workers'][0]['journal']['objects'];output=next(k for k,v in objects.items() if v==bytes.fromhex('0000000000000000000000000000000002000000000000000200000000000000ffffffffffffffff03000000000000000100000000000000020000000000000002000000000000000d0000000000000005000000000000000800000000000000'))
        del objects[output]
        with self.assertRaises(Rejected):reduce(bundle,anchor,self.public,self.cfg['public_digest'],sha(anchor))

    def test_conflicting_second_packet_keeps_first_receipt(self):
        self.dispatch();self.launch();receipt=regular(self.state/'receipt.cbor')
        from network import request
        sub=decode(regular(self.state/'submission.cbor'));sb=decode(sub['body']);sb['submission_nonce']=bytes(16);sub['body']=encode(sb);raw=encode(sub)
        j=Journal(self.state/'journal',sub['worker']['stream']);prepared=next(r for r in j.events() if decode(r)['kind']=='PREPARED')
        pp=encode({'submission_digest':sha(raw),'body_digest':sha(sub['body'])});pe=decode(prepared);pe['payload_ref']=sha(pp)
        nonce=secrets.token_bytes(16);sp=encode({'submission_digest':sha(raw),'attempt_nonce':nonce})
        se=decode(j.events()[-2]);se['payload_ref']=sha(sp)
        data={'submission':raw,'prepared_event':encode(pe),'prepared_payload':pp,'send_event':encode(se),'send_payload':sp}
        response=verify(self.ledger.handle(request(self.cfg,sb['grant_id'],'SUBMIT',data,nonce)),self.public,self.cfg['public_digest'])
        self.assertEqual(response['status'],'CONFLICT');self.assertEqual(regular(self.state/'receipt.cbor'),receipt)
        state=self.check();self.assertEqual(state['accepted'],1);self.assertEqual(state['authority_counts']['SUBMIT_CONFLICT'],1)
    def test_corrupt_first_packet_rejected_then_original_replayed(self):
        self.dispatch()
        def stop(stage):
            if stage=='after-prepared':raise Stop()
        with self.assertRaises(Stop):self.launch(hook=stop)
        from network import request
        raw=regular(self.state/'submission.cbor');sub=decode(raw);j=Journal(self.state/'journal',sub['worker']['stream'])
        pe=next(r for r in j.events() if decode(r)['kind']=='PREPARED');pp=j.get(decode(pe)['payload_ref'])
        nonce=secrets.token_bytes(16);sp=encode({'submission_digest':sha(raw+b'x'),'attempt_nonce':nonce})
        se={'schema_id':'aclt.exp.causal-event@1','stream':sub['worker']['stream'],'seq':999,'prev':bytes(32),'kind':'SEND','payload_ref':sha(sp),'parents':[]}
        data={'submission':raw+b'x','prepared_event':pe,'prepared_payload':pp,'send_event':encode(se),'send_payload':sp}
        response=verify(self.ledger.handle(request(self.cfg,decode(sub['body'])['grant_id'],'SUBMIT',data,nonce)),self.public,self.cfg['public_digest'])
        self.assertEqual(response['status'],'REJECTED');self.assertEqual(self.check()['accepted'],0)
        self.assertEqual(replay(self.state,self.identity,self.cfg,self.public,self.ledger.handle)['status'],'ACCEPTED');self.assertEqual(self.check()['accepted'],1)
    def test_accept_projection_and_event_transaction_roll_back_together(self):
        self.dispatch()
        def stop(stage):
            if stage=='after-prepared':raise Stop()
        with self.assertRaises(Stop):self.launch(hook=stop)
        before,anchor=self.ledger.export()
        from ledger import sql_append as real_append
        def fail(c,stream,kind,payload,parents=()):
            if kind=='ACCEPT':raise HostFault('injected event write failure')
            return real_append(c,stream,kind,payload,parents)
        with patch('ledger.sql_append',side_effect=fail),self.assertRaises(HostFault):replay(self.state,self.identity,self.cfg,self.public,self.ledger.handle)
        after,_=self.ledger.export();self.assertEqual(before['events'],after['events']);self.assertEqual(before['projection'],after['projection']);self.assertEqual(self.check()['accepted'],0)
        self.assertEqual(replay(self.state,self.identity,self.cfg,self.public,self.ledger.handle)['status'],'ACCEPTED');self.check()
    def test_old_signed_export_is_only_as_of_its_retained_anchor(self):
        self.dispatch();old,old_anchor=self.package();self.launch();current,current_anchor=self.package()
        self.assertEqual(reduce(old,old_anchor,self.public,self.cfg['public_digest'],sha(current_anchor))['accepted'],0)
        self.assertEqual(reduce(old,old_anchor,self.public,self.cfg['public_digest'],sha(old_anchor))['accepted'],0)
    def test_truncated_worker_tail_is_not_silently_discarded(self):
        self.dispatch();self.launch();tail=sorted((self.state/'journal/events').iterdir())[-1];tail.write_bytes(regular(tail)[:-1])
        with self.assertRaises(Rejected):replay(self.state,self.identity,self.cfg,self.public,self.ledger.handle)
    def test_missing_cross_stream_worker_proof_rejected(self):
        self.dispatch();self.launch();bundle,anchor=self.package();bundle['workers']=[]
        with self.assertRaises(Rejected):reduce(bundle,anchor,self.public,self.cfg['public_digest'],sha(anchor))
    def test_duplicate_registration_and_no_empty_ledger_recovery(self):
        self.ledger.register(self.c,self.artifact,self.input)
        with self.assertRaises(Rejected):Ledger(self.root/'missing.sqlite',self.private,self.public,{self.provider:self.secret})
        with self.assertRaises(FileExistsError):Ledger(self.ledger.path,self.private,self.public,{self.provider:self.secret},initialize=True)
    def test_consumed_permit_without_outcome_never_replays(self):
        self.dispatch()
        def stop(stage):
            if stage=='after-permit':raise Stop()
        with self.assertRaises(Stop):self.launch(hook=stop)
        with self.assertRaises((HostFault,FileNotFoundError)):replay(self.state,self.identity,self.cfg,self.public,self.ledger.handle)
        state=self.check();self.assertEqual(state['consumed'],1);self.assertEqual(state['accepted'],0);self.assertEqual(state['workers'][0]['phase'],'PERMITTED')

    def test_malformed_prepared_header_cannot_create_acceptance(self):
        self.dispatch();captured=[]
        def malformed(packet):
            import hmac
            req=decode(decode(packet)['payload'])
            if req['op']=='SUBMIT':
                pe=decode(req['data']['prepared_event']);pe['unexpected']=1;req['data']['prepared_event']=encode(pe)
                raw=encode(req);packet=encode({'payload':raw,'mac':hmac.digest(self.secret,raw,'sha256')})
                reply=self.ledger.handle(packet);captured.append(verify(reply,self.public,self.cfg['public_digest'])['status']);return reply
            return self.ledger.handle(packet)
        with self.assertRaises(Rejected):self.launch(transport=malformed)
        self.assertEqual(captured,['REJECTED']);self.assertEqual(self.check()['accepted'],0)
        self.assertEqual(replay(self.state,self.identity,self.cfg,self.public,self.ledger.handle)['status'],'ACCEPTED')
    def test_wrong_dispatch_object_reference_is_denied(self):
        captured=[]
        def wrong(packet):
            import hmac
            req=decode(decode(packet)['payload']);pack=req['data'];e=decode(pack['events'][0]);v=decode(pack['objects'][e['payload_ref'].hex()]);v['input_ref']=bytes(32)
            raw=encode(v);pack['objects'][sha(raw).hex()]=raw;e['payload_ref']=sha(raw);pack['events'][0]=encode(e)
            raw=encode(req);packet=encode({'payload':raw,'mac':hmac.digest(self.secret,raw,'sha256')});reply=self.ledger.handle(packet);captured.append(verify(reply,self.public,self.cfg['public_digest'])['status']);return reply
        with self.assertRaises(Rejected):dispatch(self.delivery,self.c,self.identity,self.artifact,[self.input],self.cfg,self.public,self.state,wrong)
        self.assertEqual(captured,['DENY']);self.assertEqual(self.check()['consumed'],0)

if __name__=='__main__':unittest.main()
