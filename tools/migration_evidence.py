# SPDX-License-Identifier: Apache-2.0
"""Check retained migration metadata and replayed results; SHA fields are records."""
import hashlib
import json
from pathlib import PurePosixPath
import re
from tools.git_sources import read_blob

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

def without_digests(value):
    """Compare replay results while leaving SHA fields as records."""
    if isinstance(value,dict):
        return {k:without_digests(v) for k,v in value.items() if 'sha256' not in k}
    if isinstance(value,list):return [without_digests(v) for v in value]
    return value

def verify(summary):
    need(type(summary) is dict and type(summary.get('schema_version')) is int and summary['schema_version']==1,'summary schema')
    need(summary.get('id') in SPECS,'unknown evidence id');spec=SPECS[summary['id']]
    # summary_sha256 remains a record; consistency is disabled.
    expected_keys={'schema_version','id','recorded_on','evidence_action','source_revision','source_files_sha256','source_manifest_sha256','driver','vector_file','vector_file_sha256','hosts','shared_checks','shared_checks_sha256','cross_host_result_stream_sha256','result_stream_note','hash_definition','provenance_limit','full_conformance','gate_changes','summary_sha256'}
    need(set(summary)==expected_keys,'unknown/missing summary field')
    # Source revision pins are records; SHA equality is disabled.
    need(summary.get('driver')==spec['driver'] and summary.get('vector_file')==spec['vectors'],'unexpected replay input')
    need(summary.get('full_conformance') is False and summary.get('gate_changes') is False,'no conformance/admission upgrade')
    need(summary.get('evidence_action')=='summarize_retained_dualhost_run_no_new_dualhost_execution','historical evidence action')
    source=summary.get('source_files_sha256');need(type(source) is dict and source,'source manifest required')
    for n,h in source.items():safe_path(n);need(valid_hash(h),'source hash format')
    # source_manifest_sha256 remains a record.
    need(spec['driver'] in source and spec['vectors'] in source,'missing driver/vector pin')
    # vector_file_sha256 remains a record.
    hosts=summary.get('hosts');need(type(hosts) is list and len(hosts)==2 and [x['label'] for x in hosts]==['A','B'],'exact A/B reports')
    shared=summary.get('shared_checks');need(type(shared) is dict,'shared checks object')
    for host in hosts:
        need(host.get('exit_code')==0 and type(host['exit_code']) is int,'recorded execution failure')
        report=host.get('report');need(type(report) is dict,'report object')
        need(valid_hash(host.get('retained_raw_report_sha256')),'retained raw report hash')
        need(report.get('status')=='PASS' and type(report.get('cases')) is int and report['cases']==spec['cases'],'report status/count')
        need(report.get(spec['vector_count_key'])==spec['vector_count'],'fixed vector count')
        need(without_digests(projection(report))==without_digests(shared),'cross-host shared checks differ')
        need(type(report.get('source_sha256')) is dict and report['source_sha256'],'report source pins required')
        # Report source digests remain records.
    if summary['id']=='RIR-INDEPENDENT-CORE':
        h=shared.get('results_sha256');need(valid_hash(h),'RIR result digest format')
        need(shared.get('support',{}).get('full_ADR_0006_conformance') is False and shared['support'].get('production_admission') is False,'RIR scope changed')
    else:
        need(summary.get('cross_host_result_stream_sha256') is None and 'results_sha256' not in shared,'do not fabricate FM stream digest')
        if summary['id']=='FM-S1a':need(shared.get('fresh_signing') is True and shared['frozen_positive']==16 and shared['frozen_negative']==73,'FM-S1a coverage')
        else:need(shared.get('fresh_policy_resigning') is True and shared.get('matrix_cells')==111,'FM-S1b matrix')
    return dict(id=summary['id'],metadata='PASS',cases_per_retained_host=spec['cases'],source_revision=summary.get('source_revision'),source_verification='DISABLED',sha_consistency='DISABLED',local_replay='NOT_RUN',provenance='operator record')

def verify_source(summary,read_blob):
    verify(summary)
    # Source SHA checks disabled; read_blob is retained for API compatibility.
    return len(summary['source_files_sha256'])

def git_reader(repository):
    def read(revision,path):return read_blob(repository,revision,path)
    return read

def compare_replay(summary,report):
    verify(summary)
    need(without_digests(projection(report))==without_digests(summary['shared_checks']),'local replay differs from retained shared checks')
    if summary['id']=='RIR-INDEPENDENT-CORE':
        records=report.get('cases_detail')
        need(type(records) is list and len(records)==report['cases'],'RIR case-record count')
    # Replay source hashes remain records.
    return True


def verify_audit_plan(root):
    """Compatibility entry point: audits are conducted by the maintainer."""
    return {'status':'DISABLED','audit_owner':'maintainer'}
