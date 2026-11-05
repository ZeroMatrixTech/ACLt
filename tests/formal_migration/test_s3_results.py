# SPDX-License-Identifier: Apache-2.0
import copy
import json
import shutil
from pathlib import Path
import tempfile
import unittest
from tools.formal_migration import foundation as f, policy as p, s2, s2_fixture as fixture
from tools.formal_migration import s2_evidence as evidence, s3_results as s3
from tools.verification_profile import codec as c
ROOT = Path(__file__).resolve().parents[2]


class S3ResultsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.keys = Path(cls.tmp.name) / 'keys'
        cls.cfg, bundles = fixture.build(ROOT, cls.keys, b'x' * 32, count=1)
        cls.old_bundle = bundles[0]
        cls.bundle = s3.bind_bundle(cls.old_bundle)
        cls.rid = p.bundle(cls.bundle)
        cls.cfg['allowed_receipts'] = [cls.rid]
        cls.ledger = s2.Ledger(Path(cls.tmp.name) / 'ledger.db', cls.cfg,
                              cls.keys / 'issuer.pem', clock=lambda: 3000, create=True)
        def call(role, op, body):
            record = cls.cfg['requester'] if role == 'requester' else cls.cfg['providers'][role.upper()]
            req = s2.request(cls.cfg, cls.keys / (role + '.pem'), f.principal_digest(record), op, body, 3000)
            return s2.check_response(cls.cfg, req, cls.ledger.handle(c.encode(req)))['result']
        task = call('requester', 'CREATE', dict(bundle=cls.bundle,
                    receipt_signature=fixture.receipt_sign(cls.keys / 'requester.pem', cls.bundle)))
        leases = {}
        for role in s2.ROLES:
            leases[role] = call(role.lower(), 'ACTIVATE', dict(receipt=cls.rid,
                          assignment=task['leases'][role]['proposal']['assignment'], epoch=1))
        cls.active = evidence.export(cls.ledger)
        for i, role in enumerate(s2.ROLES):
            lease = leases[role]
            call(role.lower(), 'CONSUME', dict(receipt=cls.rid, assignment=lease['proposal']['assignment'],
                 epoch=1, capability=lease['capability'], intent=bytes([i+1])*32))
        cls.snapshot = evidence.export(cls.ledger)
        cls.cp = cls.snapshot['checkpoint']
        fenced_path = Path(cls.tmp.name) / 'fenced.db'
        shutil.copyfile(cls.ledger.path, fenced_path)
        fenced_ledger = s2.Ledger(fenced_path, cls.cfg, cls.keys / 'issuer.pem', clock=lambda:5000)
        req = s2.request(cls.cfg, cls.keys / 'requester.pem', f.principal_digest(cls.cfg['requester']),
                         'FENCE', dict(receipt=cls.rid), 5000)
        fenced_ledger.handle(c.encode(req))
        cls.fenced = evidence.export(fenced_ledger)
        cls.outcome = c.encode(dict(outcome='OK', gas_used=9000, output=b'fixed stats output'))
        cls.results = [c.encode(s3.sign_result(cls.cfg, cls.snapshot, cls.cp, cls.rid, role,
                       cls.outcome, cls.keys / (role.lower() + '.pem'))) for role in s2.ROLES]

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def replay(self, results=None, snapshot=None, checkpoint=None, receipt=None):
        return s3.replay_pair(self.cfg, self.snapshot if snapshot is None else snapshot,
                             self.cp if checkpoint is None else checkpoint,
                             self.rid if receipt is None else receipt,
                             self.results if results is None else results)

    def resign(self, value, role=None):
        body = {k:v for k,v in value.items() if k != 'signature'}
        value['signature'] = s2.sign(self.keys / ((role or value['role']).lower() + '.pem'), s3.SCHEMA + '/RESULT', body)
        return c.encode(value)

    def test_bound_profile_changes_receipt_without_mutation(self):
        self.assertNotEqual(self.rid, p.bundle(self.old_bundle))
        self.assertEqual(self.old_bundle['inputs'], self.bundle['inputs'])
        self.assertEqual(s3.bind_bundle(self.bundle), self.bundle)
        self.assertEqual(s3.bundle_profile(self.bundle), s3.check_profile(s3.profile()))

    def test_frozen_profile_wire_vector(self):
        vector = json.loads((ROOT / 'tests/formal_migration/audit-result-vectors.json').read_text())
        self.assertEqual(c.encode(s3.profile()).hex(), vector['profile_cbor_hex'])
        self.assertEqual(s3.check_profile(s3.profile()).hex(), vector['profile_digest'])
        self.assertEqual(len(s3.EVENTS), 13)
        self.assertEqual(len(set(s3.EVENTS)), 13)
        self.assertNotIn('ACCEPT', s3.RULES)
        self.assertEqual(set(s3.profile()['reachable_terminals']), set(p.PROCESS_TERMINALS))

    def test_profile_rejects_bounded_claim_null_and_reordered_rules(self):
        edits = [lambda v:v.update(method='REEXEC_BOUNDED'), lambda v:v.update(verified_claim_spec=None),
                 lambda v:v.update(eligibility_snapshot=b'x'*32), lambda v:v.update(B=0,Q=1),
                 lambda v:v['rules'].reverse(), lambda v:v['failure_mapping'].pop(),
                 lambda v:v['failure_mapping'].append(v['failure_mapping'][0]),
                 lambda v:v.update(min_reexecutions=True), lambda v:v.update(min_reexecutions=2),
                 lambda v:v.update(terminal='TRUSTED'), lambda v:v['failure_mapping'][0].update(outcome='ACCEPT')]
        for edit in edits:
            value=s3.profile();edit(value)
            with self.subTest(value=value),self.assertRaises((c.CodecError,TypeError)):
                s3.check_profile(value)

    def test_old_placeholder_contract_cannot_be_reused(self):
        with self.assertRaises(c.CodecError):s3.bundle_profile(self.old_bundle)

    def test_matching_pair_is_concordance_only_and_order_independent(self):
        before=self.ledger.state();report=self.replay()
        self.assertEqual(report,self.replay(list(reversed(self.results))))
        self.assertEqual(report['outcome'],'CONCORDANT')
        self.assertFalse(report['correctness_claim'])
        self.assertFalse(report['decision_committed'])
        self.assertFalse(report['entitlement_created'])
        self.assertEqual(self.ledger.state(),before)
        self.assertEqual(before['held'],17)

    def test_valid_resigned_disagreement_is_accepted_as_discordant(self):
        other=c.decode(self.results[1]);obj=c.decode(other['outcome']);obj['output']=b'other';other['outcome']=c.encode(obj)
        report=self.replay([self.results[0],self.resign(other)])
        self.assertEqual((report['event'],report['outcome']),('NEGATIVE','DISCORDANT'))

    def test_gas_is_part_of_exact_comparison(self):
        other=c.decode(self.results[1]);obj=c.decode(other['outcome']);obj['gas_used']+=1;other['outcome']=c.encode(obj)
        self.assertEqual(self.replay([self.results[0],self.resign(other)])['outcome'],'DISCORDANT')

    def test_both_signed_results_required_no_duplicate_role(self):
        for values in ([],self.results[:1],self.results*2,[self.results[0]]*2):
            with self.subTest(count=len(values)),self.assertRaises(c.CodecError):self.replay(values)

    def test_wrong_signer_and_signature_tamper_rejected(self):
        value=c.decode(self.results[0]);wrong=self.resign(value,'AUDITOR')
        with self.assertRaises(c.CodecError):self.replay([wrong,self.results[1]])
        value=c.decode(self.results[0]);value['signature']=b'\0'*256
        with self.assertRaises(c.CodecError):self.replay([c.encode(value),self.results[1]])

    def test_all_binding_changes_rejected_even_after_resigning(self):
        changes=dict(schema='ACLt/FM/S2/1',genesis=b'z'*32,receipt=b'z'*32,profile=b'z'*32,
                     provider=b'z'*32,assignment=b'z'*32,epoch=2,intent=b'z'*32,consume_event=b'z'*32)
        before=self.ledger.state()
        for key,val in changes.items():
            value=c.decode(self.results[0]);value[key]=val
            with self.subTest(field=key),self.assertRaises(c.CodecError):
                self.replay([self.resign(value),self.results[1]])
        self.assertEqual(self.ledger.state(),before)

    def test_missing_unknown_fields_and_bad_cbor_rejected(self):
        for key in s3.RESULT_FIELDS:
            v=c.decode(self.results[0]);del v[key]
            with self.subTest(missing=key),self.assertRaises(c.CodecError):self.replay([c.encode(v),self.results[1]])
        for key,val in [('terminal','TRUSTED'),('fee',7),('claim',{}),('eligibility_snapshot',{})]:
            v=c.decode(self.results[0]);v[key]=val
            with self.subTest(extra=key),self.assertRaises(c.CodecError):self.replay([self.resign(v),self.results[1]])
        with self.assertRaises(c.CodecError):self.replay([self.results[0]+b'\x00',self.results[1]])

    def test_host_fault_trap_overflow_and_unknown_outcome_fail_closed(self):
        objects=[dict(outcome='HOST_FAULT',gas_used=0,output=b''),dict(outcome='TRAP_GAS_EXHAUSTED',gas_used=9000),
                 dict(outcome='OK',gas_used=True,output=b''),dict(outcome='OK',gas_used=50000001,output=b''),
                 dict(outcome='OK',gas_used=9000,output=b'x'*4097),dict(outcome='OK',gas_used=9000,output='text')]
        for obj in objects:
            value=c.decode(self.results[0]);value['outcome']=c.encode(obj)
            with self.subTest(obj=str(obj)[:90]),self.assertRaises(c.CodecError):
                self.replay([self.resign(value),self.results[1]])

    def test_active_without_consume_is_not_result_authorization(self):
        with self.assertRaises(c.CodecError):
            self.replay(snapshot=self.active,checkpoint=self.active['checkpoint'])

    def test_missing_wrong_and_old_checkpoint_rejected(self):
        with self.assertRaises(c.CodecError):s3.context(self.cfg,self.snapshot,None,self.rid)
        wrong=copy.deepcopy(self.cp);wrong['head']=b'z'*32
        with self.assertRaises(c.CodecError):self.replay(checkpoint=wrong)
        with self.assertRaises(c.CodecError):self.replay(snapshot=self.active)
        with self.assertRaises(c.CodecError):self.replay(receipt=b'z'*32)

    def test_tampered_snapshot_and_truncated_chain_rejected(self):
        for edit in (lambda v:v['events'].pop(),lambda v:v.update(state=c.encode({})),
                     lambda v:v.update(signature=b'\0'*256)):
            value=copy.deepcopy(self.snapshot);edit(value)
            with self.assertRaises(c.CodecError):self.replay(snapshot=value)

    def test_repeat_replay_does_not_allocate_right_or_change_events(self):
        before=evidence.export(self.ledger);a=self.replay();b=self.replay()
        self.assertEqual(a,b);self.assertEqual(before,evidence.export(self.ledger))

    def test_fenced_lease_cannot_be_reused_for_result_replay(self):
        with self.assertRaises(c.CodecError):
            self.replay(snapshot=self.fenced,checkpoint=self.fenced['checkpoint'])

    def test_new_receipt_cannot_keep_old_requester_signature(self):
        old_signature=fixture.receipt_sign(self.keys / 'requester.pem',self.old_bundle)
        ledger=s2.Ledger(Path(self.tmp.name) / 'old-signature.db',self.cfg,self.keys / 'issuer.pem',clock=lambda:3000,create=True)
        req=s2.request(self.cfg,self.keys / 'requester.pem',f.principal_digest(self.cfg['requester']),
                       'CREATE',dict(bundle=self.bundle,receipt_signature=old_signature),3000)
        before=ledger.state()
        with self.assertRaises(c.CodecError):ledger.handle(c.encode(req))
        self.assertEqual(ledger.state(),before)
