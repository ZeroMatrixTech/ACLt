# SPDX-License-Identifier: Apache-2.0
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest

from tools.formal_migration import foundation as f, policy as p, s2, s2_evidence, s2_fixture
from tools.formal_migration import s3_authority as s3
from tools.verification_profile import codec as c

ROOT = Path(__file__).resolve().parents[2]


class AuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.keys = Path(cls.temp.name) / 'keys'
        cls.cfg, bundles = s2_fixture.build(ROOT, cls.keys, b'x' * 32, count=2)
        cls.bundle = s3.bind_bundle(bundles[0])
        cls.rid = p.bundle(cls.bundle)
        cls.second_bundle = s3.bind_bundle(bundles[1])
        cls.cfg['allowed_receipts'] = [cls.rid, p.bundle(cls.second_bundle)]
        cls.signature = s2_fixture.receipt_sign(cls.keys / 'requester.pem', cls.bundle)

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.now = 3000
        self.deadline = self.bundle['receipt']['execution']['deadline']
        self.ledger = s3.Ledger(Path(temp.name) / 'ledger', self.cfg, self.keys / 'issuer.pem',
                                clock=lambda: self.now, create=True)
        self.call('requester', 'CREATE', dict(bundle=self.bundle, receipt_signature=self.signature))
        self.bindings = {}
        for role in s2.ROLES:
            proposal = s2.proposal(self.cfg, self.rid, role, self.bundle)
            body = dict(receipt=self.rid, assignment=proposal['assignment'], epoch=1)
            active = self.call(role.lower(), 'ACTIVATE', body)
            self.call(role.lower(), 'CONSUME', dict(body, capability=active['capability'],
                                                  intent=b'i' * 32))
        snapshot = s2_evidence.export(self.ledger)
        task = self.ledger.state()['tasks'][self.rid.hex()]
        for role in s2.ROLES:
            self.bindings[role] = s3.role_binding(task, snapshot['events'], role)

    def request(self, role, op, body):
        record = self.cfg['requester'] if role == 'requester' else self.cfg['providers'][role.upper()]
        return s2.request(self.cfg, self.keys / (role + '.pem'), f.principal_digest(record),
                          op, body, self.now)

    def send(self, request):
        return s2.check_response(self.cfg, request, self.ledger.handle(c.encode(request)))['result']

    def call(self, role, op, body):
        return self.send(self.request(role, op, body))

    def start(self, role):
        return self.call(role.lower(), 'S3_START', self.bindings[role])['start']

    def result_body(self, role, start, output=b'answer'):
        return dict(self.bindings[role], start=start,
                    outcome=c.encode(dict(outcome='OK', gas_used=9000, output=output)))

    def finalize(self):
        return self.call('requester', 'S3_FINALIZE', dict(receipt=self.rid))

    def test_pair_replays_unique_terminal_and_retains_funds(self):
        for role in s2.ROLES:
            body = self.result_body(role, self.start(role))
            first = self.call(role.lower(), 'S3_RESULT', body)
            self.assertEqual(self.call(role.lower(), 'S3_RESULT', body), first)
        before = self.ledger.state()['held']
        decision = self.finalize()
        self.assertEqual(decision['method_observation'], 'CONCORDANT')
        self.assertEqual(decision['terminal'], 'UNRESOLVED')
        seq = self.ledger.replay()['seq']
        self.assertEqual(self.finalize(), decision)
        self.assertEqual(self.ledger.replay()['seq'], seq)
        self.assertEqual(self.ledger.state()['held'], before)
        snapshot = s2_evidence.export(self.ledger)
        self.assertEqual(s3.verify_snapshot(self.cfg, snapshot, snapshot['checkpoint'])['status'], 'PASS')
        with self.assertRaises(c.CodecError):
            s2_evidence.verify(self.cfg, snapshot)

    def test_validation_crossing_deadline_rejects_atomically(self):
        body = self.result_body('AUDITOR', self.start('AUDITOR'))
        self.now = self.deadline - 1
        req = self.request('auditor', 'S3_RESULT', body)
        before = self.ledger.state()
        readings = iter((self.now, self.deadline))
        self.ledger.clock = lambda: next(readings)
        with self.assertRaisesRegex(c.CodecError, 'deadline'):
            self.send(req)
        self.assertEqual(self.ledger.state(), before)

    def test_hostfault_conflict_does_not_displace_first_result(self):
        start = self.start('EXECUTOR')
        body = self.result_body('EXECUTOR', start)
        first = self.call('executor', 'S3_RESULT', body)
        for reason in ('IO', 'RESOURCE', 'INTERRUPTED'):
            conflict = self.call('executor', 'S3_HOST_FAULT',
                                 dict(self.bindings['EXECUTOR'], start=start, reason=reason))
            self.assertEqual(conflict, dict(conflict=True, accepted=first['identity']))
        self.assertEqual(self.call('executor', 'S3_RESULT', body), first)
        audit = self.ledger.state()['tasks'][self.rid.hex()]['audit']
        self.assertEqual(len(audit['conflicts']), 1)
        self.assertEqual(audit['accepted_cost'], self.bundle['funding']['execution_limit'])

    def test_missing_start_and_revoked_start_invalidate(self):
        self.start('AUDITOR')
        self.call('requester', 'S3_REVOKE', dict(receipt=self.rid))
        decision = self.finalize()
        self.assertEqual(decision['assumption_evaluation']['status'], 'INVALIDATING')
        self.assertEqual(decision['assumption_evaluation']['unknown_starts'], ['EXECUTOR'])
        self.assertEqual(decision['condition'], 'VERIFICATION_INVALIDATING')

    def test_concurrent_finalize_has_one_event_and_returns_same_decision(self):
        for role in s2.ROLES:
            self.start(role)
        self.now = self.deadline
        seq = self.ledger.replay()['seq']
        with ThreadPoolExecutor(max_workers=2) as pool:
            decisions = list(pool.map(lambda _: self.finalize(), range(2)))
        self.assertEqual(decisions[0], decisions[1])
        self.assertEqual(decisions[0]['terminal'], 'EXPIRED')
        self.assertEqual(self.ledger.replay()['seq'], seq + 1)

    def test_result_retry_after_terminal_keeps_original_receipt(self):
        body = self.result_body('AUDITOR', self.start('AUDITOR'))
        first = self.call('auditor', 'S3_RESULT', body)
        self.now = self.deadline
        self.finalize()
        self.assertEqual(self.call('auditor', 'S3_RESULT', body), first)
        with self.assertRaises(c.CodecError):
            self.call('auditor', 'S3_RESULT', dict(body, epoch=2))

    def test_commit_then_lost_reply_reopens_with_original_result(self):
        body = self.result_body('AUDITOR', self.start('AUDITOR'))
        req = self.request('auditor', 'S3_RESULT', body)
        def fail(point):
            if point == 'AFTER_COMMIT':
                raise OSError('lost reply')
        self.ledger.hook = fail
        with self.assertRaisesRegex(OSError, 'lost reply'):
            self.send(req)
        self.ledger = s3.Ledger(self.ledger.path, self.cfg, self.keys / 'issuer.pem',
                                clock=lambda: self.now)
        first = self.send(req)
        self.assertEqual(self.call('auditor', 'S3_RESULT', body), first)

    def test_unstarted_and_wrong_signer_results_do_not_mutate(self):
        before = self.ledger.state()
        body = self.result_body('AUDITOR', b'x' * 32)
        with self.assertRaisesRegex(c.CodecError, 'start reference'):
            self.call('auditor', 'S3_RESULT', body)
        with self.assertRaisesRegex(c.CodecError, 'signer binding'):
            self.call('executor', 'S3_START', self.bindings['AUDITOR'])
        self.assertEqual(self.ledger.state(), before)

    def test_discordant_pair_and_exact_role_budget(self):
        for role in s2.ROLES:
            self.call(role.lower(), 'S3_RESULT',
                      self.result_body(role, self.start(role), role.encode()))
        task = self.ledger.state()['tasks'][self.rid.hex()]
        self.assertEqual(task['audit']['accepted_cost'],
                         sum(task['bundle']['funding'][bucket] for bucket in s3.BUCKET.values()))
        self.assertLessEqual(task['audit']['accepted_cost'], task['funding_held'])
        self.assertEqual(self.finalize()['method_observation'], 'DISCORDANT')

    def test_hostfault_first_occupies_slot_without_cost(self):
        start = self.start('EXECUTOR')
        report = dict(self.bindings['EXECUTOR'], start=start, reason='IO')
        accepted = self.call('executor', 'S3_HOST_FAULT', report)
        self.assertEqual(accepted['cost'], 0)
        rejected = self.call('executor', 'S3_RESULT', self.result_body('EXECUTOR', start))
        self.assertEqual(rejected, dict(conflict=True, accepted=accepted['identity']))

    def settlement_call(self, op='S3_SETTLE'):
        return self.call('requester', op, dict(receipt=self.rid))

    def test_settlement_requires_terminal_and_requester(self):
        before = self.ledger.state()
        self.assertEqual(self.settlement_call('S3_SETTLEMENT_STATUS')['status'],
                         'AWAITING_TERMINAL')
        with self.assertRaisesRegex(c.CodecError, 'committed terminal'):
            self.settlement_call()
        with self.assertRaisesRegex(c.CodecError, 'requester role'):
            self.call('executor', 'S3_SETTLE', dict(receipt=self.rid))
        self.assertEqual(self.ledger.state(), before)

    def test_discordant_results_get_policy_fees_and_refund(self):
        for role in s2.ROLES:
            self.call(role.lower(), 'S3_RESULT',
                      self.result_body(role, self.start(role), role.encode()))
        decision = self.finalize()
        self.assertEqual(decision['method_observation'], 'DISCORDANT')
        before = self.ledger.state()
        plan = p.quote(dict(bundle=self.bundle, terminal=decision['terminal'],
                            executor='COMPLETE', auditor='COMPLETE', storage='MISSING'))
        result = self.settlement_call()
        by_kind = {right['kind']: right for right in result['entitlements']}
        for role, kind in (('EXECUTOR', 'execution_fee'), ('AUDITOR', 'verification_fee')):
            self.assertEqual(by_kind[kind]['amount'], int(plan['amounts'][kind]))
            self.assertEqual(by_kind[kind]['beneficiary'],
                             f.principal_digest(self.cfg['providers'][role]))
        self.assertEqual(by_kind['refund']['beneficiary'], f.principal_digest(self.cfg['requester']))
        self.assertEqual(result['refund'], int(plan['refund']))
        self.assertEqual(result['decision_digest'], s2.h(decision))
        self.assertEqual(result['policy'], self.bundle['receipt']['settlement_ref'])
        self.assertEqual(result['paid'] + result['refund'], before['held'])
        self.assertEqual(len({right['key'] for right in by_kind.values()}), len(by_kind))
        after = self.ledger.state()
        self.assertEqual(after['held'], 0)
        self.assertEqual(after['free'], before['free'] + result['refund'])
        self.assertEqual(after['free'] + after['held'] + result['paid'], self.cfg['balance'])
        self.assertEqual(self.call('requester', 'QUERY', dict(receipt=self.rid))['settlement'], result)
        snapshot = s2_evidence.export(self.ledger)
        self.assertEqual(s3.verify_snapshot(self.cfg, snapshot, snapshot['checkpoint'])['status'],
                         'PASS')

    def test_missing_and_hostfault_refund_all_held_funds(self):
        start = self.start('EXECUTOR')
        self.start('AUDITOR')
        self.call('executor', 'S3_HOST_FAULT',
                  dict(self.bindings['EXECUTOR'], start=start, reason='IO'))
        self.now = self.deadline
        self.assertEqual(self.finalize()['terminal'], 'EXPIRED')
        result = self.settlement_call()
        self.assertEqual(result['fulfillment'],
                         dict(executor='HOST_FAULT', auditor='MISSING', storage='MISSING'))
        self.assertEqual(result['paid'], 0)
        self.assertEqual(result['refund'], self.bundle['funding']['total_limit'])
        self.assertEqual([right['kind'] for right in result['entitlements']], ['refund'])

    def test_never_reserved_receipt_cannot_generate_refund(self):
        path = self.ledger.path.with_name('unfunded')
        self.ledger = s3.Ledger(path, self.cfg, self.keys / 'issuer.pem',
                                clock=lambda: self.now, create=True)
        self.call('requester', 'CREATE', dict(bundle=self.bundle, receipt_signature=self.signature))
        self.now = self.deadline
        self.finalize()
        result = self.settlement_call()
        self.assertEqual((result['paid'], result['refund'], result['entitlements']), (0, 0, []))
        self.assertEqual(self.ledger.state()['free'], self.cfg['balance'])

    def test_concurrent_settlement_and_status_have_only_one_allocation_event(self):
        self.now = self.deadline
        self.finalize()
        seq = self.ledger.replay()['seq']
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.settlement_call(), range(2)))
        self.assertEqual(results[0], results[1])
        status = self.settlement_call('S3_SETTLEMENT_STATUS')
        self.assertEqual(status, dict(status='COMMITTED', settlement=results[0]))
        self.assertEqual(self.ledger.replay()['seq'], seq + 1)

    def test_settlement_commit_boundary_recovers_by_query(self):
        self.now = self.deadline
        self.finalize()
        before = self.ledger.state()
        request = self.request('requester', 'S3_SETTLE', dict(receipt=self.rid))
        for boundary, expected_status in [('BEFORE_COMMIT', 'READY'), ('AFTER_COMMIT', 'COMMITTED')]:
            def fail(point):
                if point == boundary:
                    raise OSError(boundary)
            self.ledger.hook = fail
            with self.assertRaisesRegex(OSError, boundary):
                self.send(request)
            self.ledger = s3.Ledger(self.ledger.path, self.cfg, self.keys / 'issuer.pem',
                                    clock=lambda: self.now)
            recovered = self.settlement_call('S3_SETTLEMENT_STATUS')
            self.assertEqual(recovered['status'], expected_status)
            if expected_status == 'READY':
                self.assertEqual(self.ledger.state(), before)
        self.assertEqual(self.send(request), recovered['settlement'])
        self.assertEqual(self.settlement_call(), recovered['settlement'])
        self.assertEqual(self.ledger.state()['held'], 0)

    def test_settlement_rejects_client_selected_policy_amount_and_terminal(self):
        self.now = self.deadline
        self.finalize()
        before = self.ledger.state()
        for override in (dict(policy=b'\0' * 32), dict(amount=1), dict(terminal='TRUSTED')):
            with self.subTest(override=override), self.assertRaises(c.CodecError):
                self.call('requester', 'S3_SETTLE', dict(receipt=self.rid, **override))
        self.assertEqual(self.ledger.state(), before)

    def test_new_receipt_reserves_after_nonzero_prior_allocation(self):
        for role in s2.ROLES:
            self.call(role.lower(), 'S3_RESULT',
                      self.result_body(role, self.start(role)))
        self.finalize()
        first = self.settlement_call()
        self.assertGreater(first['paid'], 0)
        bundle = self.second_bundle
        rid = p.bundle(bundle)
        signature = s2_fixture.receipt_sign(self.keys / 'requester.pem', bundle)
        self.call('requester', 'CREATE', dict(bundle=bundle, receipt_signature=signature))
        assignment = s2.proposal(self.cfg, rid, 'EXECUTOR', bundle)['assignment']
        self.call('executor', 'ACTIVATE', dict(receipt=rid, assignment=assignment, epoch=1))
        state = self.ledger.state()
        self.assertEqual(state['held'], bundle['funding']['total_limit'])
        self.assertEqual(state['free'] + state['held'] + first['paid'], self.cfg['balance'])
        self.assertEqual(self.settlement_call(), first)
        self.ledger.replay()
