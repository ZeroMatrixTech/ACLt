# SPDX-License-Identifier: Apache-2.0
"""Exact sampling-error controls plus scope/source rejection cases."""
from fractions import Fraction
import json
from math import factorial
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.bq_boundaries.calibration import (
    analyze, binomial_lower_tail, conditional_test, ratio, research_report,
    sensitivity, validate_dataset, zero_failure_minimum,
)

FIXTURE=ROOT/'tests/bq_calibration/fixtures/synthetic-v1.json'
D=Fraction(1,20); A=Fraction(1,20)


def independent_binomial_dp(n,p):
    dist=[Fraction(1)]
    for _ in range(n):
        nxt=[Fraction() for _ in range(len(dist)+1)]
        for k,mass in enumerate(dist):
            nxt[k]+=mass*(1-p);nxt[k+1]+=mass*p
        dist=nxt
    return dist


class CalibrationTests(unittest.TestCase):
    def data(self): return json.loads(FIXTURE.read_text())

    def test_tail_matches_independent_bernoulli_DP(self):
        for n in range(1,13):
            for p in [Fraction(1,10),Fraction(1,4),Fraction(1,2)]:
                dist=independent_binomial_dp(n,p)
                for k in range(n+1):
                    self.assertEqual(binomial_lower_tail(n,k,p),sum(dist[:k+1]))

    def test_zero_failure_minimum_is_exact_and_minimal(self):
        for family,want in [(1,59),(3,80)]:
            n=zero_failure_minimum(D,A,family)
            self.assertEqual(n,want)
            self.assertLessEqual((1-D)**n,A/family)
            self.assertGreater((1-D)**(n-1),A/family)

    def test_candidate_family_correction_prevents_naive_selection(self):
        self.assertEqual(conditional_test([8]*60,10,[8],D,A)['selected_Q_if_assumptions_hold'],8)
        self.assertIsNone(conditional_test([8]*60,10,[4,6,8],D,A)['selected_Q_if_assumptions_hold'])
        self.assertEqual(conditional_test([8]*80,10,[4,6,8],D,A)['selected_Q_if_assumptions_hold'],8)

    def test_labeled_synthetic_fixture_never_approves_deployment(self):
        r=analyze(self.data())
        self.assertEqual(r['n_units_assumed_iid'],80)
        self.assertEqual(r['selected_Q_if_assumptions_hold'],8)
        self.assertFalse(r['automatic_deployment_eligibility'])
        self.assertFalse(r['empirical_calibration_established'])
        self.assertFalse(r['B_estimated'])

    def test_missing_task_support_consumed_as_failure_not_dropped(self):
        d=self.data()
        for row in d['rows'][:4]:row['correct_support']=None
        r=analyze(d)
        self.assertEqual(r['n_units_assumed_iid'],80)
        self.assertTrue(all(row['failures']==4 for row in r['candidate_tests']))
        self.assertIsNone(r['selected_Q_if_assumptions_hold'])

    def test_shared_dependence_blocks_are_rejected(self):
        d=self.data();d['rows'][1]['block_id']=d['rows'][0]['block_id']
        with self.assertRaises(ValueError):analyze(d)
        self.assertIsNone(conditional_test([8]*6,10,[8],D,A)['selected_Q_if_assumptions_hold'])
        self.assertEqual(conditional_test([8]*60,10,[8],D,A)['selected_Q_if_assumptions_hold'],8)

    def test_majority_labels_or_unknown_truth_rejected(self):
        d=self.data();d['truth']['mode']='worker-majority'
        with self.assertRaises(ValueError):analyze(d)
        d=self.data();d['rows'][0]['truth_correct']=False
        with self.assertRaises(ValueError):analyze(d)

    def test_task_family_matches_while_scope_sha_fields_are_records(self):
        for key in self.data()['scope']:
            d=self.data();d['target_scope'][key]='changed' if key=='task_family' else '0'*64
            if key=='task_family':
                with self.assertRaises(ValueError):analyze(d)
            else:
                self.assertEqual(analyze(d)['sha_consistency'],'DISABLED')

    def test_fixed_horizon_and_predeclaration_required(self):
        for change in ['truncated','postselected','iid','unknown']:
            d=self.data()
            if change=='truncated':d['rows'].pop()
            elif change=='postselected':d['plan']['selection']='picked-after-results'
            elif change=='iid':d['plan']['iid_asserted']=False
            else:d['plan']['override']=True
            with self.assertRaises(ValueError):analyze(d)

    def test_duplicate_tasks_and_invalid_types_rejected(self):
        d=self.data();d['rows'][1]['task_id']=d['rows'][0]['task_id']
        with self.assertRaises(ValueError):analyze(d)
        for q in [[8,8],[8,4],[True],[]]:
            with self.assertRaises(ValueError):conditional_test([8]*80,10,q,D,A)
        for value in [0.05,'0.05','2/40','0/1','NaN']:
            with self.assertRaises(ValueError):ratio(value)
        d=self.data();d['rows'][0]['correct_support']=8.0
        with self.assertRaises(ValueError):analyze(d)

    def test_multinomial_enumeration_controls_false_calibration(self):
        # Independent distribution enumeration, including simultaneous Q choice.
        n=6;alpha=Fraction(1,5);delta=Fraction(1,2)
        for masses in [(Fraction(1,4),)*4,(Fraction(3,5),Fraction(1,10),Fraction(1,10),Fraction(1,5))]:
            wrong_pass=Fraction();total=Fraction()
            for a in range(n+1):
                for b in range(n-a+1):
                    for c in range(n-a-b+1):
                        counts=[a,b,c,n-a-b-c];prob=Fraction(factorial(n))
                        observations=[]
                        for m,(cnt,mass) in enumerate(zip(counts,masses)):
                            prob*=mass**cnt/factorial(cnt);observations += [m]*cnt
                        total+=prob
                        rows=conditional_test(observations,3,[1,2,3],delta,alpha)['candidate_tests']
                        if any(x['conditional_pass'] and sum(masses[:x['Q']])>delta for x in rows):wrong_pass+=prob
            self.assertEqual(total,1)
            self.assertLessEqual(wrong_pass,alpha)

    def test_sensitivity_preserves_old_profile_and_rejects_nonpositive_gap(self):
        r=sensitivity()
        self.assertEqual([x['frozen_old_false_acceptance'] for x in r['fixed_old_profile_capability_miss']],['1/12','4/21','43/126','11/21','8/9'])
        self.assertEqual(r['fixed_old_profile_support_loss'][1]['frozen_six_draw_liveness'],'53/60')
        self.assertEqual([x['six_draw_liveness'] for x in r['common_task_outage']],['1','19/20','4/5'])
        self.assertEqual(len(r['prospective_new_profiles_not_retroactive_repair']),20)
        for x in r['prospective_new_profiles_not_retroactive_repair']:
            if not x['positive_gap']:
                self.assertIsNone(x['prospective_required_draws']);self.assertFalse(x['fits_six_draw_budget'])
        self.assertEqual(r['externally_bounded_distribution_shift'][0]['joint_release_and_liveness_failure_bound'],'3/20')

    def test_cli_reproduces_new_report_and_preserves_existing(self):
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/'result.json';cmd=[sys.executable,'-B',str(ROOT/'scripts/check-bq-calibration.py'),'--report',str(dest)]
            subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL)
            raw=dest.read_bytes();data=json.loads(raw)
            self.assertEqual(len(data.pop('source_sha256')),8);self.assertEqual(len(data.pop('dataset_sha256')),64)
            self.assertEqual(data,research_report(self.data()))
            self.assertNotEqual(subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode,0)
            self.assertEqual(raw,dest.read_bytes())

    def test_cli_rejects_bad_scope_and_duplicate_JSON_without_success_report(self):
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp)
            for label in ['scope','duplicate','float']:
                src=temp/(label+'.json');dest=temp/(label+'-result.json');d=self.data()
                if label=='scope':d['target_scope']['task_family']='changed'
                raw=json.dumps(d)
                if label=='duplicate':raw=raw.replace('"population": 10','"population": 10, "population": 10')
                if label=='float':raw=raw.replace('"population": 10','"population": 10.0')
                src.write_text(raw)
                r=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/check-bq-calibration.py'),'--dataset',str(src),'--report',str(dest)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                self.assertNotEqual(r.returncode,0);self.assertFalse(dest.exists())


    def test_zero_failure_search_above_former_500_limit(self):
        from tools.bq_boundaries.calibration import zero_failure_minimum
        delta, alpha = Fraction(1,1000), Fraction(1,20)
        n = zero_failure_minimum(delta,alpha)
        self.assertGreater(n,500)
        self.assertLessEqual((1-delta)**n,alpha)
        self.assertGreater((1-delta)**(n-1),alpha)

if __name__=='__main__':unittest.main()
