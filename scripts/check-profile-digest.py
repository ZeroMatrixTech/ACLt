#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Independent Python/Rust Profile digest and audit field crosschecks."""
import argparse
import copy
import hashlib
import json
import os
import platform
import socket
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.verification_profile import codec as c, profile as p

VECTOR = ROOT/'tests/verification_profile/codec/profile-digest-vectors.json'
# Explicit historical SHA-only rejection cases; frozen vector bytes stay unchanged.
DISABLED_SHA_CASES = frozenset(['stale-schema_version', 'stale-supersedes', 'stale-task_type', 'stale-contract_tuple_constraints', 'stale-admission_predicate', 'stale-verified_claim_spec', 'stale-excluded_claims', 'stale-verification_method', 'stale-method_parameters', 'stale-result_equivalence', 'stale-safety_parameters', 'stale-liveness_parameters', 'stale-assumption_references', 'stale-failure_mapping', 'stale-decision_mapping', 'stale-degradation', 'profile-digest-wrong-digest', 'profile-decision-wrong-digest', 'audit-profile-wrong-digest'])


def fixture():
    reference = dict(id='acl.ecr.baseline', version=[1, 0, 0], digest=b'e'*32)
    value = dict(
        schema_version=2, encoding_profile_id=c.ENCODING,
        profile_id='acl.vp.stats.audit', profile_version=[1, 0, 0], profile_digest=b'\0'*32,
        task_type='acl.tt.stats', contract_tuple_constraints=dict(
            protocol_version_range={0: [0, 5, 0]}, rir_version_range={0: [0, 1, 0]},
            runtime_profile_version_range={0: [1, 0, 0]}, allowed_effects=[], resource_bounds={}),
        admission_predicate='acl.pred.stats@1.0.0',
        excluded_claims=dict(registry_ref=reference, exclusion_ids=[], digest=b'x'*32),
        verification_method='REEXEC_AUDIT_ONLY',
        method_parameters=dict(min_reexecutions=1, evidence_retention='opaque-retention-reference',
                               reachable_terminals=sorted(set(p.TERMINALS[x] for x in p.AUDIT_CONDITIONS),
                                                          key=c.encode)),
        result_equivalence=dict(equivalence_id='acl.eq.exact@1', canonical_encoding_id=c.ENCODING,
                                relation_kind='CANONICAL_BITWISE', totality='TOTAL',
                                undecided_mapping='EQUIVALENCE_UNDECIDED',
                                resource_exceeded_mapping='EQUIVALENCE_RESOURCE_EXCEEDED'),
        cost_parameters={}, documentation={}, assumption_references=[],
        failure_mapping=dict(entries=[
            dict(key=event, value=dict(outcome='INCONCLUSIVE', attribution='NO_ATTRIBUTION'))
            for event in sorted(p.AUDIT_EVENTS, key=c.encode)]),
        decision_mapping=dict(rules=list(p.AUDIT_CONDITIONS), default='UNRESOLVED'))
    return seal(value)


def seal(value):
    value['profile_digest'] = p.profile_digest(value)
    return value


