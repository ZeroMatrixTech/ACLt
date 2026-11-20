# SPDX-License-Identifier: Apache-2.0
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wire import *
import ledger as writer
from ledger import Ledger
from audit import reduce
from fixtures import task


class FundingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keys = tempfile.TemporaryDirectory()
        cls.private, cls.public = create_keys(Path(cls.keys.name)/'keys')

    @classmethod
    def tearDownClass(cls): cls.keys.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.other = sha(b'other-payer'); self.payee = sha(b'payee')
        self.enrollment = {ZERO: b'a'*32, self.other: b'b'*32}
        self.ledger = Ledger(self.root/'ledger.sqlite', self.private, self.public, self.enrollment,
                             {ZERO: 100, self.other: 0, self.payee: 0})
        self.cfg = {'authority_id': self.ledger.authority, 'requester': ZERO, 'secret': b'a'*32, 'public_digest': self.ledger.pin}

    def call(self, op, data, cfg=None):
        cfg = cfg or self.cfg; packet = request(cfg, op, data)
        return response(packet, self.ledger.handle(packet), cfg, self.public)

    def freeze(self, cap=60, fee=20, nonce=0, payee=None):
        c, _, a, i = task(bytes([nonce])*16)
        p = policy(c, payee or self.payee, cap, fee)
        data = {'policy': p, 'commitment': c, 'artifact': a, 'input': i}
        r = self.call('FREEZE', data)
        return policy_id(p), data, r

    def audit(self):
        bundle, anchor = self.ledger.export()
        return reduce(bundle, anchor, self.public, self.ledger.pin, sha(anchor))

    def test_freeze_only_does_not_move_funds(self):
        _, _, r = self.freeze(); self.assertEqual(r['status'], 'FROZEN')
        a = self.audit(); self.assertEqual((a['available'], a['reserved']), (100, 0))

    def test_reserve_uses_frozen_cap_and_conserves(self):
        pid, _, _ = self.freeze(); r = self.call('RESERVE', {'policy_id': pid})
        body = verify(r['result']['receipt'], self.public, self.ledger.pin)
        self.assertEqual(body['amount'], 60); self.assertEqual(r['status'], 'RESERVED')
        a = self.audit(); self.assertEqual((a['available'], a['reserved'], a['reservations']), (40, 60, 1))

    def test_duplicate_new_nonce_returns_same_receipt(self):
        pid, _, _ = self.freeze(); one = self.call('RESERVE', {'policy_id': pid}); two = self.call('RESERVE', {'policy_id': pid})
        self.assertEqual(two['status'], 'DUPLICATE'); self.assertEqual(one['result'], two['result'])
        self.assertEqual(self.audit()['reserved'], 60)

    def test_exact_transport_packet_replay_does_not_debit_twice(self):
        pid, _, _ = self.freeze(); packet = request(self.cfg, 'RESERVE', {'policy_id': pid})
        one = response(packet, self.ledger.handle(packet), self.cfg, self.public)
        two = response(packet, self.ledger.handle(packet), self.cfg, self.public)
        self.assertEqual(one['result'], two['result']); self.assertEqual(self.audit()['reserved'], 60)

    def test_insufficient_is_not_partial_or_implicit_credit(self):
        pid, _, _ = self.freeze(101, 20); self.assertEqual(self.call('RESERVE', {'policy_id': pid})['status'], 'INSUFFICIENT')
        self.assertEqual(self.call('STATUS', {'policy_id': pid})['status'], 'UNRESERVED')
        a = self.audit(); self.assertEqual((a['available'], a['reserved']), (100, 0))

    def test_competing_tasks_cannot_overreserve(self):
        p1, _, _ = self.freeze(70, 20, 1); p2, _, _ = self.freeze(70, 20, 2)
        with ThreadPoolExecutor(2) as pool:
            statuses = list(pool.map(lambda p: self.call('RESERVE', {'policy_id': p})['status'], [p1, p2]))
        self.assertEqual(sorted(statuses), ['INSUFFICIENT', 'RESERVED'])
        a = self.audit(); self.assertEqual((a['available'], a['reserved']), (30, 70))

    def test_concurrent_identical_requests_one_encumbrance(self):
        pid, _, _ = self.freeze(40, 10)
        with ThreadPoolExecutor(4) as pool:
            results = list(pool.map(lambda _: self.call('RESERVE', {'policy_id': pid}), range(4)))
        self.assertEqual(sum(r['status'] == 'RESERVED' for r in results), 1)
        self.assertEqual(len({r['result']['receipt'] for r in results}), 1)
        self.assertEqual(self.audit()['reservations'], 1)

    def test_policy_immutable_even_before_reserve(self):
        pid, original, _ = self.freeze()
        self.assertEqual(self.call('FREEZE', original)['status'], 'DUPLICATE')
        for change in [{'authorized_cap': 50}, {'success_fee': 10}, {'payee': self.other}]:
            changed = {**original, 'policy': encode({**decode(original['policy']), **change})}
            self.assertEqual(self.call('FREEZE', changed)['status'], 'CONFLICT')
        self.call('RESERVE', {'policy_id': pid}); self.assertEqual(self.audit()['reserved'], 60)

    def test_wrong_task_input_is_rejected(self):
        _, data, _ = self.freeze(); data['input'] = b'wrong'
        with self.assertRaises(Rejected): self.call('FREEZE', data)
        self.assertEqual(self.audit()['reserved'], 0)

    def test_wrong_payer_cannot_freeze_or_reserve(self):
        pid, data, _ = self.freeze(); cfg = {**self.cfg, 'requester': self.other, 'secret': b'b'*32}
        with self.assertRaises(Rejected): self.call('FREEZE', data, cfg)
        self.assertEqual(self.call('RESERVE', {'policy_id': pid}, cfg)['status'], 'DENIED')
        self.assertEqual(self.audit()['reserved'], 0)

    def test_bad_mac_and_wrong_deployment_rejected(self):
        for cfg in [{**self.cfg, 'secret': bytes(32)}, {**self.cfg, 'authority_id': bytes(16)}]:
            with self.assertRaises(Rejected): self.call('BALANCE', {}, cfg)
        self.assertEqual(self.audit()['events'], 1)

    def test_amount_and_policy_schema_boundaries(self):
        c, _, _, _ = task(bytes(16))
        for cap, fee in [(0, 0), (-1, 0), (True, 0), (MAX+1, 0), (10, 11), (10, -1), (10, 0.5)]:
            with self.assertRaises(Rejected): policy(c, self.payee, cap, fee)
        p = decode(policy(c, self.payee, 10, 0))
        for key, value in [('asset', 'USD'), ('decimal_places', 2), ('source', 'issuance'), ('pending_rule', 'refund'), ('extra', 1)]:
            with self.assertRaises(Rejected): validate_policy({**p, key: value})

    def test_sqlite_integer_max_reserve_and_genesis_overflow(self):
        ledger = Ledger(self.root/'max.sqlite', self.private, self.public, {ZERO: b'a'*32}, {ZERO: MAX})
        cfg = {**self.cfg, 'authority_id': ledger.authority}; old = self.ledger; self.ledger = ledger; self.cfg = cfg
        pid, _, _ = self.freeze(MAX, MAX); self.call('RESERVE', {'policy_id': pid})
        self.assertEqual(self.audit()['reserved'], MAX)
        with self.assertRaises(Rejected): Ledger(self.root/'bad.sqlite', self.private, self.public, self.enrollment, {ZERO: MAX, self.other: 1})
        self.ledger = old

    def test_no_amount_override_or_unknown_policy(self):
        pid, _, _ = self.freeze()
        with self.assertRaises(Rejected): self.call('RESERVE', {'policy_id': pid, 'amount': 1})
        self.assertEqual(self.call('RESERVE', {'policy_id': bytes(32)})['status'], 'DENIED')

    def test_no_payment_refund_or_runtime_mint_endpoint(self):
        for op in ['PAY', 'REFUND', 'CREDIT', 'CANCEL', 'ISSUE_GRANT']:
            with self.assertRaises(Rejected): self.call(op, {})
        self.assertEqual(self.audit()['initial_total'], 100)

    def test_restart_and_status_keep_original_receipt(self):
        pid, _, _ = self.freeze(); original = self.call('RESERVE', {'policy_id': pid})
        self.ledger = Ledger(self.root/'ledger.sqlite', self.private, self.public, self.enrollment)
        self.assertEqual(self.call('STATUS', {'policy_id': pid})['result'], original['result'])
        self.assertEqual(self.call('RESERVE', {'policy_id': pid})['status'], 'DUPLICATE')
        self.audit()

    def test_missing_or_existing_ledger_not_reinitialized(self):
        with self.assertRaises(Rejected): Ledger(self.root/'missing', self.private, self.public, self.enrollment)
        with self.assertRaises(FileExistsError): Ledger(self.root/'ledger.sqlite', self.private, self.public, self.enrollment, {ZERO: 100, self.other: 0})

    def test_event_write_failure_rolls_back_balance_and_receipt(self):
        pid, _, _ = self.freeze()
        with patch.object(self.ledger, 'append', side_effect=OSError('injected event write')):
            with self.assertRaises(OSError): self.call('RESERVE', {'policy_id': pid})
        a = self.audit(); self.assertEqual((a['reserved'], a['reservations']), (0, 0))
        self.assertEqual(self.call('RESERVE', {'policy_id': pid})['status'], 'RESERVED')

    def test_reservation_signature_failure_rolls_back(self):
        pid, _, _ = self.freeze()
        with patch.object(writer, 'sign', side_effect=HostFault('injected signer failure')):
            with self.assertRaises(HostFault): self.call('RESERVE', {'policy_id': pid})
        self.assertEqual(self.audit()['reserved'], 0)

    def test_response_failure_after_commit_queries_original_without_redebit(self):
        pid, _, _ = self.freeze(); real = writer.sign
        def fault(payload, private):
            if payload['schema_id'] == 'aclt.exp.funding-response@1': raise HostFault('reply signing lost')
            return real(payload, private)
        with patch.object(writer, 'sign', side_effect=fault):
            with self.assertRaises(HostFault): self.call('RESERVE', {'policy_id': pid})
        receipt = self.call('STATUS', {'policy_id': pid})['result']
        self.assertEqual(self.call('RESERVE', {'policy_id': pid})['result'], receipt)
        self.assertEqual(self.audit()['reserved'], 60)

    def test_signed_response_cannot_substitute_another_request(self):
        one = request(self.cfg, 'BALANCE', {}); raw = self.ledger.handle(one)
        with self.assertRaises(Rejected): response(request(self.cfg, 'BALANCE', {}), raw, self.cfg, self.public)

    def test_offline_projection_truncation_and_wrong_pins_rejected(self):
        pid, _, _ = self.freeze(); self.call('RESERVE', {'policy_id': pid})
        bundle, anchor = self.ledger.export()
        bad = copy.deepcopy(bundle); bad['projection']['accounts'][ZERO.hex()]['available'] += 1
        with self.assertRaises(Rejected): reduce(bad, anchor, self.public, self.ledger.pin, sha(anchor))
        bad = copy.deepcopy(bundle); bad['events'].pop()
        with self.assertRaises(Rejected): reduce(bad, anchor, self.public, self.ledger.pin, sha(anchor))
        self.assertEqual(reduce(bundle, anchor, self.public, bytes(32), bytes(32))['sha_consistency'], 'DISABLED')
