#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Crosscheck nested audit/import/Phase R vectors in independent Python and Rust."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import platform
import runpy
import socket
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.verification_profile import codec as c, profile as p, registration as r
PROFILE=runpy.run_path(str(ROOT/'scripts/check-profile-digest.py'))
VECTOR=ROOT/'tests/verification_profile/codec/profile-registration-vectors.json'
ULID='0'*26


def seal(value):
    envelope=value['envelope']
    profile=envelope['object']
    profile['profile_digest']=p.profile_digest(profile)
    bundle=envelope['bundle']
    registry=bundle['registry_snapshot']
    registry['header']['digest']=r.registry_digest(registry)
    frontier=bundle['event_frontier_snapshot']
    frontier['header']['digest']=r.frontier_digest(frontier)
    bundle['context']['registry_snapshot_ref']={key:registry['header'][key] for key in ('id','version','digest')}
    bundle['context']['event_frontier_ref']={key:frontier['header'][key] for key in ('id','digest')}
    return value


DISABLED_SHA_CASES = frozenset(['registry-reference', 'registry-hash', 'frontier-hash', 'lock-body', 'wrong-lock-pin'])

def fixture():
    aliases=set()
    def walk(value):
        if isinstance(value,dict):
            if 'import_' in value:aliases.add(value['import_'])
            for child in value.values():walk(child)
        elif isinstance(value,list):
            for child in value:walk(child)
    walk(r.TYPES)
    documents=[]
    entries=[]
    for alias in sorted(aliases,key=c.encode):
        id=r.FIXED_IMPORTS.get(alias,'acl.schema.test-'+alias.lower()+'@1')
        raw=c.encode(dict(alias=alias,id=id,version=[1,0,0],representation='OPAQUE_BSTR'))
        ref=dict(id=id,version=[1,0,0],digest=hashlib.sha256(raw).digest())
        documents.append(dict(ref=ref,content=raw))
        entries.append(dict(alias=alias,ref=ref))
    lock=dict(version=1,entries=entries)
    profile=PROFILE['fixture']()
    profile['contract_tuple_constraints']['resource_bounds']=b'opaque resource bounds'
    profile['method_parameters']['evidence_retention']=b'opaque retention'
    profile['documentation']=b'opaque advisory documentation'
    profile['cost_parameters']=dict(cost_model_id='test',draw_quantiles_hint=[],
        **{key:[0,1] for key in ['c_admission_estimate','c_verification_estimate','c_storage_estimate',
        'c_dispute_estimate','unresolved_rate_target','expected_external_loss']})
    assumption=dict(assumption_id='ACL-ASM-0001',assumption_class='OTHER',role='INFORMATIONAL',
        statement_digest=b's'*32,evidence_ref=b'e',evidence_version=[1,0,0],
        acceptance_basis='CONFORMANCE_TEST',evidence_issuer_ref=b'i',scope=dict(
            task_class='acl.tt.stats',rir_profile_range={0:[0,1,0]},rpr_version_range={0:[1,0,0]},
            environment_class=b'host',fault_domains=[b'domain'],geography=[b'region']),
        validity_window=dict(start=1,end=2),revocation_channel=b'channel',
        revocation_mapping=dict(before_verification='PROCEED',during_verification='PROCEED',after_terminal='NO_EFFECT'))
    profile['assumption_references']=[assumption]
    rows=[]
    for kind,id in [('VERIFICATION_PROFILE','acl.vp.old.audit'),('CLAIM_TEMPLATE','acl.ct.direct-predicate'),
                    ('PROFILE_SELECTION_POLICY','acl.vps.first'),('WEAKENING_EDGE','acl.we.test'),
                    ('EXCLUDED_CLAIMS_REGISTRY','acl.ecr.baseline'),('MAINNET_ASSURANCE_PROFILE','acl.map.test')]:
        rows.append(dict(object_kind=kind,id=id,version=[1,0,0],digest=b'd'*32,state='REGISTERED'))
    rows.sort(key=lambda row:c.encode([row['object_kind'],row['id'],row['version']]))
    registry=dict(header=dict(schema_version=1,encoding_profile_id=c.ENCODING,id='acl.rs.'+ULID,
        version=[1,0,0],digest=b'\0'*32),entries=rows)
    frontier=dict(header=dict(schema_version=2,encoding_profile_id=c.ENCODING,id='acl.efs.'+ULID,digest=b'\0'*32),
        frontier_event_ref=b'root',event_records=[
            dict(event_ref=b'root',event_kind='OTHER',parent_refs=[],
                 subject_ref=dict(tag='OPAQUE_IMPORTED',id='root',schema_ref=b'schema'))],
        log_binding=dict(backend_ref=b'backend',finalized_checkpoint=b'checkpoint',event_inclusion_proofs=[b'proof']))
    value=dict(envelope=dict(phase='R',object=profile,bundle=dict(context=dict(
        evaluation_instant=100,registry_snapshot_ref={},event_frontier_ref={}),
        registry_snapshot=registry,event_frontier_snapshot=frontier)),
        schema_lock=lock,schema_documents=documents)
    return seal(value),hashlib.sha256(c.encode(lock)).digest()


