# SPDX-License-Identifier: Apache-2.0
"""Verify retained migration summaries; checksums are consistency, not attestation."""
import hashlib
import json
from pathlib import PurePosixPath
import re
import subprocess

SPECS={
 'FM-S1a':dict(stem='FM-S1A-20261028',revision='5780db358a8e8fffcc6c95a1c7a9f5e78783aabc',driver='scripts/check-fm-s1a.py',vectors='tests/formal_migration/vectors.json',cases=179,vector_count=89,vector_count_key='frozen_vectors'),
 'FM-S1b':dict(stem='FM-S1B-20261028',revision='e69764af04eb7c2a9a5c8f8f0942154609e160ed',driver='scripts/check-fm-s1b.py',vectors='tests/formal_migration/policy-vectors.json',cases=196,vector_count=28,vector_count_key='fixed_vectors'),
 'RIR-INDEPENDENT-CORE':dict(stem='RIR-INDEPENDENT-CORE-20261028',revision='d669b02c5209c70faea9b4478a88fb280b0f8735',driver='scripts/check-rir-independent.py',vectors='experiments/aclt-rir-stats-probe/tests/independent-vectors.json',cases=161,vector_count=38,vector_count_key='fixed_vectors')}
ENV_KEYS={'python','python_version','rustc','openssl','scope','source_sha256','cases_detail'}

def need(ok,message):
    if not ok:raise ValueError(message)

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def valid_hash(v):return type(v) is str and re.fullmatch('[0-9a-f]{64}',v) is not None

def load(path):
    def unique(rows):
        d={}
        for k,v in rows:need(k not in d,'duplicate JSON field');d[k]=v
        return d
    def bad(_):raise ValueError('non-JSON constant')
    return json.loads(path.read_text(),object_pairs_hook=unique,parse_constant=bad)

def seal(value):return digest({k:v for k,v in value.items() if k!='summary_sha256'})
def projection(report):return {k:v for k,v in report.items() if k not in ENV_KEYS}

def safe_path(path):
    need(type(path) is str and path!='' and '\\' not in path,'source path type')
    p=PurePosixPath(path)
    need(bool(p.parts) and not p.is_absolute() and '..' not in p.parts and '.' not in p.parts and str(p)==path,'unsafe source path')
    return path

def verify(summary):
    need(type(summary) is dict and type(summary.get('schema_version')) is int and summary['schema_version']==1,'summary schema')
    need(summary.get('id') in SPECS,'unknown evidence id');spec=SPECS[summary['id']]
    need(summary.get('summary_sha256')==seal(summary),'summary checksum mismatch')
    expected_keys={'schema_version','id','recorded_on','evidence_action','source_revision','source_files_sha256','source_manifest_sha256','driver','vector_file','vector_file_sha256','hosts','shared_checks','shared_checks_sha256','cross_host_result_stream_sha256','result_stream_note','hash_definition','provenance_limit','full_conformance','gate_changes','summary_sha256'}
    need(set(summary)==expected_keys,'unknown/missing summary field')
    need(summary.get('source_revision')==spec['revision'],'unexpected source revision')
    need(summary.get('driver')==spec['driver'] and summary.get('vector_file')==spec['vectors'],'unexpected replay input')
    need(summary.get('full_conformance') is False and summary.get('gate_changes') is False,'no conformance/admission upgrade')
    need(summary.get('evidence_action')=='summarize_retained_dualhost_run_no_new_dualhost_execution','historical evidence action')
    source=summary.get('source_files_sha256');need(type(source) is dict and source,'source manifest required')
    for n,h in source.items():safe_path(n);need(valid_hash(h),'source hash format')
    need(summary.get('source_manifest_sha256')==digest(source),'manifest digest')
    need(spec['driver'] in source and spec['vectors'] in source,'missing driver/vector pin')
    need(summary.get('vector_file_sha256')==source[spec['vectors']],'vector hash')
    hosts=summary.get('hosts');need(type(hosts) is list and len(hosts)==2 and [x['label'] for x in hosts]==['A','B'],'exact A/B reports')
    shared=summary.get('shared_checks');need(type(shared) is dict and summary.get('shared_checks_sha256')==digest(shared),'shared checksum')
    for host in hosts:
        need(host.get('exit_code')==0 and type(host['exit_code']) is int,'recorded execution failure')
        report=host.get('report');need(type(report) is dict and host.get('report_projection_sha256')==digest(report),'report projection checksum')
        need(valid_hash(host.get('retained_raw_report_sha256')),'retained raw report hash')
        need(report.get('status')=='PASS' and type(report.get('cases')) is int and report['cases']==spec['cases'],'report status/count')
        need(report.get(spec['vector_count_key'])==spec['vector_count'],'fixed vector count')
        need(projection(report)==shared,'cross-host shared checks differ')
        need(type(report.get('source_sha256')) is dict and report['source_sha256'],'report source pins required')
        for n,h in report['source_sha256'].items():need(source.get(n)==h,'report/deployed source mismatch')
    if summary['id']=='RIR-INDEPENDENT-CORE':
        h=shared.get('results_sha256');need(valid_hash(h) and summary.get('cross_host_result_stream_sha256')==h,'RIR result digest')
        need(shared.get('support',{}).get('full_ADR_0006_conformance') is False and shared['support'].get('production_admission') is False,'RIR scope changed')
    else:
        need(summary.get('cross_host_result_stream_sha256') is None and 'results_sha256' not in shared,'do not fabricate FM stream digest')
        if summary['id']=='FM-S1a':need(shared.get('fresh_signing') is True and shared['frozen_positive']==16 and shared['frozen_negative']==73,'FM-S1a coverage')
        else:need(shared.get('fresh_policy_resigning') is True and shared.get('matrix_cells')==111,'FM-S1b matrix')
    return dict(id=summary['id'],metadata='PASS',cases_per_retained_host=spec['cases'],source_revision=spec['revision'],source_verification='NOT_RUN',local_replay='NOT_RUN',provenance='operator record; checksum consistency is not authentication')

