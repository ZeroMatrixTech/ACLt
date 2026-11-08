#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Crosscheck selected common Phase R rules and fixed audit R4 integration."""
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
from tools.verification_profile import codec as c, profile as p, registration as reg, registration_rules as r
PREVIOUS=runpy.run_path(str(ROOT/'scripts/check-profile-references.py'))
VECTOR=ROOT/'tests/verification_profile/codec/registration-rules-vectors.json'


def fixture(method='REEXEC_AUDIT_ONLY'):
    base,pin=PREVIOUS['fixture']()
    profile=copy.deepcopy(base['envelope']['object'])
    profile['verification_method']=method
    template=profile['assumption_references'][0]
    for index,(kind,role) in enumerate(sorted(r.REQUIRED[method]),2):
        row=copy.deepcopy(template)
        row.update(assumption_id='ACL-ASM-%04d'%index,assumption_class=kind,role=role,
            statement_digest=hashlib.sha256(kind.encode()).digest())
        if role=='SAFETY_CRITICAL':row['revocation_mapping']=copy.deepcopy(r.SAFE_REVOCATION)
        profile['assumption_references'].append(row)
    if method!='REEXEC_AUDIT_ONLY':
        # Unexamined method/claim blocks are test placeholders, not SchemaValid Profiles.
        profile.update(verified_claim_spec={},method_parameters={},failure_mapping={})
        if method=='REEXEC_BOUNDED':profile.update(safety_parameters={},liveness_parameters={})
    value=dict(profile=profile,registry_snapshot=copy.deepcopy(base['envelope']['bundle']['registry_snapshot']),
        schema_lock=copy.deepcopy(base['schema_lock']),schema_documents=copy.deepcopy(base['schema_documents']),
        assumption_set_digest=b'\0'*32)
    return seal(value),pin


def seal(value):
    value['profile']['profile_digest']=p.profile_digest(value['profile'])
    value['registry_snapshot']['header']['digest']=reg.registry_digest(value['registry_snapshot'])
    value['assumption_set_digest']=r.assumption_set_digest(value['profile']['assumption_references'])
    return value


def evaluate(mode,raw,pin):
    return (r.inspect_audit if mode=='phase-r4' else r.inspect)(raw,pin)


