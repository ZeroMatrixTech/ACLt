# SPDX-License-Identifier: Apache-2.0
"""Evidence ceilings and phase boundaries; not a formal protocol validator."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.bq_boundaries.readiness import (
    REQUIREMENTS, assess_inventory, lifecycle_projection, matrix_report, precreate_selection,
)
from tools.bq_boundaries.model import accepts
BASE=ROOT/'tests/bq_readiness/fixtures'


class ReadinessTests(unittest.TestCase):
    def data(self):return json.loads((BASE/'hypothetical-complete.json').read_text())
    def row(self,d,rid):return next(r for r in d['records'] if r['requirement_id']==rid)
    def edge(self):
        return {'stage':'CREATE','failure_reasons':['SUPPORT_CAPABILITY_BOUND_UNAVAILABLE'],
         'enabling_triggers':['SUPPORT_CAPABILITY_BOUND_UNAVAILABLE'],'requester_authorized':True,
         'edge_class':'AUTO_DECIDABLE','source_digest':'1'*64,'edge_source_digest':'1'*64,
         'target_digest':'2'*64,'edge_target_digest':'2'*64,'target_applicable':True,'target_gate_ok':True}

    def test_complete_stipulated_review_never_enables_runtime(self):
        r=assess_inventory(self.data());self.assertEqual(r['research_ceiling'],'BOUNDED_REVIEW_CANDIDATE')
        self.assertFalse(r['automatic_deployment_eligibility']);self.assertFalse(r['writes_runtime_state'])
        self.assertFalse(r['formal_phase_validator_implemented']);self.assertEqual(r['computed_n_required'],6)

    def test_every_core_gap_blocks_even_audit_review(self):
        for rid,(_,core,_) in REQUIREMENTS.items():
            if core:
                d=self.data();d['records']=[r for r in d['records'] if r['requirement_id']!=rid]
                self.assertEqual(assess_inventory(d)['research_ceiling'],'NO_REEXEC_REVIEW_CANDIDATE',rid)

    def test_every_bounded_gap_lowers_ceiling_without_granting_fallback(self):
        for rid,(_,core,_) in REQUIREMENTS.items():
            if not core:
                d=self.data();self.row(d,rid)['state']='NOT_ESTABLISHED'
                r=assess_inventory(d);self.assertEqual(r['research_ceiling'],'AUDIT_ONLY_REVIEW_CANDIDATE',rid)
                self.assertFalse(r['automatic_deployment_eligibility'])

    def test_synthetic_calibration_cannot_be_promoted_by_pass_label(self):
        d=self.data();self.row(d,'q_truth_calibration')['evidence_kind']='SYNTHETIC_ONLY'
        r=assess_inventory(d);self.assertIn('q_truth_calibration:BASIS_SYNTHETIC_ONLY',r['causes'])
        self.assertEqual(r['research_ceiling'],'AUDIT_ONLY_REVIEW_CANDIDATE')

    def test_half_open_validity_and_expired_B(self):
        d=self.data();self.row(d,'support_capability_bound')['validity']=[100,200]
        self.assertEqual(assess_inventory(d)['research_ceiling'],'BOUNDED_REVIEW_CANDIDATE')
        d['context']['evaluation_tick']=99
        self.assertIn('support_capability_bound:OUTSIDE_WINDOW',assess_inventory(d)['causes'])
        d['context']['evaluation_tick']=200
        self.assertIn('support_capability_bound:OUTSIDE_WINDOW',assess_inventory(d)['causes'])

    def test_invalid_gap_and_DP_budget_never_get_bounded_review(self):
        for patch,reason in [({'B':8,'Q':8},'NUMERIC_PROFILE_NOT_ADMISSIBLE'),({'delta_min':'3/5'},'NUMERIC_PROFILE_NOT_ADMISSIBLE'),({'n_budget':5},'DP_BUDGET_TOO_SMALL'),({'n_required_claimed':5},'DP_REQUIREMENT_NOT_BOUND')]:
            d=self.data();d['parameters'].update(patch);r=assess_inventory(d)
            self.assertIn(reason,r['causes']);self.assertNotEqual(r['research_ceiling'],'BOUNDED_REVIEW_CANDIDATE')

    def test_official_assurance_cannot_cross_network(self):
        for patch in [{'network_is_official':False}]:
            d=self.data();d['context'].update(patch)
            self.assertEqual(assess_inventory(d)['research_ceiling'],'NO_REEXEC_REVIEW_CANDIDATE')

    def test_all_causes_retained_and_record_order_irrelevant(self):
        d=self.data();self.row(d,'support_capability_bound').update(state='REVOKED',validity=[0,100])
        self.row(d,'q_truth_calibration')['scope_digest']='0'*64
        original=copy.deepcopy(d);a=assess_inventory(d);self.assertEqual(d,original)
        d['records'].reverse();self.assertEqual(assess_inventory(d),a)
        self.assertIn('support_capability_bound:STATE_REVOKED',a['causes'])
        self.assertIn('support_capability_bound:OUTSIDE_WINDOW',a['causes'])
        self.assertNotIn('q_truth_calibration:SCOPE_NOT_BOUND',a['causes'])
        self.assertEqual(a['causes'],sorted(set(a['causes'])))

    def test_precreate_requires_authorization_edge_and_matching_digests(self):
        c=self.edge();self.assertEqual(precreate_selection(c)['projection'],'AUDIT_SLOT_REVIEW_CANDIDATE')
        for patch in [{'requester_authorized':False},{'edge_class':'ATTESTED'},{'target_gate_ok':False},{'target_applicable':False}]:
            bad=copy.deepcopy(c);bad.update(patch)
            self.assertEqual(precreate_selection(bad)['projection'],'NO_AUTOMATIC_FALLBACK')

    def test_digest_bindings_are_record_only(self):
        d=self.data();self.row(d,'q_truth_calibration')['scope_digest']='0'*64;d['context']['network_digest']='0'*64
        self.assertEqual(assess_inventory(d)['research_ceiling'],'BOUNDED_REVIEW_CANDIDATE')
        edge=self.edge();edge['edge_target_digest']='3'*64
        self.assertEqual(precreate_selection(edge)['projection'],'AUDIT_SLOT_REVIEW_CANDIDATE')

    def test_unrelated_failure_cannot_be_hidden_by_allowed_trigger(self):
        c=self.edge();c['failure_reasons'].append('CONTRACT_MISMATCH')
        self.assertIn('FAILURES_NOT_COVERED',precreate_selection(c)['causes'])
        c=self.edge();c['failure_reasons']=['REQUIRED_EVIDENCE_MISSING']
        self.assertEqual(precreate_selection(c)['projection'],'NO_AUTOMATIC_FALLBACK')

    def test_no_Profile_switch_after_receipt_even_before_first_draw(self):
        for stage in ['PRE_FREEZE','FROZEN_PRE_DRAW','RUNNING','TERMINAL']:
            c=self.edge();c['stage']=stage;r=precreate_selection(c)
            self.assertEqual(r['projection'],'NO_AUTOMATIC_FALLBACK')
            self.assertFalse(r['changes_existing_receipt']);self.assertFalse(r['authorizes_runtime'])

    def test_population_binding_failure_four_stage_boundary(self):
        expected={'PRE_FREEZE':'REJECT_CURRENT_PHASE_B_OPERATION','FROZEN_PRE_DRAW':'INVALIDATE_SNAPSHOT_BLOCK_FIRST_DRAW_AND_REFREEZE',
                  'RUNNING':'VERIFICATION_INVALIDATING','TERMINAL':'APPEND_QUALIFICATION_REVIEW_ONLY'}
        for stage,action in expected.items():
            r=lifecycle_projection(stage,'POPULATION_BINDING_FAILURE','TRUSTED' if stage=='TERMINAL' else None)
            self.assertEqual(r['action'],action);self.assertFalse(r['profile_switch_authorized'])
            if stage=='TERMINAL':self.assertEqual(r['terminal_preserved'],'TRUSTED')

    def test_safety_revocation_prevents_accept_and_preserves_terminal(self):
        self.assertTrue(accepts([1,1]))  # Kernel evidence cannot override revocation.
        r=lifecycle_projection('RUNNING','SAFETY_REVOKED')
        self.assertEqual(r['action'],'VERIFICATION_INVALIDATING');self.assertEqual(r['terminal_hint_not_commit'],'UNRESOLVED')
        self.assertFalse(r['new_TRUSTED_authorized'])
        r=lifecycle_projection('TERMINAL','SAFETY_REVOKED','TRUSTED')
        self.assertEqual(r['terminal_preserved'],'TRUSTED');self.assertEqual(r['qualification_hint'],'DEPENDENCY_REVOKED')

    def test_source_unknown_does_not_become_valid_or_revoke_old_terminal(self):
        r=lifecycle_projection('RUNNING','SOURCE_UNAVAILABLE')
        self.assertEqual(r['action'],'NO_VERDICT_FAIL_CLOSED');self.assertFalse(r['new_TRUSTED_authorized'])
        r=lifecycle_projection('TERMINAL','SOURCE_UNAVAILABLE','TRUSTED')
        self.assertEqual(r['terminal_preserved'],'TRUSTED');self.assertIsNone(r['qualification_hint'])

    def test_expiry_after_terminal_is_not_retroactive_revocation(self):
        r=lifecycle_projection('TERMINAL','VALIDITY_WINDOW_ENDED','TRUSTED')
        self.assertEqual(r['action'],'PRESERVE_TERMINAL_NO_RETROACTIVE_EXPIRY');self.assertIsNone(r['qualification_hint'])
        self.assertEqual(lifecycle_projection('RUNNING','VALIDITY_WINDOW_ENDED')['action'],'VERIFICATION_INVALIDATING')

    def test_liveness_mapping_not_replaced_by_safety_default(self):
        m={'before_verification':'PROCEED','during_verification':'PROCEED','after_terminal':'QUALIFY_WEAKENED'}
        r=lifecycle_projection('RUNNING','CALIBRATION_REVOKED',liveness_mapping=m)
        self.assertEqual(r['action'],'PROCEED');self.assertTrue(r['liveness_claim_requires_review'])
        self.assertEqual(lifecycle_projection('RUNNING','SAFETY_REVOKED',liveness_mapping=m)['action'],'VERIFICATION_INVALIDATING')
        self.assertEqual(lifecycle_projection('TERMINAL','CALIBRATION_REVOKED','TRUSTED',m)['qualification_hint'],'WEAKENED')
        with self.assertRaises(ValueError):lifecycle_projection('RUNNING','CALIBRATION_REVOKED')

    def test_unknown_records_duplicate_and_forged_project_approval_rejected(self):
        for mutation in ['duplicate','unknown','project','bool','missing_binding']:
            d=self.data()
            if mutation=='duplicate':d['records'].append(copy.deepcopy(d['records'][0]))
            elif mutation=='unknown':d['records'][0]['state']='ENABLED'
            elif mutation=='project':d['data_kind']='project-gap-inventory'
            elif mutation=='bool':d['parameters']['B']=True
            else:d['records'][0]['evidence_digest']=None
            with self.assertRaises(ValueError):assess_inventory(d)
        with self.assertRaises(ValueError):lifecycle_projection('TERMINAL','SAFETY_REVOKED')

    def test_cli_reproduces_report_protects_old_report_and_rejects_bad_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp);dest=temp/'report.json';cmd=[sys.executable,'-B',str(ROOT/'scripts/check-bq-readiness.py'),'--report',str(dest)]
            subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL)
            raw=dest.read_bytes();data=json.loads(raw)
            self.assertEqual(data['case_counts'],{'requirements':14,'inventories':12,'precreate':8,'lifecycle':19})
            self.assertEqual(data['inventory_assessment']['research_ceiling'],'NO_REEXEC_REVIEW_CANDIDATE')
            self.assertEqual(len(data['source_sha256']),11)
            self.assertNotEqual(subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode,0)
            self.assertEqual(dest.read_bytes(),raw)
            for name,raw_bad in [('duplicate','{"schema_id":1,"schema_id":1}'),('float','{"G":10.0}')]:
                src=temp/(name+'.json');dst=temp/(name+'-out.json');src.write_text(raw_bad)
                result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/check-bq-readiness.py'),'--inventory',str(src),'--report',str(dst)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                self.assertNotEqual(result.returncode,0);self.assertFalse(dst.exists())


if __name__=='__main__':unittest.main()
