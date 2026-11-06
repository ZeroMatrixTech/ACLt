import copy
import unittest

from tools.verification_profile import codec as c, phase_b


class NoSnapshotPhaseBTests(unittest.TestCase):
    profile = dict(id='acl.vp.test.audit', version=[2, 0, 0], digest=b'p'*32)
    receipt = b'r'*32

    def event(self, ref, kind, parents=(), receipt=None):
        return dict(event_ref=ref, event_kind=kind, parent_refs=list(parents),
                    subject_ref=dict(tag='RECEIPT', id=receipt or self.receipt))

    def payload(self, prior, proposed, ref=None):
        def state(stage):
            return dict(round_stage=stage, bound_profile_ref=copy.deepcopy(self.profile))
        value = dict(tag=phase_b.TAG, transition=dict(prior_round_state=state(prior),
                                                       proposed_round_state=state(proposed)))
        if ref is not None:
            value['transition_event_ref'] = ref
        return value

    def check(self, payload, events, frontier, method='REEXEC_AUDIT_ONLY'):
        phase_b.validate_no_snapshot_round(method, self.receipt, self.profile, payload,
            dict(frontier_event_ref=frontier, event_records=events))

    def test_four_legal_edges_and_method_dispatch(self):
        start = self.event('start', phase_b.STARTED)
        end = self.event('end', phase_b.COMMITTED, ['start'])
        for method in sorted(phase_b.METHODS):
            with self.subTest(method=method):
                self.check(self.payload('PRE_FREEZE', 'RUNNING', 'start'), [start], 'start', method)
                self.check(self.payload('RUNNING', 'RUNNING'), [start], 'start', method)
                self.check(self.payload('RUNNING', 'TERMINAL', 'end'), [end, start], 'end', method)
                self.check(self.payload('PRE_FREEZE', 'TERMINAL', 'end'),
                           [self.event('end', phase_b.COMMITTED)], 'end', method)
        with self.assertRaises(c.CodecError):
            self.check(self.payload('PRE_FREEZE', 'RUNNING', 'start'), [start], 'start', 'REEXEC_BOUNDED')

    def test_snapshot_fields_old_tag_and_invalid_edges_reject(self):
        start = self.event('start', phase_b.STARTED)
        base = self.payload('PRE_FREEZE', 'RUNNING', 'start')
        variants = [dict(base, eligibility_snapshot={}), dict(base, tag='ROUND_TRANSITION_POST_FREEZE'),
                    self.payload('PRE_FREEZE', 'FROZEN_PRE_DRAW', 'start'),
                    self.payload('TERMINAL', 'RUNNING', 'start'),
                    self.payload('RUNNING', 'PRE_FREEZE', 'start')]
        for field in ('frozen_parameters', 'population_size', 'cluster_mapping_ref', 'bound_profile_ref'):
            bad = copy.deepcopy(base)
            bad['transition']['proposed_round_state'][field] = {}
            variants.append(bad)
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(c.CodecError):
                self.check(variant, [start], 'start')

    def test_start_requires_unique_causally_visible_receipt_event(self):
        base = self.payload('PRE_FREEZE', 'RUNNING', 'start')
        start = self.event('start', phase_b.STARTED)
        for events, frontier in (
            ([self.event('start', 'OTHER')], 'start'),
            ([self.event('start', phase_b.STARTED, receipt=b'x'*32)], 'start'),
            ([start, self.event('outside', 'OTHER')], 'outside'),
            ([start, self.event('another', phase_b.STARTED, ['start'])], 'another'),
            ([start, self.event('closed', phase_b.COMMITTED, ['start'])], 'closed'),
        ):
            with self.subTest(frontier=frontier), self.assertRaises(c.CodecError):
                self.check(base, events, frontier)
        with self.assertRaises(c.CodecError):
            self.check(self.payload('PRE_FREEZE', 'RUNNING'), [start], 'start')
        with self.assertRaises(c.CodecError):
            self.check(self.payload('RUNNING', 'RUNNING', 'start'), [start], 'start')

    def test_terminal_requires_unique_commit_and_correct_start_order(self):
        start = self.event('start', phase_b.STARTED)
        end = self.event('end', phase_b.COMMITTED)
        fork = self.event('frontier', 'OTHER', ['start', 'end'])
        with self.assertRaises(c.CodecError):
            self.check(self.payload('RUNNING', 'TERMINAL', 'end'), [start, end, fork], 'frontier')
        with self.assertRaises(c.CodecError):
            self.check(self.payload('PRE_FREEZE', 'TERMINAL', 'end'), [start, end, fork], 'frontier')
        with self.assertRaises(c.CodecError):
            self.check(self.payload('PRE_FREEZE', 'TERMINAL', 'end'),
                       [end, self.event('another', phase_b.COMMITTED, ['end'])], 'another')
        with self.assertRaises(c.CodecError):
            self.check(self.payload('PRE_FREEZE', 'TERMINAL', 'end'),
                       [self.event('end', 'OTHER')], 'end')
