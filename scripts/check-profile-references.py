#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Crosscheck frozen exclusion references and corrected audit Phase R wire types."""
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
from tools.verification_profile import codec as c, references as r
PREVIOUS=runpy.run_path(str(ROOT/'scripts/check-profile-registration.py'))
VECTOR=ROOT/'tests/verification_profile/codec/profile-references-vectors.json'
SEED=ROOT/'registries/verification-profile/excluded_claims.seed.json'


def external(ref,payload):
    raw=c.encode(payload)
    return dict(schema_ref=copy.deepcopy(ref),canonical_bytes=raw,object_digest=hashlib.sha256(raw).digest())


def seal(value):
    registry=value['registry_objects'][0]['object']
    registry['header']['digest']=r.exclusion_registry_digest(registry)
    identity={key:registry['header'][key] for key in ('id','version','digest')}
    selection=value['envelope']['object']['excluded_claims']
    selection['registry_ref']=copy.deepcopy(identity)
    selection['digest']=r.excluded_digest(selection)
    rows=value['envelope']['bundle']['registry_snapshot']['entries']
    for row in rows:
        if row['object_kind']=='EXCLUDED_CLAIMS_REGISTRY':row.update(identity)
    return PREVIOUS['seal'](value)


def fixture():
    value,_=PREVIOUS['fixture']()
    lock=value['schema_lock'];documents=value['schema_documents']
    for row in lock['entries']:
        document=next(doc for doc in documents if doc['ref']==row['ref'])
        description=c.decode(document['content'])
        if row['alias']=='ExternalTypedObject':
            row['alias']='PayloadBytes';description.update(alias='PayloadBytes',id='acl.schema.test-payload-bytes@1')
        if row['alias']=='ExternalVersionedObjectRef':description['representation']='VERSIONED_REF'
        raw=c.encode(description)
        ref=dict(id=description['id'],version=description['version'],digest=hashlib.sha256(raw).digest())
        row['ref']=copy.deepcopy(ref);document.update(ref=copy.deepcopy(ref),content=raw)
    lock['entries'].sort(key=lambda row:c.encode(row['alias']))
    ref=next(row['ref'] for row in lock['entries'] if row['alias']=='PayloadBytes')
    profile=value['envelope']['object']
    for row in profile['assumption_references']:
        row['validity_window']=[row['validity_window']['start'],row['validity_window']['end']]
    frontier=value['envelope']['bundle']['event_frontier_snapshot']
    frontier['event_records'][0]['subject_ref']['schema_ref']=copy.deepcopy(ref)
    frontier['log_binding']=dict(backend_ref=dict(id='acl.backend.test',version=[1,0,0],digest=b'b'*32),
        finalized_checkpoint=external(ref,b'checkpoint'),event_inclusion_proofs=[external(ref,b'proof')])
    seed=json.loads(SEED.read_text())
    registry=dict(header=dict(schema_version=1,encoding_profile_id=c.ENCODING,
        id=seed['registry_id'],version=[int(x) for x in seed['registry_version']],digest=b'\0'*32),entries=seed['entries'])
    value['registry_objects']=[dict(object_kind='EXCLUDED_CLAIMS_REGISTRY',object=registry)]
    profile['excluded_claims']['exclusion_ids']=sorted(r.BASELINE,key=c.encode)
    return seal(value),hashlib.sha256(c.encode(lock)).digest()


def selection_input(value):
    return dict(selection=copy.deepcopy(value['envelope']['object']['excluded_claims']),
        registry=copy.deepcopy(value['registry_objects'][0]['object']),
        registry_snapshot=copy.deepcopy(value['envelope']['bundle']['registry_snapshot']))


def evaluate(mode,raw,pin=None):
    if mode=='excluded-selection':return r.inspect_excluded(raw)
    if mode=='phase-r3':return r.inspect(raw,pin)
    raise ValueError('unknown vector mode')


