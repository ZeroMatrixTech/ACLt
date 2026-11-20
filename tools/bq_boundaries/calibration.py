# SPDX-License-Identifier: Apache-2.0
"""Fixed-horizon task-level Q calibration research; never deployment approval.

The exact binomial test requires independent identically distributed task
indicators, a fixed sample size and a predeclared finite candidate family.
Metadata assertions do not establish those facts. B and drift are not fitted.
"""
from fractions import Fraction
from math import comb
import re

from .model import placements, liveness_curve, required_draws

SCOPE_FIELDS = {'task_family', 'profile_digest', 'resource_digest', 'population_digest',
                'truth_policy_digest', 'deadline_policy_digest', 'sampling_policy_digest'}


def integer(x, lower, upper, name):
    if type(x) is not int or x < lower or (upper is not None and x > upper):
        raise ValueError('bounded integer required: ' + name)
    return x


def probability(x):
    if type(x) is not Fraction or not 0 < x < 1:
        raise ValueError('exact probability strictly inside (0,1) required')
    return x


def ratio(s):
    if type(s) is not str or re.fullmatch(r'[1-9][0-9]*/[1-9][0-9]*', s) is None:
        raise ValueError('bounded rational string required')
    p = probability(Fraction(s))
    if str(p) != s:
        raise ValueError('reduced rational required')
    return p


def fields(value, names):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError('closed research record fields required')


def digest(x):
    if type(x) is not str or re.fullmatch('[0-9a-f]{64}', x) is None:
        raise ValueError('research digest required')


def binomial_lower_tail(n, k, p):
    integer(n, 1, None, 'sample size'); integer(k, 0, n, 'failures'); probability(p)
    return sum((Fraction(comb(n, j)) * p**j * (1-p)**(n-j) for j in range(k+1)), Fraction())


def conditional_test(counts, g, candidates, delta_q, alpha):
    """Test p_q=P(M<Q) <= delta_q, simultaneous alpha via Bonferroni.

    This is an exact threshold test, not a numerical inversion of a CP limit.
    Passing is a conditional research result, not a posterior probability.
    """
    integer(g, 1, None, 'G'); integer(len(counts), 1, None, 'sample size')
    probability(delta_q); probability(alpha)
    if type(candidates) is not list or not candidates:
        raise ValueError('finite predeclared candidate list required')
    for q in candidates: integer(q, 1, g, 'Q')
    if candidates != sorted(set(candidates)):
        raise ValueError('strictly increasing unique candidate family required')
    for x in counts: integer(x, 0, g, 'correct support count')
    threshold = alpha / len(candidates)
    rows = []
    for q in candidates:
        k = sum(x < q for x in counts)
        tail = binomial_lower_tail(len(counts), k, delta_q)
        rows.append({'Q': q, 'failures': k, 'boundary_tail': str(tail),
                     'alpha_per_candidate': str(threshold), 'conditional_pass': tail <= threshold})
    passing = [x['Q'] for x in rows if x['conditional_pass']]
    return {'n_units_assumed_iid': len(counts), 'candidate_tests': rows,
            'selected_Q_if_assumptions_hold': max(passing) if passing else None,
            'alpha_calibration': str(alpha), 'delta_Q': str(delta_q),
            'automatic_deployment_eligibility': False}


def validate_dataset(data):
    fields(data, {'schema_id', 'data_kind', 'population', 'scope', 'target_scope', 'truth', 'plan', 'rows'})
    if data['schema_id'] != 'aclt.research.bq-calibration@1' or data['data_kind'] != 'synthetic':
        raise ValueError('only labeled synthetic research inputs supported by this slice')
    integer(data['population'], 1, None, 'G')
    for scope in [data['scope'], data['target_scope']]:
        fields(scope, SCOPE_FIELDS)
        if type(scope['task_family']) is not str or not scope['task_family']:
            raise ValueError('explicit task family required')
        for n in SCOPE_FIELDS - {'task_family'}: digest(scope[n])
    if data['scope']['task_family'] != data['target_scope']['task_family']:
        raise ValueError('calibration/target task family differs')
    fields(data['truth'], {'mode', 'provenance_digest'})
    if data['truth']['mode'] != 'synthetic-independent-oracle':
        raise ValueError('majority/self-agreement is not independent truth')
    digest(data['truth']['provenance_digest'])
    p = data['plan']
    fields(p, {'unit', 'iid_asserted', 'selection', 'fixed_n', 'candidate_Q', 'alpha', 'delta_Q'})
    if p['unit'] != 'task' or p['iid_asserted'] is not True or p['selection'] != 'predeclared-fixed-horizon':
        raise ValueError('fixed independent task plan required (assertion is not proof)')
    integer(p['fixed_n'], 1, None, 'fixed_n'); ratio(p['alpha']); ratio(p['delta_Q'])
    if type(data['rows']) is not list or len(data['rows']) != p['fixed_n']:
        raise ValueError('complete fixed-horizon sample required; missing tasks cannot be dropped')
    tasks = set(); blocks = set(); counts = []
    for row in data['rows']:
        fields(row, {'task_id', 'block_id', 'truth_correct', 'correct_support'})
        digest(row['task_id']); digest(row['block_id'])
        if row['truth_correct'] is not True:
            raise ValueError('correct-candidate independent labels required for Q')
        if row['task_id'] in tasks or row['block_id'] in blocks:
            raise ValueError('duplicate task or shared dependence block: no iid certificate')
        tasks.add(row['task_id']); blocks.add(row['block_id'])
        count = row['correct_support']
        # Null means no support observed by the frozen deadline for this known
        # correct task; consume it conservatively, never drop its task slot.
        counts.append(0 if count is None else integer(count, 0, data['population'], 'support'))
    conditional_test(counts, data['population'], p['candidate_Q'], ratio(p['delta_Q']), ratio(p['alpha']))
    return counts


