# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from unittest import mock

from tools.formal_migration import foundation as f, policy as p, s2, s2_evidence, s2_fixture
from tools.formal_migration import s2_worker, s3_authority as s3, s3_closure, s3_terminals as t
from tools.verification_profile import codec as c

ROOT = Path(__file__).resolve().parents[2]
# Reserving one Receipt (17) leaves 5 units, so a second Receipt is under-funded.
BALANCE = 22
# SHA-256 of canonical contract bytes on main 9f915c3, before the opt-in fields existed.
OLD_PROFILE_DIGESTS = {
    'OK_ONLY': '7f196206e994e1168b4dac84bad249768747b63bd49cd8ce94d9b68402bbd412',
    'TASK_TRAPS': '5dfc30713f225f0b3084909f35cc15d852c5195ebf7810ae5805a6419594872f',
}


def terminal_contract(observer_der):
    return dict(task_traps=True, closure_observer_der=observer_der, rpr_entry=True, funding_boundary=True)


class TerminalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.keys = Path(cls.temp.name) / 'keys'
        cls.cfg, bundles = s2_fixture.build(ROOT, cls.keys, b'x' * 32, count=4, balance=BALANCE)
        cls.observer = Path(cls.temp.name) / 'observer.pem'
        cls.observer_der = s2_fixture.keypair(cls.observer)
        full = terminal_contract(cls.observer_der)
        cls.bundles = [s3.bind_bundle(bundles[0], **full), s3.bind_bundle(bundles[1], **full),
                       s3.bind_bundle(bundles[2]),
                       s3.bind_bundle(bundles[3], closure_observer_der=cls.observer_der)]
        cls.cfg['allowed_receipts'] = [p.bundle(b) for b in cls.bundles]
        cls.signatures = [s2_fixture.receipt_sign(cls.keys / 'requester.pem', b) for b in cls.bundles]

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.now = 3000
        self.ledger = s3.Ledger(Path(temp.name) / 'ledger', self.cfg, self.keys / 'issuer.pem',
                                clock=lambda: self.now, create=True)
        self.use(0)

    def use(self, index):
        self.index = index
        self.bundle = self.bundles[index]
        self.rid = p.bundle(self.bundle)
        self.deadline = self.bundle['receipt']['execution']['deadline']

    def request(self, role, op, body):
        record = self.cfg['requester'] if role == 'requester' else self.cfg['providers'][role.upper()]
        return s2.request(self.cfg, self.keys / (role + '.pem'), f.principal_digest(record),
                          op, body, self.now)

    def send(self, request):
        return s2.check_response(self.cfg, request, self.ledger.handle(c.encode(request)))['result']

    def call(self, role, op, body):
        return self.send(self.request(role, op, body))

    def create(self):
        self.call('requester', 'CREATE', dict(bundle=self.bundle,
                                              receipt_signature=self.signatures[self.index]))

    def lease_body(self, role):
        proposal = s2.proposal(self.cfg, self.rid, role, self.bundle)
        return dict(receipt=self.rid, assignment=proposal['assignment'], epoch=1)

    def activate(self, role):
        return self.call(role.lower(), 'ACTIVATE', self.lease_body(role))

    def consume(self, role):
        active = self.activate(role)
        self.call(role.lower(), 'CONSUME', dict(self.lease_body(role), capability=active['capability'],
                                                 intent=role.encode().ljust(32, b'i')))

    def binding(self, role):
        task = self.ledger.state()['tasks'][self.rid.hex()]
        return s3.role_binding(task, s2_evidence.export(self.ledger)['events'], role)

    def descriptor(self, role):
        return t.entry_descriptor(self.cfg, self.bundle, self.rid, role)

    def entry(self, role):
        return self.call(role.lower(), 'S3_ENTRY', dict(self.binding(role), entry=self.descriptor(role)))['start']

    def result(self, role, start, output=b'answer'):
        body = dict(self.binding(role), start=start,
                    outcome=c.encode(dict(outcome='OK', gas_used=9000, output=output)))
        return self.call(role.lower(), 'S3_RESULT', body)

    def hostfault(self, role, start, reason='RESOURCE'):
        return self.call(role.lower(), 'S3_HOST_FAULT', dict(self.binding(role), start=start, reason=reason))

    def closure_body(self, start, key=None):
        statement = s3_closure.observation(self.cfg, self.binding('EXECUTOR'), start)
        signature = s2.sign(key or self.observer, s3_closure.SIGNATURE_DOMAIN, statement)
        return dict(receipt=self.rid, observation=statement, observer_signature=signature)

    def close(self, start, key=None):
        return self.call('requester', 'S3_CLOSE_EXECUTION', self.closure_body(start, key))

    def finalize(self):
        return self.call('requester', 'S3_FINALIZE', dict(receipt=self.rid))

    def settle(self):
        return self.call('requester', 'S3_SETTLE', dict(receipt=self.rid))

    def query(self):
        return self.call('requester', 'QUERY', dict(receipt=self.rid))

    def replay_public(self):
        snapshot = s2_evidence.export(self.ledger)
        self.assertEqual(s3.verify_snapshot(self.cfg, snapshot, snapshot['checkpoint'])['status'], 'PASS')

    def test_existing_contract_bytes_are_unchanged_and_options_are_explicit(self):
        for flags, digest in ((dict(), OLD_PROFILE_DIGESTS['OK_ONLY']),
                              (dict(task_traps=True), OLD_PROFILE_DIGESTS['TASK_TRAPS'])):
            self.assertEqual(hashlib.sha256(c.encode(s3.profile(**flags))).hexdigest(), digest)
        closure_only = s3.check_bundle(self.bundles[3])
        self.assertEqual(closure_only['start_source'], 'PINNED_PROVIDER_TEST_ENTRY_ATTESTATION')
        self.assertFalse({'rpr_entry', 'funding_boundary'} & set(closure_only))
        full = s3.check_bundle(self.bundles[0])
        self.assertEqual((full['start_source'], full['rpr_entry'], full['funding_boundary']),
                         (t.ENTRY_SOURCE, t.ENTRY_CONTRACT, t.FUNDING_CONTRACT))
        self.assertEqual(full['execution_closure'], s3_closure.CONTRACT)

    def test_verified_entry_replaces_self_attested_start(self):
        self.create()
        self.consume('EXECUTOR')
        self.assertEqual(self.query()['start_states'],
                         dict(EXECUTOR='AUTHORIZATION_CONSUMED', AUDITOR='NOT_CONSUMED'))
        before = self.ledger.state()
        with self.assertRaisesRegex(c.CodecError, 'verified RPR entry'):
            self.call('executor', 'S3_START', self.binding('EXECUTOR'))
        good = self.descriptor('EXECUTOR')
        for field, value in (('runtime_sha256', b'y' * 32), ('fuel', good['fuel'] - 1),
                             ('input_sha256', hashlib.sha256(b'other').digest()),
                             ('memory_pages', good['memory_pages'] + 1),
                             ('call_depth_limit', 9), ('role', 'AUDITOR'), ('rir_digest', b'r' * 32)):
            with self.subTest(field=field), self.assertRaisesRegex(c.CodecError, 'RPR entry binding'):
                self.call('executor', 'S3_ENTRY', dict(self.binding('EXECUTOR'), entry=dict(good, **{field: value})))
        self.assertEqual(self.ledger.state(), before)
        start = self.entry('EXECUTOR')
        self.assertEqual(self.entry('EXECUTOR'), start)
        self.assertEqual(self.query()['start_states']['EXECUTOR'], 'EXECUTION_STARTED')
        execution = self.bundle['receipt']['execution']
        self.assertEqual(t.invocation_args(good, '/bin/rt', 'a', 'i')[4:],
                         [str(execution['fuel']), str(execution['output_bytes_limit']), '8', '20000000',
                          str(execution['memory_bytes'] // 65536),
                          s2.proposal(self.cfg, self.rid, 'EXECUTOR', self.bundle)['rir_digest'].hex()])

    def test_entry_is_rejected_for_contracts_without_it(self):
        for index in (2, 3):
            with self.subTest(index=index):
                self.ledger = s3.Ledger(self.ledger.path.with_name(f'entry-{index}'), self.cfg,
                                        self.keys / 'issuer.pem', clock=lambda: self.now, create=True)
                self.use(index)
                self.create()
                self.consume('EXECUTOR')
                descriptor = self.descriptor('EXECUTOR')
                with self.assertRaisesRegex(c.CodecError, 'requires the entry contract'):
                    self.call('executor', 'S3_ENTRY', dict(self.binding('EXECUTOR'), entry=descriptor))
                self.assertNotIn('start_states', self.query())

    def test_consumed_without_entry_is_start_unknown_at_evaluation(self):
        self.create()
        self.consume('EXECUTOR')
        self.consume('AUDITOR')
        self.result('AUDITOR', self.entry('AUDITOR'))
        with self.assertRaisesRegex(c.CodecError, 'evidence still open'):
            self.finalize()
        self.now = self.deadline
        decision = self.finalize()
        self.assertEqual(decision['start_states'], dict(EXECUTOR='START_UNKNOWN', AUDITOR='EXECUTION_STARTED'))
        self.assertEqual(decision['assumption_evaluation']['causes'], ['START_UNDETERMINED'])
        self.assertEqual((decision['condition'], decision['terminal']),
                         ('VERIFICATION_INVALIDATING', 'UNRESOLVED'))
        self.assertEqual(decision['boundary']['resolved'], 'DEADLINE_REACHED')
        self.assertEqual(self.query()['start_states'], decision['start_states'])
        settled = self.settle()
        self.assertEqual((settled['fulfillment']['auditor'], settled['paid']),
                         ('COMPLETE', self.bundle['funding']['verification_limit']))
        self.replay_public()

    def test_self_report_does_not_close_and_observer_closure_is_failed(self):
        self.create()
        self.consume('EXECUTOR')
        start = self.entry('EXECUTOR')
        self.assertEqual(self.hostfault('EXECUTOR', start)['cost'], 0)
        with self.assertRaisesRegex(c.CodecError, 'evidence still open'):
            self.finalize()
        before = self.ledger.state()
        with self.assertRaises(c.CodecError):
            self.close(start, self.keys / 'executor.pem')
        self.assertEqual(self.ledger.state(), before)
        record = self.close(start)
        self.assertEqual((record['attempts_observed'], record['valid_submission_count']), (1, 0))
        self.assertEqual(self.close(start), record)
        with self.assertRaisesRegex(c.CodecError, 'source unavailable'):
            self.activate('AUDITOR')
        decision = self.finalize()
        self.assertEqual((decision['condition'], decision['terminal']), ('EXECUTION_FAILED', 'FAILED'))
        self.assertEqual(decision['start_states'], dict(EXECUTOR='EXECUTION_STARTED', AUDITOR='NOT_CONSUMED'))
        self.assertEqual(decision['execution_observation']['record'], record)
        settled = self.settle()
        self.assertEqual((settled['terminal'], settled['paid'], settled['refund']),
                         ('FAILED', 0, self.bundle['funding']['total_limit']))
        self.assertEqual(settled['fulfillment'], dict(executor='HOST_FAULT', auditor='MISSING', storage='MISSING'))
        self.assertEqual(self.ledger.state()['free'], BALANCE)
        self.replay_public()

    def test_closure_preconditions_fail_closed(self):
        cases = {
            'needs entry': lambda: (self.consume('EXECUTOR'), None)[1],
            'verification started': lambda: (self.consume('EXECUTOR'), self.consume('AUDITOR'), self.entry('EXECUTOR'))[2],
            'valid submission': lambda: (self.consume('EXECUTOR'), self.result('EXECUTOR', self.entry('EXECUTOR')))[1]['identity'],
        }
        for name, prepare in cases.items():
            with self.subTest(case=name):
                self.ledger = s3.Ledger(self.ledger.path.with_name(name.replace(' ', '-')), self.cfg,
                                        self.keys / 'issuer.pem', clock=lambda: self.now, create=True)
                self.create()
                start = prepare()
                task = self.ledger.state()['tasks'][self.rid.hex()]
                start = task['audit']['starts'].get('EXECUTOR', b's' * 32)
                before = self.ledger.state()
                with self.assertRaises(c.CodecError):
                    self.close(start)
                self.assertEqual(self.ledger.state(), before)

    def test_revocation_precedes_execution_failure(self):
        self.create()
        self.consume('EXECUTOR')
        self.close(self.entry('EXECUTOR'))
        self.call('requester', 'S3_REVOKE', dict(receipt=self.rid))
        decision = self.finalize()
        # Both conditions hold; the frozen rule order selects P1 before P5.
        conditions = dict(decision['conditions'])
        self.assertEqual((conditions['VERIFICATION_INVALIDATING'], conditions['EXECUTION_FAILED']), (True, True))
        self.assertEqual(decision['terminal'], 'UNRESOLVED')

    def test_underfunded_activation_records_boundary_and_blocks_evidence(self):
        self.create()
        self.activate('EXECUTOR')
        self.assertEqual(self.ledger.state()['free'], BALANCE - 17)
        self.use(1)
        self.create()
        request = self.request('executor', 'ACTIVATE', self.lease_body('EXECUTOR'))
        boundary = self.send(request)
        self.assertEqual(boundary, dict(funding_exhausted=True, receipt=self.rid, role='EXECUTOR',
                                        required=17, available=BALANCE - 17))
        seq = self.ledger.replay()['seq']
        self.assertEqual(self.send(request), boundary)
        self.assertEqual(self.ledger.replay()['seq'], seq)
        for role in ('EXECUTOR', 'AUDITOR'):
            with self.subTest(role=role), self.assertRaisesRegex(c.CodecError, 'funding boundary'):
                self.activate(role)
        state = self.ledger.state()
        self.assertEqual((state['held'], state['tasks'][self.rid.hex()]['funding_held']), (17, 0))
        decision = self.finalize()
        self.assertEqual((decision['condition'], decision['terminal']), ('BUDGET_EXHAUSTED', 'FUNDING_EXHAUSTED'))
        self.assertEqual(set(decision['boundary']['observation']), {'funding_event_ref'})
        settled = self.settle()
        self.assertEqual((settled['terminal'], settled['paid'], settled['refund'], settled['entitlements']),
                         ('FUNDING_EXHAUSTED', 0, 0, []))
        state = self.ledger.state()
        self.assertEqual(state['free'] + state['held'], BALANCE)
        self.replay_public()

    def test_funding_boundary_precedes_later_deadline_observation(self):
        self.create()
        self.activate('EXECUTOR')
        self.use(1)
        self.create()
        self.activate('EXECUTOR')
        self.now = self.deadline
        decision = self.finalize()
        self.assertEqual(set(decision['boundary']['observation']), {'funding_event_ref', 'deadline_event_ref'})
        self.assertEqual(decision['boundary']['resolved'], 'BUDGET_EXHAUSTED')
        self.assertEqual(decision['terminal'], 'FUNDING_EXHAUSTED')

    def test_boundary_reference_must_match_the_recorded_event(self):
        self.create()
        self.activate('EXECUTOR')
        self.use(1)
        self.create()
        self.activate('EXECUTOR')
        task = self.ledger.state()['tasks'][self.rid.hex()]
        events = s2_evidence.export(self.ledger)['events']
        self.assertEqual(t.resolve(task, events, self.now)[0], 'BUDGET_EXHAUSTED')
        moved = dict(task, audit=dict(task['audit'], funding_boundary=dict(task['audit']['funding_boundary'], seq=1)))
        self.assertEqual(t.resolve(moved, events, self.now)[0], 'VERIFICATION_INVALIDATING')
        self.assertEqual(t.resolve(task, events[:-1], self.now)[0], 'VERIFICATION_INVALIDATING')


class WorkerEntryTests(unittest.TestCase):
    """Worker adapter over an in-process authority; no socket and no real runtime."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        root = Path(cls.temp.name)
        raw = c.encode(dict(outcome='OK', gas_used=9000, output=b'answer'))
        digest = c.domain_hash('ACLt/RIR-0/ExecutionOutcome/1', raw).hex()
        cls.runtime = root / 'fake-runtime'
        cls.runtime.write_text(
            '#!/usr/bin/env python3\nimport json, sys\nfrom pathlib import Path\n'
            'Path(sys.argv[3]).with_name("argv.json").write_text(json.dumps(sys.argv[1:]))\n'
            'if sys.argv[-1] == "test-memory-fault":\n'
            '    print(json.dumps(dict(status="HOST_FAULT", code="HOST_RESOURCE_EXHAUSTED"))); sys.exit(3)\n'
            f'print(json.dumps(dict(status="TASK_OUTCOME", canonical_outcome_hex="{raw.hex()}", '
            f'outcome_digest="{digest}")))\n')
        cls.runtime.chmod(0o755)
        cls.keys = root / 'keys'
        cls.cfg, bundles = s2_fixture.build(ROOT, cls.keys, hashlib.sha256(cls.runtime.read_bytes()).digest(), count=1)
        cls.observer = root / 'observer.pem'
        cls.bundle = s3.bind_bundle(bundles[0], **terminal_contract(s2_fixture.keypair(cls.observer)))
        cls.rid = p.bundle(cls.bundle)
        cls.cfg['allowed_receipts'] = [cls.rid]
        cls.signature = s2_fixture.receipt_sign(cls.keys / 'requester.pem', cls.bundle)

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        self.ledger = s3.Ledger(self.dir / 'ledger', self.cfg, self.keys / 'issuer.pem',
                                clock=lambda: 3000, create=True)
        self.call('requester', 'CREATE', dict(bundle=self.bundle, receipt_signature=self.signature))
        proposal = s2.proposal(self.cfg, self.rid, 'EXECUTOR', self.bundle)
        self.call('executor', 'ACTIVATE', dict(receipt=self.rid, assignment=proposal['assignment'], epoch=1))
        patcher = mock.patch.object(s2_worker, 'rpc', lambda host, port, raw: self.ledger.handle(raw))
        patcher.start()
        self.addCleanup(patcher.stop)

    def call(self, role, op, body):
        record = self.cfg['requester'] if role == 'requester' else self.cfg['providers'][role.upper()]
        request = s2.request(self.cfg, self.keys / (role + '.pem'), f.principal_digest(record), op, body, 3000)
        return s2.check_response(self.cfg, request, self.ledger.handle(c.encode(request)))['result']

    def work(self, directory, hook=None, closure_fault=False):
        return s2_worker.run(self.cfg, self.bundle, 'EXECUTOR', self.keys / 'executor.pem', 'in-process', 0,
                             self.runtime, directory, 3000, hook, s3b=True, closure_fault=closure_fault)

    def states(self):
        return self.call('requester', 'QUERY', dict(receipt=self.rid))['start_states']

    def descriptor_args(self, directory):
        descriptor = t.entry_descriptor(self.cfg, self.bundle, self.rid, 'EXECUTOR')
        return descriptor, t.invocation_args(descriptor, self.runtime.resolve(), directory / 'artifact',
                                             directory / 'input')

    def test_runtime_argv_is_derived_from_the_verified_entry(self):
        directory = self.dir / 'work'
        self.assertEqual(self.work(directory)['status'], 'LOCAL_OBSERVATION_ONLY')
        descriptor, expected = self.descriptor_args(directory)
        self.assertEqual(json.loads((directory / 'argv.json').read_text()), expected[1:])
        self.assertEqual(c.decode((directory / 's3-start').read_bytes())['entry'], descriptor)
        self.assertEqual(self.states()['EXECUTOR'], 'EXECUTION_STARTED')
        self.assertEqual(self.call('executor', 'S3_RESULT', s2_worker.s3_result_body(directory))['kind'], 'S3_RESULT')
        with self.assertRaisesRegex(c.CodecError, 'completed task outcome'):
            s2_worker.s3_hostfault_body(directory, 'INTERRUPTED')

    def test_physical_fault_through_verified_entry_closes_execution(self):
        directory = self.dir / 'fault'
        observed = self.work(directory, closure_fault=True)
        self.assertEqual((observed['returncode'], c.decode(observed['core'])),
                         (3, dict(status='HOST_FAULT', code=s3_closure.FAULT)))
        _, expected = self.descriptor_args(directory)
        self.assertEqual(json.loads((directory / 'argv.json').read_text()), expected[1:] + ['test-memory-fault'])
        report = s2_worker.s3_hostfault_body(directory, 'RESOURCE')
        self.assertEqual(self.call('executor', 'S3_HOST_FAULT', report)['kind'], 'S3_HOST_FAULT')
        binding = s2_worker.s3_binding(directory)
        start = binding.pop('start')
        statement = s3_closure.observation(self.cfg, binding, start)
        body = dict(receipt=self.rid, observation=statement,
                    observer_signature=s2.sign(self.observer, s3_closure.SIGNATURE_DOMAIN, statement))
        self.assertEqual(self.call('requester', 'S3_CLOSE_EXECUTION', body)['valid_submission_count'], 0)
        self.assertEqual(self.call('requester', 'S3_FINALIZE', dict(receipt=self.rid))['terminal'], 'FAILED')

    def crash_at(self, point, directory):
        def hook(name):
            if name == point:
                raise OSError(point)
        with self.assertRaisesRegex(OSError, point):
            self.work(directory, hook)
        return self.work(directory)

    def test_interruption_before_guest_reports_stage_and_never_reinvokes(self):
        directory = self.dir / 'interrupted'
        again = self.crash_at('BEFORE_GUEST', directory)
        self.assertEqual(again, dict(status='UNKNOWN_NO_REEXECUTION', stage='INVOCATION_RECORDED'))
        self.assertFalse((directory / 'argv.json').exists())
        self.assertEqual(self.states()['EXECUTOR'], 'EXECUTION_STARTED')
        fault = self.call('executor', 'S3_HOST_FAULT', s2_worker.s3_hostfault_body(directory, 'INTERRUPTED'))
        self.assertEqual(fault['kind'], 'S3_HOST_FAULT')

    def test_interruption_after_consume_is_authorization_consumed(self):
        directory = self.dir / 'consumed'
        again = self.crash_at('AFTER_CONSUME', directory)
        self.assertEqual(again, dict(status='UNKNOWN_NO_REEXECUTION', stage='AUTHORIZATION_CONSUMED'))
        self.assertEqual(self.states()['EXECUTOR'], 'AUTHORIZATION_CONSUMED')
        self.assertFalse((directory / 's3-start').exists())


if __name__ == '__main__':
    unittest.main()
