# SPDX-License-Identifier: Apache-2.0
"""Run and verify the three local B/Q research slices; no deployment approval."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

SHA_CONSISTENCY_STATUS="DISABLED"

ROOT=Path(__file__).resolve().parents[1]
SLICES={'boundaries':'check-bq-boundaries.py','calibration':'check-bq-calibration.py','readiness':'check-bq-readiness.py'}
SAVED={'boundaries':'bq-boundary-slice1-20261026.json','calibration':'bq-calibration-slice2-20261026.json','readiness':'bq-readiness-slice3-20261026.json'}


def sha(path):
    if path.is_symlink() or not path.is_file():raise ValueError('regular file required')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise ValueError('duplicate evidence JSON key')
            result[k]=v
        return result
    def reject(x):raise ValueError('non-exact JSON number')
    return json.loads(path.read_text(),object_pairs_hook=pairs,parse_float=reject,parse_constant=reject)


def dump(path,data):
    with path.open('x') as f:json.dump(data,f,indent=2);f.write('\n')


def retained(root,name):
    rel=Path(name)
    if rel.is_absolute() or '..' in rel.parts or rel.as_posix()!=name:raise ValueError('unsafe evidence path')
    p=root/rel
    if any(x.is_symlink() for x in [p,*p.parents]):raise ValueError('symlink evidence path')
    sha(p);return p


def source_lock():
    result={}
    for name in SAVED.values():
        path='docs/testing/'+name;report=read(ROOT/path);result[path]=sha(ROOT/path)
        for group in ['source_sha256','project_experimental_artifacts_sha256']:
            for n,h in report.get(group,{}).items():
                result[n]=h
    for n in ['scripts/bq-work4.py','tests/workflow/test_bq_work4.py']:result[n]=sha(ROOT/n)
    return dict(sorted(result.items()))


def continuity(reports):
    a,b,c=[reports[k] for k in SLICES]
    if a['parameters']!={'G':10,'B':3,'Q':8,'epsilon_F':'1/5'} or a['case_count']!=8:raise ValueError('boundary scope drift')
    cases={x['id']:x for x in a['cases']}
    capacity={x['actual_C']:x['false_acceptance'] for x in cases['BQ1-CAPACITY']['rates']}
    for row in b['sensitivity']['fixed_old_profile_capability_miss']:
        if capacity[row['actual_C']]!=row['frozen_old_false_acceptance']:raise ValueError('capacity continuity drift')
    budget=cases['BQ1-Q-BUDGET']
    loss=b['sensitivity']['fixed_old_profile_support_loss'][1]
    if budget['actual_probability_at_budget']!=loss['frozen_six_draw_liveness'] or budget['required_draws_under_Q']!=6:raise ValueError('liveness continuity drift')
    if b['zero_failure_minimum_samples']!={'single_Q':59,'three_Q':80}:raise ValueError('calibration scope drift')
    if b['dataset_analysis']['empirical_calibration_established'] or b['dataset_analysis']['automatic_deployment_eligibility']:raise ValueError('synthetic data promoted')
    if c['case_counts']!={'requirements':14,'inventories':12,'precreate':8,'lifecycle':19}:raise ValueError('review scope drift')
    if c['inventory_assessment']['research_ceiling']!='NO_REEXEC_REVIEW_CANDIDATE' or c['automatic_deployment_eligibility'] or c['changes_runtime_capability']:raise ValueError('review promoted to capability')
    synthetic=next(x for x in c['stipulated_inventory_cases'] if x['case']=='synthetic_Q_not_deployment')
    if synthetic['result']['research_ceiling']!='AUDIT_ONLY_REVIEW_CANDIDATE':raise ValueError('synthetic Q boundary changed')
    for x in c['lifecycle_projections']:
        if x['profile_switch_authorized'] or x['new_TRUSTED_authorized'] or x['writes_runtime_state']:raise ValueError('lifecycle projection gained authority')
        if x['stage']=='TERMINAL' and x['terminal_preserved']!='TRUSTED':raise ValueError('terminal rewritten')
    return {'G':10,'B':3,'Q':8,'epsilon_F':'1/5','capacity_C5_vote_cap3':'43/126',
            'actual_M7_six_draw_liveness':'53/60','zero_failure_samples_single_Q':59,'zero_failure_samples_three_Q':80,
            'review_cases':c['case_counts'],'real_BQ_established':False,'capability_changed':False,
            'scope':'exact countermodels, synthetic conditional calibration and non-authoritative evidence review'}


def compute(directory):
    reports={}
    for label,script in SLICES.items():
        dest=directory/(label+'.json')
        with (directory/(label+'.log')).open('xb') as f:
            subprocess.run([sys.executable,'-B',ROOT/'scripts'/script,'--report',dest],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=60)
        reports[label]=read(dest)
    return reports


def inventory(root):
    result={}
    for p in sorted(root.rglob('*')):
        n=p.relative_to(root).as_posix()
        if p.is_symlink():raise ValueError('symlink evidence')
        if p.is_file() and n not in {'suite.json','inventory.json'}:result[n]=sha(p)
    return result


def verify(root):
    source_record = root/'source-lock.json'
    if source_record.exists() or source_record.is_symlink():
        read(retained(root,'source-lock.json'))
    reports={label:read(retained(root,label+'.json')) for label in SLICES}
    with tempfile.TemporaryDirectory(prefix='aclt-bq-verify-') as tmp:
        replay=compute(Path(tmp))
        if replay!=reports:raise ValueError('retained slice report drift from offline recomputation')
    result={'sha_consistency':SHA_CONSISTENCY_STATUS,'status':'PASS','source_files':len(source_lock()),'slices_recomputed':3,'continuity':continuity(reports),
            'verification_kind':'offline deterministic mathematical recomputation; no network, guest or runtime writes'}
    if read(retained(root,'suite.json'))!=result:raise ValueError('suite summary drift')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    r=sub.add_parser('run');r.add_argument('--output',type=Path,required=True)
    v=sub.add_parser('verify');v.add_argument('--evidence',type=Path,required=True);v.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    if a.command=='run':
        out=a.output.resolve()
        if out.is_relative_to(ROOT):p.error('new output outside repository required')
        lock=source_lock();out.mkdir(parents=True,exist_ok=False);dump(out/'source-lock.json',lock)
        reports=compute(out)
        result={'sha_consistency':SHA_CONSISTENCY_STATUS,'status':'PASS','source_files':len(lock),'slices_recomputed':3,'continuity':continuity(reports),
                'verification_kind':'offline deterministic mathematical recomputation; no network, guest or runtime writes'}
        dump(out/'suite.json',result);dump(out/'inventory.json',inventory(out))
        verify(out)
        print('PASS: three B/Q research slices and cross-slice boundaries reproduced')
    else:
        if a.report.exists() or a.report.resolve().is_relative_to(a.evidence.resolve()):p.error('new report outside retained evidence required')
        result=verify(a.evidence.resolve());dump(a.report,result)
        print('PASS: retained B/Q research evidence recomputed offline; no approval')


if __name__=='__main__':main()