def vectors():
    rows=[]
    def add(name,value,valid=True,*,mode='registration-rules',pin,reseal=True):
        if reseal:
            if mode=='phase-r4':value=PREVIOUS['seal'](value)
            else:value=seal(value)
        raw=c.encode(value)
        row=dict(id=name,mode=mode,cbor_hex=raw.hex(),lock_pin=pin.hex(),valid=valid)
        if valid:row['expected']=evaluate(mode,raw,pin)
        rows.append(row)
    for method in p.METHODS:
        base,pin=fixture(method)
        add('common-'+method,copy.deepcopy(base),pin=pin)
        value=copy.deepcopy(base);value['profile']['assumption_references'].reverse()
        add('permuted-assumptions-'+method,value,pin=pin)
        value=copy.deepcopy(base);value['profile']['assumption_references'][0]['scope'].update(fault_domains=[],geography=[])
        add('empty-scope-dimensions-'+method,value,pin=pin)
        value=copy.deepcopy(base);value['profile']['supersedes']=dict(id='acl.vp.old.audit',version=[1,0,0],digest=b'd'*32)
        add('supersedes-'+method,value,pin=pin)
        for field in sorted(r.REVOCATION_FIELDS):
            value=copy.deepcopy(base);value['profile']['assumption_references'][0]['revocation_mapping'].pop(field)
            add('missing-stage-'+field+'-'+method,value,False,pin=pin)
        for field in sorted(r.SCOPE_FIELDS):
            value=copy.deepcopy(base);value['profile']['assumption_references'][0]['scope'].pop(field)
            add('missing-scope-'+field+'-'+method,value,False,pin=pin)
        for kind,role in sorted(r.REQUIRED[method]):
            for label in ('missing','wrong-role'):
                value=copy.deepcopy(base)
                row=next(row for row in value['profile']['assumption_references'] if row['assumption_class']==kind)
                if label=='missing':value['profile']['assumption_references'].remove(row)
                else:row['role']='INFORMATIONAL'
                add(label+'-'+kind+'-'+method,value,False,pin=pin)
        for field,new_value in [('id','acl.vp.missing.audit'),('version',[9,0,0]),('digest',b'x'*32)]:
            value=copy.deepcopy(base);value['profile']['supersedes']=dict(id='acl.vp.old.audit',version=[1,0,0],digest=b'd'*32)
            value['profile']['supersedes'][field]=new_value
            add('unresolved-supersedes-'+field+'-'+method,value,False,pin=pin)
        value=copy.deepcopy(base);value['profile']['supersedes']={'digest':b'd'*32}
        add('digest-only-supersedes-'+method,value,False,pin=pin)
        value=copy.deepcopy(base);value['profile']['post_execution_predicate']={}
        add('removed-post-execution-predicate-'+method,value,False,pin=pin,reseal=False)
    base,pin=fixture()
    for method in ('ATTESTED','',True,3,[]):
        value=copy.deepcopy(base);value['profile']['verification_method']=method
        add('unknown-method-'+str(method),value,False,pin=pin,reseal=False)
    value=copy.deepcopy(base);value['profile'].pop('verification_method')
    add('missing-method',value,False,pin=pin,reseal=False)
    for before in ('BLOCK_ADMISSION','PROCEED'):
        for during in ('VERIFICATION_INVALIDATING','PROCEED'):
            for after in ('QUALIFY_REVOKED','QUALIFY_WEAKENED','NO_EFFECT'):
                mapping=dict(before_verification=before,during_verification=during,after_terminal=after)
                value=copy.deepcopy(base);value['profile']['assumption_references'][0]['revocation_mapping']=mapping
                add('informational-map-'+before+'-'+during+'-'+after,value,pin=pin)
                value=copy.deepcopy(value);value['profile']['assumption_references'][0]['role']='SAFETY_CRITICAL'
                add('safety-map-'+before+'-'+during+'-'+after,value,mapping==r.SAFE_REVOCATION,pin=pin)
    for label,edit in [
        ('extra-scope',lambda v:v['profile']['assumption_references'][0]['scope'].update(extra=1)),
        ('extra-stage',lambda v:v['profile']['assumption_references'][0]['revocation_mapping'].update(extra='NO_EFFECT')),
        ('duplicate-assumption-id',lambda v:v['profile']['assumption_references'].append(copy.deepcopy(v['profile']['assumption_references'][0]))),
        ('bad-scope-import',lambda v:v['profile']['assumption_references'][0]['scope'].update(environment_class='host')),
    ]:
        value=copy.deepcopy(base);edit(value);add(label,value,False,pin=pin)
    ref=dict(id='acl.vp.old.audit',version=[1,0,0],digest=b'd'*32)
    for triggers in ([],*[[name] for name in sorted(r.TRIGGERS)],list(sorted(r.TRIGGERS)),['POPULATION_TOO_SMALL']*2):
        value=copy.deepcopy(base);value['profile']['degradation']=dict(target=ref,triggers=triggers)
        add('allowed-triggers-'+str(triggers),value,pin=pin)
    for invalid in (['UNKNOWN'],[1],'POPULATION_TOO_SMALL',{}):
        value=copy.deepcopy(base);value['profile']['degradation']=dict(target=ref,triggers=invalid)
        add('bad-triggers-'+str(invalid),value,False,pin=pin)
    value=copy.deepcopy(base);value['assumption_set_digest']=b'x'*32
    add('wrong-set-digest',value,False,pin=pin,reseal=False)
    for field,new_value in [('assumption_id','ACL-ASM-9999'),('statement_digest',b'x'*32)]:
        value=copy.deepcopy(base);old=value['assumption_set_digest'];value['profile']['assumption_references'][0][field]=new_value
        seal(value);value['assumption_set_digest']=old
        add('stale-set-digest-'+field,value,False,pin=pin,reseal=False)
    value=copy.deepcopy(base);value['profile']['assumption_references']=[]
    add('empty-assumption-set',value,pin=pin)
    value=copy.deepcopy(base);value['profile']['assumption_references'][0]['evidence_version']=[2,0,0]
    add('metadata-does-not-enter-static-set',value,pin=pin)
    audit,pin=PREVIOUS['fixture']()
    add('audit-integration',copy.deepcopy(audit),mode='phase-r4',pin=pin)
    value=copy.deepcopy(audit);value['envelope']['object']['assumption_references']=[]
    add('audit-empty-assumptions',value,mode='phase-r4',pin=pin)
    value=copy.deepcopy(audit);value['envelope']['object']['supersedes']=ref
    add('audit-supersedes',value,mode='phase-r4',pin=pin)
    value=copy.deepcopy(audit);value['envelope']['object']['degradation']=dict(target=ref,triggers=['POPULATION_TOO_SMALL'])
    add('audit-degradation-guard',value,False,mode='phase-r4',pin=pin)
    for method in p.METHODS[:-1]:
        value=copy.deepcopy(audit);value['envelope']['object']=fixture(method)[0]['profile']
        add('audit-other-method-guard-'+method,value,False,mode='phase-r4',pin=pin)
    for label,edit in [
        ('audit-missing-scope',lambda v:v['envelope']['object']['assumption_references'][0]['scope'].pop('geography')),
        ('audit-missing-stage',lambda v:v['envelope']['object']['assumption_references'][0]['revocation_mapping'].pop('after_terminal')),
        ('audit-unsafe-revocation',lambda v:v['envelope']['object']['assumption_references'][0].update(role='SAFETY_CRITICAL')),
    ]:
        value=copy.deepcopy(audit);edit(value);add(label,value,False,mode='phase-r4',pin=pin)
    return rows