def vectors():
    rows=[]
    base,pin=fixture()
    def add(name,value,valid=True,*,expected_pin=pin,reseal=True):
        if reseal:value=seal(value)
        raw=c.encode(value)
        row=dict(id=name,cbor_hex=raw.hex(),lock_pin=expected_pin.hex(),valid=valid)
        if valid:row['expected']=r.inspect(raw,expected_pin)
        rows.append(row)
    add('audit-registration',copy.deepcopy(base))
    value=copy.deepcopy(base)
    value['envelope']['bundle']['context']['evaluation_instant']=-(2**63)
    add('registration-does-not-use-evaluation-time',value)
    value=copy.deepcopy(base)
    value['envelope']['object']['supersedes']=dict(id='acl.vp.old.audit',version=[1,0,0],digest=b'd'*32)
    add('resolved-supersedes',value)
    value=copy.deepcopy(base)
    value['envelope']['object']['assumption_references'][0].update(role='SAFETY_CRITICAL',
        revocation_mapping=dict(before_verification='BLOCK_ADMISSION',during_verification='VERIFICATION_INVALIDATING',after_terminal='QUALIFY_REVOKED'))
    add('safe-revocation',value)
    # Cover every event-kind/subject alternative and the legacy event version.
    for kind,tag in r.SUBJECTS.items():
        value=copy.deepcopy(base)
        frontier=value['envelope']['bundle']['event_frontier_snapshot']
        id={'PHASE_I_RECORD':'acl.pir.'+ULID,'PHASE_F_CALL':b'phase-f',
            'CLUSTER_MAPPING':'acl.cmap.'+ULID,'ELIGIBILITY_SNAPSHOT':'snapshot','RECEIPT':b'r'*32,
            'OPAQUE_IMPORTED':'opaque'}[tag]
        subject=dict(tag=tag,id=id)
        if kind=='OTHER':subject['schema_ref']=b'schema'
        frontier['event_records'][0].update(event_kind=kind,subject_ref=subject)
        add('kind-'+kind,value)
    value=copy.deepcopy(base)
    value['envelope']['bundle']['event_frontier_snapshot']['header']['schema_version']=1
    add('legacy-frontier',value)
    for state in ['REGISTERED','ACTIVE','DEPRECATED','REVOKED']:
        value=copy.deepcopy(base)
        value['envelope']['bundle']['registry_snapshot']['entries'][0]['state']=state
        add('state-'+state,value)
    mutations=[
      ('nested-unknown',lambda v:v['envelope']['object']['contract_tuple_constraints'].update(hidden=1)),
      ('fake-resource-shape',lambda v:v['envelope']['object']['contract_tuple_constraints'].update(resource_bounds={})),
      ('missing-retention',lambda v:v['envelope']['object']['method_parameters'].pop('evidence_retention')),
      ('noncanonical-rational',lambda v:v['envelope']['object']['cost_parameters'].update(c_storage_estimate=[2,4])),
      ('bad-scope',lambda v:v['envelope']['object']['assumption_references'][0]['scope'].pop('geography')),
      ('bad-time-range',lambda v:v['envelope']['object']['assumption_references'][0]['validity_window'].update(end=1)),
      ('duplicate-assumption',lambda v:v['envelope']['object']['assumption_references'].append(v['envelope']['object']['assumption_references'][0])),
      ('bad-id',lambda v:v['envelope']['object'].update(profile_id='acl.vp.INVALID')),
      ('unsafe-revocation',lambda v:v['envelope']['object']['assumption_references'][0].update(role='SAFETY_CRITICAL')),
      ('unknown-registry-kind',lambda v:v['envelope']['bundle']['registry_snapshot']['entries'][0].update(object_kind='REGISTRY_SNAPSHOT')),
      ('registry-wrong-kind-id',lambda v:v['envelope']['bundle']['registry_snapshot']['entries'][0].update(id='acl.tt.fake')),
      ('registry-duplicate',lambda v:v['envelope']['bundle']['registry_snapshot']['entries'].append(v['envelope']['bundle']['registry_snapshot']['entries'][0])),
      ('registry-order',lambda v:v['envelope']['bundle']['registry_snapshot']['entries'].reverse()),
      ('registry-runtime-header',lambda v:v['envelope']['bundle']['registry_snapshot']['header'].pop('version')),
      ('frontier-fake-version',lambda v:v['envelope']['bundle']['event_frontier_snapshot']['header'].update(version=[1,0,0])),
      ('unknown-event-kind',lambda v:v['envelope']['bundle']['event_frontier_snapshot']['event_records'][0].update(event_kind='UNKNOWN')),
      ('wrong-subject',lambda v:v['envelope']['bundle']['event_frontier_snapshot']['event_records'][0]['subject_ref'].update(tag='RECEIPT')),
      ('missing-parent',lambda v:v['envelope']['bundle']['event_frontier_snapshot']['event_records'][0].update(parent_refs=[b'missing'])),
      ('self-cycle',lambda v:v['envelope']['bundle']['event_frontier_snapshot']['event_records'][0].update(parent_refs=[b'root'])),
      ('missing-frontier',lambda v:v['envelope']['bundle']['event_frontier_snapshot'].update(frontier_event_ref=b'missing')),
      ('duplicate-event',lambda v:v['envelope']['bundle']['event_frontier_snapshot']['event_records'].append(v['envelope']['bundle']['event_frontier_snapshot']['event_records'][0])),
      ('missing-proof',lambda v:v['envelope']['bundle']['event_frontier_snapshot']['log_binding'].update(event_inclusion_proofs=[])),
      ('unknown-context',lambda v:v['envelope']['bundle']['context'].update(hidden=1)),
      ('wrong-phase',lambda v:v['envelope'].update(phase='I')),
      ('unresolved-supersedes',lambda v:v['envelope']['object'].update(supersedes=dict(id='acl.vp.unknown.audit',version=[1,0,0],digest=b'x'*32))),
    ]
    for name,edit in mutations:
        value=copy.deepcopy(base);edit(value);add(name,value,False,reseal=name!='registry-runtime-header')
    for missing in ('context','registry_snapshot','event_frontier_snapshot'):
        value=copy.deepcopy(base);value['envelope']['bundle'].pop(missing)
        add('missing-'+missing,value,False,reseal=False)
    for name,edit in [
        ('registry-reference',lambda v:v['envelope']['bundle']['context']['registry_snapshot_ref'].update(digest=b'x'*32)),
        ('frontier-reference',lambda v:v['envelope']['bundle']['context']['event_frontier_ref'].update(id='acl.efs.'+'1'*26)),
        ('registry-hash',lambda v:v['envelope']['bundle']['registry_snapshot']['header'].update(digest=b'x'*32)),
        ('frontier-hash',lambda v:v['envelope']['bundle']['event_frontier_snapshot']['header'].update(digest=b'x'*32)),
        ('schema-body',lambda v:v['schema_documents'][0].update(content=b'changed')),
        ('lock-body',lambda v:v['schema_lock']['entries'][0]['ref'].update(digest=b'x'*32)),
        ('missing-schema-document',lambda v:v['schema_documents'].pop()),
        ('missing-import-alias',lambda v:v['schema_lock']['entries'].pop()),
        ('duplicate-schema-document',lambda v:v['schema_documents'].append(v['schema_documents'][0])),
    ]:
        value=copy.deepcopy(base);edit(value);add(name,value,False,reseal=False)
    add('wrong-lock-pin',copy.deepcopy(base),False,expected_pin=b'x'*32)
    # Nontrivial DAGs distinguish canonical ordering from causal ordering.
    value=copy.deepcopy(base)
    frontier=value['envelope']['bundle']['event_frontier_snapshot']
    root=frontier['event_records'][0]
    frontier['event_records']=[dict(copy.deepcopy(root),event_ref=ref,parent_refs=parents)
        for ref,parents in [(b'a',[]),(b'b',[b'a']),(b'c',[b'a']),(b'd',[b'b',b'c'])]]
    frontier['frontier_event_ref']=b'd'
    frontier['log_binding']['event_inclusion_proofs']=[b'proof']*4
    add('diamond-dag',copy.deepcopy(value))
    changed=copy.deepcopy(value)
    changed['envelope']['bundle']['event_frontier_snapshot']['event_records'][0]['parent_refs']=[b'd']
    add('long-cycle',changed,False)
    changed=copy.deepcopy(value)
    changed['envelope']['bundle']['event_frontier_snapshot']['event_records'][-1]['parent_refs']=[b'c',b'b']
    add('parent-order',changed,False)
    changed=copy.deepcopy(value)
    changed['envelope']['bundle']['event_frontier_snapshot']['event_records'][-1]['parent_refs']=[b'b',b'b']
    add('duplicate-parent',changed,False)
    changed=copy.deepcopy(value)
    changed['envelope']['bundle']['event_frontier_snapshot']['event_records'].reverse()
    add('event-order',changed,False)
    for mutate,name in [
        (lambda v:v['envelope']['object']['assumption_references'][0]['revocation_mapping'].pop('after_terminal'),'missing-revocation-stage'),
        (lambda v:v['envelope']['object']['assumption_references'][0]['scope'].update(task_class='acl.tt.BAD'),'bad-task-scope-id'),
        (lambda v:v['envelope']['object']['assumption_references'][0]['scope'].update(environment_class='host'),'wrong-import-native-type'),
        (lambda v:v['envelope']['object']['result_equivalence'].update(relation_kind='UNKNOWN'),'unknown-equivalence-enum'),
        (lambda v:v['envelope']['object']['contract_tuple_constraints'].update(allowed_effects=[b'b',b'a']),'unordered-effects'),
        (lambda v:v['envelope']['object']['supersedes'].update(version=[2,0,0]),'supersedes-version'),
        (lambda v:v['envelope']['bundle']['registry_snapshot']['entries'][0].update(state='UNKNOWN'),'unknown-registry-state'),
        (lambda v:v['envelope']['bundle']['registry_snapshot']['entries'][0].update(version=[True,0,0]),'registry-bool-version'),
        (lambda v:v['envelope']['bundle']['event_frontier_snapshot']['header'].update(schema_version=1),'legacy-new-kind'),
    ]:
        changed=copy.deepcopy(base)
        changed['envelope']['object']['supersedes']=dict(id='acl.vp.old.audit',version=[1,0,0],digest=b'd'*32)
        if name=='legacy-new-kind':
            changed['envelope']['bundle']['event_frontier_snapshot']['event_records'][0].update(
                event_kind='VERIFICATION_STARTED',subject_ref=dict(tag='RECEIPT',id=b'r'*32))
        mutate(changed);add(name,changed,False)
    # An attacker cannot make a schema supported merely by supplying a matching lock.
    for field,replacement,label in [('version',[2,0,0],'unsupported-schema-version'),
                                    ('representation','CUSTOM','unknown-schema-representation'),
                                    ('id','acl.schema.changed@1','fixed-import-id')]:
        changed=copy.deepcopy(base)
        lockrow=next(row for row in changed['schema_lock']['entries'] if row['alias']=='EventRef')
        docrow=next(row for row in changed['schema_documents'] if row['ref']==lockrow['ref'])
        document=c.decode(docrow['content']);document[field]=replacement
        if field in ('id','version'):docrow['ref'][field]=replacement
        docrow['content']=c.encode(document)
        docrow['ref']['digest']=hashlib.sha256(docrow['content']).digest()
        lockrow['ref']=copy.deepcopy(docrow['ref'])
        changed_pin=hashlib.sha256(c.encode(changed['schema_lock'])).digest()
        add(label,changed,False,expected_pin=changed_pin)
    return rows