def verify_source(summary,read_blob):
    verify(summary)
    for n,h in summary['source_files_sha256'].items():need(hashlib.sha256(read_blob(summary['source_revision'],n)).hexdigest()==h,'source revision/hash mismatch: '+n)
    return len(summary['source_files_sha256'])

def git_reader(repository):
    def read(revision,path):return subprocess.check_output(['git','show',revision+':'+path],cwd=repository,stderr=subprocess.PIPE)
    return read

def compare_replay(summary,report):
    verify(summary)
    need(projection(report)==summary['shared_checks'],'local replay differs from retained shared checks')
    if summary['id']=='RIR-INDEPENDENT-CORE':
        records=report.get('cases_detail')
        need(type(records) is list and len(records)==report['cases'] and digest(records)==report['results_sha256'],'RIR full case-record digest mismatch')
    need(report.get('source_sha256')==summary['hosts'][0]['report']['source_sha256'],'replay used a different input/source set')
    return True


def verify_audit_plan(root):
    plan=load(root/'docs/07-roadmap/fm-s3-audit-dependencies.json')
    inventory=load(root/plan['inventory']);rules={r['id']:r for r in inventory['rules']}
    rows=plan['rules'];need(len({r['id'] for r in rows})==len(rows),'duplicate audit dependency id')
    need({r['id'] for r in rows}==set(rules)|{'D-08-c'},'omitted or invented SV dependency')
    need(plan['type_a_count']==119 and sum(r['kind']=='A' for r in rows)==119,'Type A coverage accounting')
    need(plan['new_rule_implementations']==0 and plan['global_gate_changes'] is False,'planning cannot close implementation/Gates')
    for n,h in plan['source_sha256'].items():safe_path(n);need(hashlib.sha256((root/n).read_bytes()).hexdigest()==h,'stale normative dependency source')
    cov=load(root/plan['coverage']);implemented=sum(len(v) for v in cov['implemented'].values());partial=sum(len(v) for v in cov['partial'].values())
    need(plan['global_coverage_unchanged']==dict(implemented=implemented,partial=partial,not_implemented=119-implemented-partial),'coverage changed or misreported')
    need(plan['scope_contract']['conditions_in_priority_order']==['VERIFICATION_INVALIDATING','EXECUTION_FAILED','BUDGET_EXHAUSTED','DEADLINE_REACHED','EVIDENCE_EXHAUSTED'],'audit condition order')
    need(plan['scope_contract']['claim_template_allowed'] is False and plan['scope_contract']['eligibility_snapshot_allowed'] is False,'audit cannot create claim/template/population snapshot')
    scope=plan['scope_contract']
    need(scope['method']=='REEXEC_AUDIT_ONLY' and scope['bounded_safety_or_liveness_parameters'] is False and scope['full_phase_contexts_required'] is True,'audit scope/phase guard')
    events={'POSITIVE','NEGATIVE','TIMEOUT','RESOURCE_EXHAUSTED','MALFORMED_SUBMISSION','ENCODING_INVALID','VERIFIER_CRASH','VERIFIER_NONDETERMINISM_DETECTED','OBJECT_UNAVAILABLE','EPOCH_STALE','ASSUMPTION_REVOKED','EQUIVALENCE_UNDECIDED','EQUIVALENCE_RESOURCE_EXCEEDED'}
    need(len(scope['audit_events'])==13 and set(scope['audit_events'])==events,'audit event matrix')
    need(len(scope['terminals'])==4 and set(scope['terminals'])=={'UNRESOLVED','FAILED','FUNDING_EXHAUSTED','EXPIRED'} and scope['default_terminal']=='UNRESOLVED','audit terminal matrix')
    groups=plan['work_packages']
    for row in rows:
        need(row['acceptance']=='PLANNED_NOT_RUN','dependency plan claimed a pass')
        if row['id'] in rules:need(row['kind']==rules[row['id']]['kind'],'evidence kind changed')
        need(row['owner_work_package'] in groups or (row['owner_work_package'] is None and row['id'] in ['SV-15','SV-40']),'unknown or missing dependency owner')
        if row['disposition']=='GUARDED_OUT':need(row['guard_rule_ids'] and set(row['guard_rule_ids'])<=set(rules),'guarded-out obligation lacks boundary guards')
        if row['kind']=='B':need(row['disposition'] in ['GUARDED_OUT','TYPE_B_INTEGRATION_REQUIRED'],'Type B cannot become file conformance')
    for k,g in groups.items():need(k not in g['depends_on'] and set(g['depends_on'])<=set(groups)|{'FM-S2'},'bad work-package dependency')
    visiting=set();done=set()
    def visit(k):
        if k=='FM-S2' or k in done:return
        need(k not in visiting,'cyclic work packages');visiting.add(k)
        for prior in groups[k]['depends_on']:visit(prior)
        visiting.remove(k);done.add(k)
    for k in groups:visit(k)
    need({x['id'] for x in plan['blockers']}=={'AUDIT-WIRE-BOTTOM','AUDIT-PHASE-B-PATH','NONMAINNET-ASSURANCE','AUTHORITATIVE-OBSERVATIONS'},'untracked interface blocker')
    return dict(status='PASS',type_a_rules=119,type_b_plus_interface_rules=sum(r['kind']=='B' for r in rows),new_implementations=0,gate_changes=False)