def vectors():
    rows=[];base,pin=fixture()
    def add(name,value,valid=True,*,mode='phase-r3',expected_pin=pin,reseal=True):
        if reseal:value=seal(value)
        if mode=='excluded-selection':value=selection_input(value)
        raw=c.encode(value)
        row=dict(id=name,mode=mode,cbor_hex=raw.hex(),valid=valid)
        if mode=='phase-r3':row['lock_pin']=expected_pin.hex()
        if valid:row['expected']=evaluate(mode,raw,expected_pin)
        rows.append(row)
    for mode in ('phase-r3','excluded-selection'):add('baseline-'+mode,copy.deepcopy(base),mode=mode)
    value=copy.deepcopy(base)
    value['registry_objects'][0]['object']['entries'].reverse()
    add('registry-array-order-is-content',value)
    value=copy.deepcopy(base)
    value['registry_objects'][0]['object']['header'].update(id='acl.ecr.other',version=[2,0,0])
    add('registry-new-identity-same-content',value)
    value=copy.deepcopy(base)
    value['registry_objects'][0]['object']['entries'][0]['statement']='different frozen text'
    add('registered-new-statement',value)
    value=copy.deepcopy(base)
    value['registry_objects'][0]['object']['entries'].append(dict(exclusion_id='EXC-IMPL-VALIDATOR',category='METHOD_SPECIFIC',statement='test method exclusion'))
    value['envelope']['object']['excluded_claims']['exclusion_ids'].append('EXC-IMPL-VALIDATOR')
    value['envelope']['object']['excluded_claims']['exclusion_ids'].sort(key=c.encode)
    add('registered-additional-exclusion',value,mode='excluded-selection')
    for instant in (-2**63,2**63-1):
        value=copy.deepcopy(base);value['envelope']['bundle']['context']['evaluation_instant']=instant
        add('evaluation-time-'+str(instant),value)
    for a,b in ((-2**63,2**63-1),(-10,0)):
        value=copy.deepcopy(base);value['envelope']['object']['assumption_references'][0]['validity_window']=[a,b]
        add('wire-time-range-'+str(a),value)
    value=copy.deepcopy(base)
    ref=next(row['ref'] for row in value['schema_lock']['entries'] if row['alias']=='ExternalVersionedObjectRef')
    value['envelope']['bundle']['event_frontier_snapshot']['log_binding']['finalized_checkpoint']=external(ref,dict(id='acl.backend.component',version=[1,0,0],digest=b'q'*32))
    add('structured-reference-payload',value)
    value=copy.deepcopy(base);value['envelope']['object']['assumption_references']=[]
    add('no-assumptions',value)
    # Every required baseline ID must be checked explicitly, in both public paths.
    for id in sorted(r.BASELINE):
        for mode in ('phase-r3','excluded-selection'):
            value=copy.deepcopy(base)
            value['envelope']['object']['excluded_claims']['exclusion_ids'].remove(id)
            add('missing-'+id+'-'+mode,value,False,mode=mode)
    for mode in ('phase-r3','excluded-selection'):
        for label,edit in [
          ('unknown-selection',lambda v:v['envelope']['object']['excluded_claims']['exclusion_ids'].append('EXC-TEST-MISSING')),
          ('selected-id-not-in-entries',lambda v:v['registry_objects'][0]['object']['entries'].pop()),
          ('unordered-selection',lambda v:v['envelope']['object']['excluded_claims']['exclusion_ids'].reverse()),
          ('duplicate-selection',lambda v:v['envelope']['object']['excluded_claims']['exclusion_ids'].insert(0,v['envelope']['object']['excluded_claims']['exclusion_ids'][0])),
          ('unknown-registry-field',lambda v:v['registry_objects'][0]['object'].update(extra=1)),
          ('flattened-registry-header',lambda v:v['registry_objects'][0]['object'].update(id='acl.ecr.shadow')),
          ('unknown-registry-category',lambda v:v['registry_objects'][0]['object']['entries'][0].update(category='UNKNOWN')),
          ('missing-registry-statement',lambda v:v['registry_objects'][0]['object']['entries'][0].pop('statement')),
          ('unknown-registry-schema',lambda v:v['registry_objects'][0]['object']['header'].update(schema_version=2)),
          ('free-text-selection',lambda v:v['envelope']['object']['excluded_claims']['exclusion_ids'].append('everything is guaranteed')),
        ]:
            value=copy.deepcopy(base);edit(value)
            if label in ('unknown-selection','free-text-selection'):value['envelope']['object']['excluded_claims']['exclusion_ids'].sort(key=c.encode)
            add(label+'-'+mode,value,False,mode=mode)
        # Do not rebind these mutations: they specifically test existing commitments.
        for label,edit in [
          ('registry-digest',lambda v:v['registry_objects'][0]['object']['header'].update(digest=b'x'*32)),
          ('selection-digest',lambda v:v['envelope']['object']['excluded_claims'].update(digest=b'x'*32)),
          ('selection-ref-version',lambda v:v['envelope']['object']['excluded_claims']['registry_ref'].update(version=[9,0,0])),
          ('registry-ref-id',lambda v:v['registry_objects'][0]['object']['header'].update(id='acl.ecr.unrelated')),
          ('missing-snapshot-registry',lambda v:v['envelope']['bundle']['registry_snapshot']['entries'].__setitem__(slice(None),[row for row in v['envelope']['bundle']['registry_snapshot']['entries'] if row['object_kind']!='EXCLUDED_CLAIMS_REGISTRY'])),
          ('snapshot-registry-version',lambda v:next(row for row in v['envelope']['bundle']['registry_snapshot']['entries'] if row['object_kind']=='EXCLUDED_CLAIMS_REGISTRY').update(version=[9,0,0])),
          ('registry-text-tamper',lambda v:v['registry_objects'][0]['object']['entries'][0].update(statement='tampered')),
        ]:
            value=copy.deepcopy(base);edit(value)
            # Refresh unrelated owners to isolate ref/membership rejection where possible.
            if label in ('missing-snapshot-registry','snapshot-registry-version','selection-digest','selection-ref-version'):PREVIOUS['seal'](value)
            add(label+'-'+mode,value,False,mode=mode,reseal=False)
    mutations=[
      ('view-map-time-range',lambda v:v['envelope']['object']['assumption_references'][0].update(validity_window=dict(start=1,end=2))),
      ('empty-time-range',lambda v:v['envelope']['object']['assumption_references'][0].update(validity_window=[1,1])),
      ('overflow-time-range',lambda v:v['envelope']['object']['assumption_references'][0].update(validity_window=[0,2**63])),
      ('boolean-time-range',lambda v:v['envelope']['object']['assumption_references'][0].update(validity_window=[False,2])),
      ('three-element-time-range',lambda v:v['envelope']['object']['assumption_references'][0].update(validity_window=[1,2,3])),
      ('opaque-checkpoint',lambda v:v['envelope']['bundle']['event_frontier_snapshot']['log_binding'].update(finalized_checkpoint=b'checkpoint')),
      ('opaque-proof',lambda v:v['envelope']['bundle']['event_frontier_snapshot']['log_binding'].update(event_inclusion_proofs=[b'proof'])),
      ('opaque-backend-ref',lambda v:v['envelope']['bundle']['event_frontier_snapshot']['log_binding'].update(backend_ref=b'backend')),
      ('extra-asset',lambda v:v['registry_objects'].append(copy.deepcopy(v['registry_objects'][0]))),
      ('wrong-asset-kind',lambda v:v['registry_objects'][0].update(object_kind='CLAIM_TEMPLATE')),
    ]
    for label,edit in mutations:
        value=copy.deepcopy(base);edit(value);add(label,value,False)
    for target in ('finalized_checkpoint','proof'):
        for label,edit in [
          ('payload-hash',lambda o:o.update(object_digest=b'x'*32)),
          ('unresolved-payload-schema',lambda o:o['schema_ref'].update(digest=b'x'*32)),
          ('unknown-payload-version',lambda o:o['schema_ref'].update(version=[2,0,0])),
          ('unknown-wrapper-field',lambda o:o.update(extra=1)),
          ('missing-canonical-bytes',lambda o:o.pop('canonical_bytes')),
          ('noncanonical-payload',lambda o:o.update(canonical_bytes=b'\x58\x01a',object_digest=hashlib.sha256(b'\x58\x01a').digest())),
          ('wrong-payload-type',lambda o:o.update(canonical_bytes=c.encode(1),object_digest=hashlib.sha256(c.encode(1)).digest())),
        ]:
            value=copy.deepcopy(base);binding=value['envelope']['bundle']['event_frontier_snapshot']['log_binding']
            obj=binding[target] if target!='proof' else binding['event_inclusion_proofs'][0]
            edit(obj);add(target+'-'+label,value,False)
    value=copy.deepcopy(base);value.pop('registry_objects');add('missing-assets',value,False,reseal=False)
    value=copy.deepcopy(base);value['registry_objects']=[];add('empty-assets',value,False,reseal=False)
    add('wrong-pin',copy.deepcopy(base),False,expected_pin=b'x'*32)
    # Reject an already self-consistent but unsupported import representation.
    value=copy.deepcopy(base)
    row=next(row for row in value['schema_lock']['entries'] if row['alias']=='ExternalVersionedObjectRef')
    doc=next(doc for doc in value['schema_documents'] if doc['ref']==row['ref'])
    description=c.decode(doc['content']);description['representation']='OPAQUE_BSTR'
    doc['content']=c.encode(description);doc['ref']['digest']=hashlib.sha256(doc['content']).digest()
    row['ref']=copy.deepcopy(doc['ref'])
    add('structured-schema-required',value,False,expected_pin=hashlib.sha256(c.encode(value['schema_lock'])).digest())
    for alias,new_alias,representation,label in [
        ('PayloadBytes','PayloadBytes','VERSIONED_REF','structured-import-wrong-alias'),
        ('PayloadBytes','ExternalTypedObject','OPAQUE_BSTR','legacy-opaque-wrapper-alias')]:
        value=copy.deepcopy(base)
        row=next(row for row in value['schema_lock']['entries'] if row['alias']==alias)
        doc=next(doc for doc in value['schema_documents'] if doc['ref']==row['ref'])
        description=c.decode(doc['content']);description.update(alias=new_alias,representation=representation)
        row['alias']=new_alias;doc['content']=c.encode(description)
        doc['ref']['digest']=hashlib.sha256(doc['content']).digest();row['ref']=copy.deepcopy(doc['ref'])
        value['schema_lock']['entries'].sort(key=lambda row:c.encode(row['alias']))
        add(label,value,False,expected_pin=hashlib.sha256(c.encode(value['schema_lock'])).digest())
    return rows