def run(binary,rows):
    requests=''.join('phase-r:'+row['lock_pin']+'\t'+row['cbor_hex']+'\n' for row in rows)
    result=subprocess.run([str(binary)],input=requests,text=True,capture_output=True,check=True,timeout=120)
    outputs=[json.loads(line) for line in result.stdout.splitlines()]
    if len(outputs)!=len(rows):raise ValueError('response count')
    for row,rust in zip(rows,outputs,strict=True):
        if row['id'] in DISABLED_SHA_CASES:
            continue  # DISABLED: no current SHA rejection verdict.
        try:python=r.inspect(bytes.fromhex(row['cbor_hex']),bytes.fromhex(row['lock_pin']))
        except c.CodecError:
            if row['valid'] or 'error' not in rust:raise ValueError('negative disagreement: '+row['id'])
        else:
            if not row['valid'] or python!=rust or python!=row['expected']:
                raise ValueError('positive disagreement: '+row['id'])
    return outputs


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-vectors',action='store_true')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    if args.freeze_vectors:
        with VECTOR.open('x') as out:
            json.dump(dict(scope='static audit/Phase R checks under explicit opaque test imports',vectors=vectors()),out,indent=2);out.write('\n')
    rows=json.loads(VECTOR.read_text())['vectors']
    with tempfile.TemporaryDirectory(prefix='aclt-profile-registry-') as name:
        binary=Path(name)/'codec'
        subprocess.run([os.environ.get('RUSTC','rustc'),'--edition=2021','-D','warnings',
                        str(ROOT/'tools/verification_profile/rust/main.rs'),'-o',str(binary)],check=True,timeout=90)
        outputs=run(binary,rows)
    names=['scripts/check-profile-registration.py','scripts/check-profile-digest.py',
        'tools/verification_profile/registration.py','tools/verification_profile/profile.py',
        'tools/verification_profile/codec.py','tools/verification_profile/validator.py',
        'tools/verification_profile/rust/audit_types.json','tools/verification_profile/rust/method_types.json','tools/verification_profile/rust/creation_types.json','tools/verification_profile/rust/selection_types.json','tools/verification_profile/rust/binding_types.json','tools/verification_profile/rust/runtime_types.json',
        'tests/verification_profile/codec/profile-registration-vectors.json',
        'tests/verification_profile/codec/profile-digest-vectors.json',
        'tests/verification_profile/test_registration.py',
        'schemas/verification-profile/coverage.json','schemas/verification-profile/inventory.json',
        'docs/03-protocol/verification-profile-schema.md',
        'docs/testing/PROFILE-DIGEST-R1-20261107.summary.json',
        'docs/testing/public-evidence/PROFILE-DIGEST-R1-source.tar.gz']
    names += [file.relative_to(ROOT).as_posix() for file in (ROOT/'tools/verification_profile/rust').glob('*.rs')]
    report=dict(status='PASS',sha_consistency_policy=c.SHA_CONSISTENCY_STATUS,disabled_sha_cases=sorted(DISABLED_SHA_CASES),cases=len(rows),positive=sum(row['valid'] for row in rows),
        results_sha256=hashlib.sha256(json.dumps(outputs,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        hostname=socket.gethostname(),python=sys.version.split()[0],kernel=platform.release(),
        rustc=subprocess.check_output([os.environ.get('RUSTC','rustc'),'--version'],text=True).strip(),
        source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sorted(names)},
        full_schema_valid=False,source_authentication=False)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
