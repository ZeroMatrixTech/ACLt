import unittest

from tools.verification_profile import admission as a, codec as c


class AdmissionTests(unittest.TestCase):
    def test_deadline_and_exact_budget_boundaries(self):
        for received, committed, cost, cap, valid, expected in (
            (99, 4, 6, 10, True, True),
            (100, 4, 6, 10, True, False),
            (101, 4, 6, 10, True, False),
            (99, 4, 7, 10, True, False),
            (99, 4, 6, 10, False, False),
            (99, 10, 0, 10, True, True),
            (99, 11, 0, 10, True, False),
        ):
            with self.subTest(received=received, committed=committed, cost=cost, valid=valid):
                self.assertEqual(a.evidence_admissible(received, 100, committed, cost, cap, valid),
                                 expected)

    def test_uint64_limits_and_implicit_truthiness(self):
        max_uint = 2**64 - 1
        self.assertFalse(a.within_funding_cap(max_uint, 1, max_uint))
        self.assertTrue(a.within_funding_cap(max_uint, 0, max_uint))
        for malformed in (True, -1, 2**64, None):
            with self.subTest(malformed=malformed), self.assertRaises(c.CodecError):
                a.within_funding_cap(0, malformed, max_uint)
        with self.assertRaises(c.CodecError):
            a.evidence_admissible(0, 1, 0, 0, 0, 1)

    def event(self, ref, kind, *parents, subject='r'):
        return dict(event_ref=ref, event_kind=kind, parent_refs=list(parents),
                    subject_ref=dict(tag='RECEIPT', id=subject))

    def resolve(self, observation, frontier, events):
        return a.resolve_boundary(observation,
            dict(frontier_event_ref=frontier, event_records=events), 'r')

    def test_boundary_order_and_concurrency(self):
        funds = self.event('f', 'FUNDING_EXHAUSTED')
        deadline = self.event('d', a.DEADLINE)
        join = self.event('join', 'OTHER', 'f', 'd')
        both = dict(funding_event_ref='f', deadline_event_ref='d')
        cases = [
            ({}, 'f', [funds], None),
            (dict(funding_event_ref='f'), 'f', [funds], a.FUNDING),
            (dict(deadline_event_ref='d'), 'd', [deadline], a.DEADLINE),
            (both, 'join', [deadline, join, funds], a.FUNDING),
            (both, 'd', [dict(deadline, parent_refs=['f']), funds], a.FUNDING),
            (both, 'f', [dict(funds, parent_refs=['d']), deadline], a.DEADLINE),
        ]
        for observation, frontier, records, expected in cases:
            with self.subTest(observation=observation, frontier=frontier):
                self.assertEqual(self.resolve(observation, frontier, records), expected)
                self.assertEqual(self.resolve(observation, frontier, records[::-1]), expected)

    def test_invalid_boundary_facts_are_not_concurrent(self):
        funds = self.event('f', 'FUNDING_EXHAUSTED')
        deadline = self.event('d', a.DEADLINE)
        obs = dict(funding_event_ref='f', deadline_event_ref='d')
        for frontier, records in (
            ('d', [deadline]),
            ('d', [funds, deadline]),
            ('d', [funds, dict(deadline, parent_refs=['missing'])]),
            ('d', [dict(funds, parent_refs=['d']), dict(deadline, parent_refs=['f'])]),
            ('d', [dict(funds, event_kind='OTHER'), dict(deadline, parent_refs=['f'])]),
            ('d', [dict(funds, subject_ref=dict(tag='RECEIPT', id='foreign')),
                   dict(deadline, parent_refs=['f'])]),
        ):
            with self.subTest(records=records):
                self.assertEqual(self.resolve(obs, frontier, records), a.INVALIDATING)