def run(binary,rows):
    lines=[]
    for row in rows:
        mode=row['mode']+(':'+row['lock_pin'] if row['mode']=='phase-r3' else '')
        lines.append(mode+'\t'+row['cbor_hex']+'\n')
    result=subprocess.run([str(binary)],input=''.join(lines),capture_output=True,text=True,check=True,timeout=120)
    outputs=[json.loads(line) for line in result.stdout.splitlines()]
    if len(outputs)!=len(rows):raise ValueError('response count')
    for row,rust in zip(rows,outputs,strict=True):
        try:python=evaluate(row['mode'],bytes.fromhex(row['cbor_hex']),bytes.fromhex(row.get('lock_pin','')))
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
        rows=vectors()
        with VECTOR.open('x') as f:json.dump(dict(scope='exclusion objects and scoped audit Phase R wire/import checks',vectors=rows),f,indent=2);f.write('\n')
    rows=json.loads(VECTOR.read_text())['vectors']
    with tempfile.TemporaryDirectory(prefix='aclt-profile-refs-') as directory:
        binary=Path(directory)/'codec'
        subprocess.run([os.environ.get('RUSTC','rustc'),'--edition=2021','-D','warnings',str(ROOT/'tools/verification_profile/rust/main.rs'),'-o',str(binary)],check=True,timeout=90)
        outputs=run(binary,rows)
    names=['scripts/check-profile-references.py','scripts/check-profile-registration.py','scripts/check-profile-digest.py',
      'tools/verification_profile/references.py','tools/verification_profile/registration.py','tools/verification_profile/profile.py',
      'tools/verification_profile/codec.py','tools/verification_profile/validator.py','tools/verification_profile/rust/audit_types.json','tools/verification_profile/rust/method_types.json','tools/verification_profile/rust/creation_types.json',
      'tests/verification_profile/codec/profile-references-vectors.json','tests/verification_profile/codec/profile-registration-vectors.json',
      'tests/verification_profile/codec/profile-digest-vectors.json','tests/verification_profile/test_references.py',
      'schemas/verification-profile/coverage.json','schemas/verification-profile/inventory.json',
      'registries/verification-profile/excluded_claims.seed.json','docs/03-protocol/verification-profile-schema.md']
    names += [p.relative_to(ROOT).as_posix() for p in (ROOT/'tools/verification_profile/rust').glob('*.rs')]
    report=dict(status='PASS',cases=len(rows),positive=sum(row['valid'] for row in rows),
      results_sha256=hashlib.sha256(json.dumps(outputs,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
      hostname=socket.gethostname(),python=sys.version.split()[0],kernel=platform.release(),
      rustc=subprocess.check_output([os.environ.get('RUSTC','rustc'),'--version'],text=True).strip(),
      source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sorted(names)},
      full_schema_valid=False,source_authentication=False,official_schema_registration=False)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