def run(binary,rows):
    requests=''.join(row['mode']+':'+row['lock_pin']+'\t'+row['cbor_hex']+'\n' for row in rows)
    result=subprocess.run([str(binary)],input=requests,text=True,capture_output=True,check=True,timeout=120)
    outputs=[json.loads(line) for line in result.stdout.splitlines()]
    if len(outputs)!=len(rows):raise ValueError('response count')
    for row,rust in zip(rows,outputs,strict=True):
        try:python=evaluate(row['mode'],bytes.fromhex(row['cbor_hex']),bytes.fromhex(row['lock_pin']))
        except c.CodecError:
            if row['valid'] or 'error' not in rust:raise ValueError('negative disagreement: '+row['id'])
        else:
            if not row['valid'] or python!=rust or python!=row['expected']:raise ValueError('positive disagreement: '+row['id'])
    return outputs


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-vectors',action='store_true');parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    if args.freeze_vectors:
        rows=vectors()
        with VECTOR.open('x') as f:json.dump(dict(scope='selected common registration rules; non-audit parameter/claim blocks are unvalidated placeholders',vectors=rows),f,indent=2);f.write('\n')
    rows=json.loads(VECTOR.read_text())['vectors']
    with tempfile.TemporaryDirectory(prefix='aclt-register-rules-') as path:
        binary=Path(path)/'codec'
        subprocess.run([os.environ.get('RUSTC','rustc'),'--edition=2021','-D','warnings',str(ROOT/'tools/verification_profile/rust/main.rs'),'-o',str(binary)],check=True,timeout=90)
        outputs=run(binary,rows)
    names=['scripts/check-registration-rules.py','scripts/check-profile-references.py','scripts/check-profile-registration.py','scripts/check-profile-digest.py',
      'tools/verification_profile/registration_rules.py','tools/verification_profile/references.py','tools/verification_profile/registration.py',
      'tools/verification_profile/profile.py','tools/verification_profile/codec.py','tools/verification_profile/validator.py','tools/verification_profile/rust/audit_types.json','tools/verification_profile/rust/method_types.json','tools/verification_profile/rust/creation_types.json',
      'tests/verification_profile/codec/registration-rules-vectors.json','tests/verification_profile/codec/profile-references-vectors.json',
      'tests/verification_profile/codec/profile-registration-vectors.json','tests/verification_profile/codec/profile-digest-vectors.json',
      'tests/verification_profile/test_registration_rules.py','schemas/verification-profile/coverage.json','schemas/verification-profile/inventory.json',
      'registries/verification-profile/excluded_claims.seed.json','docs/03-protocol/verification-profile-schema.md',
      'docs/testing/PROFILE-REFERENCES-R3-20261108.summary.json','docs/testing/public-evidence/PROFILE-REFERENCES-R3-source.tar.gz']
    names += [p.relative_to(ROOT).as_posix() for p in (ROOT/'tools/verification_profile/rust').glob('*.rs')]
    report=dict(status='PASS',cases=len(rows),positive=sum(row['valid'] for row in rows),
        results_sha256=hashlib.sha256(json.dumps(outputs,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        hostname=socket.gethostname(),python=sys.version.split()[0],kernel=platform.release(),
        rustc=subprocess.check_output([os.environ.get('RUSTC','rustc'),'--version'],text=True).strip(),
        source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sorted(names)},
        full_schema_valid=False,source_authentication=False,non_audit_deployment_enabled=False)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