def analyze(data):
    counts = validate_dataset(data); p = data['plan']
    result = conditional_test(counts, data['population'], p['candidate_Q'], ratio(p['delta_Q']), ratio(p['alpha']))
    result.update({'data_kind':'synthetic', 'task_family_matched':True, 'sha_consistency':'DISABLED',
                   'scope_and_iid_are_assertions_not_verified_sources':True,
                   'calibration_unit':'task', 'B_estimated':False, 'empirical_calibration_established':False})
    return result


def zero_failure_minimum(delta_q, alpha, family=1):
    probability(delta_q); probability(alpha); integer(family, 1, None, 'family')
    threshold = alpha / family
    lower, upper = 0, 1
    while (1-delta_q)**upper > threshold:
        lower, upper = upper, upper * 2
    while upper - lower > 1:
        middle = (lower + upper) // 2
        if (1-delta_q)**middle <= threshold:
            upper = middle
        else:
            lower = middle
    return upper


def sensitivity():
    epsilon = Fraction(1,5); delta = Fraction(1,20); alpha = Fraction(1,20)
    nominal = placements(10,3,8,8)[5]
    missed = [{'extra_capable_units_assumed':u, 'actual_C':3+u,
               'frozen_old_false_acceptance':str(placements(10,3,8,3+u,vote_cap=3)[-1])}
              for u in [0,1,2,3,5]]
    losses = [{'lost_correct_support_units_assumed':loss, 'actual_M':8-loss,
               'frozen_six_draw_liveness':str(placements(10,3,8,8-loss)[5])} for loss in [0,1,2,3]]
    outage = [{'task_outage_mass_assumed':str(rho), 'support_when_up':8, 'support_when_down':0,
               'six_draw_liveness':str((1-rho)*nominal), 'coverage_M_ge_8':str(1-rho)}
              for rho in [Fraction(0),Fraction(1,20),Fraction(1,5)]]
    drift = [{'external_TV_budget_assumed':str(eta), 'target_tail_bound':str(min(Fraction(1),delta+eta)),
              'joint_release_and_liveness_failure_bound':str(min(Fraction(1),alpha+delta+Fraction(1,20)+eta))}
             for eta in [Fraction(0),Fraction(1,50),Fraction(1,10)]]
    prospective = []
    for u in [0,1,2,3,4]:
        for loss in [0,1,2,3]:
            b=3+u; q=8-loss
            n = required_draws(liveness_curve(10,b,q,{q:Fraction(1)},epsilon),Fraction(1,20)) if b<q else None
            prospective.append({'extra_capability_assumed':u,'support_loss_assumed':loss,'proposed_B':b,'proposed_Q':q,
                                'positive_gap':b<q,'prospective_required_draws':n,
                                'fits_six_draw_budget':n is not None and n<=6})
    return {'base_parameters':{'G':10,'B':3,'Q':8,'epsilon_F':'1/5','delta_L':'1/20','alpha_calibration':'1/20','delta_Q':'1/20','frozen_budget':6}, 'fixed_old_profile_capability_miss':missed, 'fixed_old_profile_support_loss':losses,
            'common_task_outage':outage, 'externally_bounded_distribution_shift':drift,
            'prospective_new_profiles_not_retroactive_repair':prospective,
            'interpretation':'u/loss/rho/TV are stipulated sensitivity inputs, not inferred from votes or calibrated by this tool'}


def research_report(data):
    base=analyze(data); d=Fraction(1,20); a=Fraction(1,20)
    profiles={
        'single_Q_58_clean':conditional_test([8]*58,10,[8],d,a),
        'single_Q_59_clean':conditional_test([8]*59,10,[8],d,a),
        'three_Q_60_clean':conditional_test([8]*60,10,[4,6,8],d,a),
        'three_Q_80_clean':conditional_test([8]*80,10,[4,6,8],d,a),
        'three_Q_80_four_outages':conditional_test([0]*4+[8]*76,10,[4,6,8],d,a),
        'six_independent_block_minima':conditional_test([8]*6,10,[8],d,a),
    }
    profiles['six_independent_block_minima']['unit']='iid-block-minimum-comparison-only-not-task-certificate'
    return {'status':'PASS','kind':'synthetic-fixed-horizon-calibration-and-sensitivity-research',
            'dataset_analysis':base, 'dataset_contract':{k:data[k] for k in ['schema_id','data_kind','population','scope','target_scope','truth','plan']}, 'conditional_examples':profiles,
            'zero_failure_minimum_samples':{'single_Q':zero_failure_minimum(d,a), 'three_Q':zero_failure_minimum(d,a,3)},
            'sensitivity':sensitivity(),
            'limits':['IID task indicators and target match are external premises, metadata cannot establish them',
                      'fixed sample size and finite candidate family; not anytime-valid repeated calibration',
                      'alpha is calibration confidence error, distinct from delta_Q and delta_L',
                      'joint released-task failure bound is not a posterior or conditional-on-passing guarantee',
                      'synthetic oracle is stipulated truth; no actual deployment B/Q or bounded authorization']}