def vectors():
    rows = []
    def add(name, kind, value, valid=True):
        raw = value if isinstance(value, bytes) else c.encode(value)
        row = dict(id=name, kind=kind, cbor_hex=raw.hex(), valid=valid)
        if valid:
            row['expected'] = p.inspect(kind, raw)
        rows.append(row)

    base = fixture()
    add('audit', 'audit-profile', base)
    for method in p.METHODS:
        value = copy.deepcopy(base)
        value['verification_method'] = method
        if method != 'REEXEC_AUDIT_ONLY':
            value['verified_claim_spec'] = {}
        add('digest-'+method, 'profile-digest', seal(value))
        value['decision_mapping']['rules'] = list(p.CONDITIONS)
        if method == 'REEXEC_AUDIT_ONLY':
            value['decision_mapping']['rules'] = list(p.AUDIT_CONDITIONS)
        add('decision-'+method, 'profile-decision', seal(value))
    value = copy.deepcopy(base)
    value.update(schema_version=1, verified_claim_spec='BOTTOM')
    add('legacy-v1-read', 'profile-digest', seal(value))
    add('legacy-not-new-audit', 'audit-profile', value, False)

    for key, value in [('profile_id','acl.vp.other.audit'), ('profile_version',[9,8,7]),
                       ('cost_parameters',dict(cost_model_id='other',c_admission_estimate=[999,1])),
                       ('documentation',dict(text='human notes'))]:
        edited = copy.deepcopy(base)
        edited[key] = value
        add('unhashed-'+key, 'profile-digest', edited)
    for key in p.CONTENT_FIELDS:
        value = copy.deepcopy(base)
        if key in p.OPTIONAL_FIELDS:
            value[key] = dict(test=b'frozen-content')
        elif key == 'schema_version':
            value[key] = 1
        elif key == 'encoding_profile_id':
            continue
        elif key == 'verification_method':
            value[key] = 'DIRECT_VERIFIED'
        else:
            value[key] = [b'changed-frozen-value']
        add('stale-'+key, 'profile-digest', value, False)
    value = copy.deepcopy(base)
    value['supersedes'] = dict(id=base['profile_id'], version=[0,9,0], digest=b's'*32)
    value['degradation'] = dict(target=dict(id='acl.vp.next.audit',version=[1,0,0],digest=b'd'*32),triggers=[])
    value['method_parameters']['audit_coverage_target'] = [1,2]
    add('all-audit-optionals', 'audit-profile', seal(value))

    mutations = [
        ('claim-marker', lambda v:v.update(verified_claim_spec='NO_CLAIM')),
        ('claim-empty', lambda v:v.update(verified_claim_spec={})),
        ('safety-empty', lambda v:v.update(safety_parameters={})),
        ('liveness-empty', lambda v:v.update(liveness_parameters={})),
        ('accept', lambda v:v['decision_mapping']['rules'].insert(1,'ACCEPT')),
        ('missing-condition', lambda v:v['decision_mapping']['rules'].pop()),
        ('duplicate-condition', lambda v:v['decision_mapping']['rules'].append('EVIDENCE_EXHAUSTED')),
        ('condition-order', lambda v:v['decision_mapping']['rules'].reverse()),
        ('default-trusted', lambda v:v['decision_mapping'].update(default='TRUSTED')),
        ('terminal-override', lambda v:v['decision_mapping'].update(terminal='TRUSTED')),
        ('rule-object', lambda v:v['decision_mapping']['rules'].__setitem__(0,dict(condition='VERIFICATION_INVALIDATING',terminal='UNRESOLVED'))),
        ('missing-event', lambda v:v['failure_mapping']['entries'].pop()),
        ('duplicate-event', lambda v:v['failure_mapping']['entries'].append(v['failure_mapping']['entries'][0])),
        ('event-order', lambda v:v['failure_mapping']['entries'].reverse()),
        ('bounded-event', lambda v:v['failure_mapping']['entries'][0].update(key='SNAPSHOT_DIGEST_MISMATCH')),
        ('invalid-sample', lambda v:v['failure_mapping']['entries'][0]['value'].update(outcome='INVALID_SAMPLE')),
        ('bad-attribution', lambda v:v['failure_mapping']['entries'][0]['value'].update(attribution='UNKNOWN')),
        ('invalid-limit', lambda v:v['failure_mapping'].update(max_invalid_samples=1)),
        ('bad-minimum', lambda v:v['method_parameters'].update(min_reexecutions=True)),
        ('bad-rational', lambda v:v['method_parameters'].update(audit_coverage_target=[2,4])),
        ('terminal-set', lambda v:v['method_parameters']['reachable_terminals'].append('TRUSTED')),
        ('terminal-order', lambda v:v['method_parameters']['reachable_terminals'].reverse()),
    ]
    for name, edit in mutations:
        value = copy.deepcopy(base)
        edit(value)
        add(name, 'audit-profile', seal(value), False)

    for kind in ('profile-digest','profile-decision','audit-profile'):
        add(kind+'-wrong-digest',kind,dict(base,profile_digest=b'z'*32),False)
    add('unknown-field','profile-digest',dict(base,unknown=1),False)
    add('nested-header','profile-digest',dict(base,header={}),False)
    add('trailing','profile-digest',c.encode(base)+b'\0',False)
    raw = c.encode(base)
    add('nonminimal-map','profile-digest',b'\xb8'+bytes([raw[0]&31])+raw[1:],False)
    for field,value in [('schema_version',True),('schema_version',3),('profile_version',[1,0,True]),
                        ('profile_digest',b'short'),('encoding_profile_id','unknown')]:
        add('bad-header-'+field+'-'+str(value),'profile-digest',dict(base,**{field:value}),False)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--freeze-vectors', action='store_true')
    args = parser.parse_args()
    if args.freeze_vectors:
        with VECTOR.open('x') as out:
            json.dump(dict(scope='Profile L2 digest and selected audit R rules; not full SchemaValid',
                           vectors=vectors()),out,indent=2)
            out.write('\n')
    rows = json.loads(VECTOR.read_text())['vectors']
    with tempfile.TemporaryDirectory(prefix='aclt-profile-crosscheck-') as name:
        binary = Path(name)/'codec'
        subprocess.run([os.environ.get('RUSTC','rustc'),'--edition=2021','-D','warnings',
                        str(ROOT/'tools/verification_profile/rust/main.rs'),'-o',str(binary)],check=True)
        result = subprocess.run([str(binary)],input=''.join(
            row['kind']+'\t'+row['cbor_hex']+'\n' for row in rows),text=True,
            capture_output=True,check=True,timeout=60)
    outputs = [json.loads(line) for line in result.stdout.splitlines()]
    if len(outputs) != len(rows):
        raise ValueError('Rust response count')
    for row,rust in zip(rows,outputs,strict=True):
        try:
            python = p.inspect(row['kind'],bytes.fromhex(row['cbor_hex']))
        except c.CodecError:
            if row['valid'] or 'error' not in rust:
                raise ValueError('negative disagreement: '+row['id'])
        else:
            if row['id'] in DISABLED_SHA_CASES:
                if python != rust or python['sha_consistency_policy'] != 'DISABLED':
                    raise ValueError('DISABLED policy disagreement: '+row['id'])
                continue
            if not row['valid'] or python != rust or python != dict(row['expected'], sha_consistency_policy='DISABLED'):
                raise ValueError('positive disagreement: '+row['id'])
    source_names = ['tools/verification_profile/profile.py','tools/verification_profile/codec.py',
                    'tools/verification_profile/validator.py','tools/verification_profile/rust/audit_types.json','tools/verification_profile/rust/method_types.json','tools/verification_profile/rust/creation_types.json','tools/verification_profile/rust/selection_types.json','tools/verification_profile/rust/binding_types.json','tools/verification_profile/rust/runtime_types.json','scripts/check-profile-digest.py',
                    'tests/verification_profile/codec/profile-digest-vectors.json',
                    'tests/verification_profile/test_profile_digest.py',
                    'schemas/verification-profile/coverage.json','schemas/verification-profile/inventory.json',
                    'docs/03-protocol/verification-profile-schema.md']
    source_names += [p.relative_to(ROOT).as_posix() for p in (ROOT/'tools/verification_profile/rust').glob('*.rs')]
    report = dict(status='PASS', sha_consistency_policy=c.SHA_CONSISTENCY_STATUS,
                  disabled_sha_cases=sorted(DISABLED_SHA_CASES),
                  cases=len(rows),positive=sum(row['valid'] for row in rows),
                  hostname=socket.gethostname(),kernel=platform.release(),python=sys.version.split()[0],
                  rustc=subprocess.check_output([os.environ.get('RUSTC','rustc'),'--version'],text=True).strip(),
                  results_sha256=hashlib.sha256(c.encode(outputs)).hexdigest(),
                  source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                                 for name in sorted(source_names)},
                  full_schema_valid=False,production_admission=False)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
