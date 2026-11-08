#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Independent four-method matrices and frozen outcome projection crosscheck."""
import argparse,copy,hashlib,json,os,platform,runpy,socket,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.verification_profile import codec as c,profile as p,registration as reg,registration_rules as common,method_rules as r
PREVIOUS=runpy.run_path(str(ROOT/'scripts/check-registration-rules.py'))
VECTOR=ROOT/'tests/verification_profile/codec/method-matrix-vectors.json'


def extend_imports(value):
    aliases=set()
    def walk(x):
        if isinstance(x,dict):
            if 'import_' in x:aliases.add(x['import_'])
            for v in x.values():walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(r.METHOD_TYPES)
    existing={row['alias'] for row in value['schema_lock']['entries']}
    for alias in sorted(aliases-existing):
        id=reg.FIXED_IMPORTS.get(alias,'acl.schema.test-'+alias.lower()+'@1')
        raw=c.encode(dict(alias=alias,id=id,version=[1,0,0],representation='OPAQUE_BSTR'))
        ref=dict(id=id,version=[1,0,0],digest=hashlib.sha256(raw).digest())
        value['schema_lock']['entries'].append(dict(alias=alias,ref=copy.deepcopy(ref)))
        value['schema_documents'].append(dict(ref=ref,content=raw))
    value['schema_lock']['entries'].sort(key=lambda row:c.encode(row['alias']))
    return hashlib.sha256(c.encode(value['schema_lock'])).digest()


def fixture(method='REEXEC_AUDIT_ONLY',*,soundness='SOUND',certificate=False):
    value,_=PREVIOUS['fixture'](method);pin=extend_imports(value);profile=value['profile']
    find=lambda kind:next(row['assumption_id'] for row in profile['assumption_references'] if row['assumption_class']==kind)
    if method=='DIRECT_VERIFIED':
        profile['method_parameters']=dict(predicate_ref='acl.pred.stats@1.0.0',validator_ref='acl.val.stats@1.0.0',
            predicate_signature=b'(InputRefs,Output,Certificate?)->{ACCEPT,REJECT,UNDECIDED}',soundness_class=soundness,
            certificate_required=certificate,certificate_producer='PROVIDER' if certificate else 'NONE',
            determinism='DETERMINISTIC',effects=[],resource_bound=b'test-resource-bound',verifier_replication_min=1,
            reject_attribution='NO_ATTRIBUTION' if soundness=='SOUND' else 'PROVIDER_FAULT')
    elif method=='PROOF_VERIFIED':
        profile['method_parameters']=dict(proof_system_ref=b'proof-system',public_params_ref=b'public-params',statement_binding_rule=b'binding-rule',
            verifier_ref=b'verifier',soundness_assumptions=[find('PROOF_SYSTEM')],setup_kind='TRANSPARENT',verification_cost_bound=b'test-resource-bound')
    elif method=='REEXEC_BOUNDED':
        profile['method_parameters']=dict(sampling_unit='CORRELATION_CLUSTER',population_definition=b'population',snapshot_schema_ref=b'snapshot-schema',
            randomness_commitment=b'commitment',algorithm_id='finite-population-boundary-lr-v1',arithmetic='exact-rational',
            mixture_weights=[dict(m=3,weight=[1,1])],threshold_comparison='>=')
        profile['safety_parameters']=dict(epsilon_f=[1,20],G=5,B=1,delta_min=[1,5],support_capability_bound_ref=find('SUPPORT_CAPABILITY_BOUND'))
        profile['liveness_parameters']=dict(Q=3,delta_q=[1,20],delta_l=[1,20],q_source='ANCHORED_IN_CLASS',
            calibration_dataset_ref=b'dataset',calibration_task_class='acl.tt.stats',calibration_rir_profile={0:[1,0,0]},
            calibration_rpr_version={0:[1,0,0]},calibration_environment=b'host',calibration_sample_period=[1,2],
            calibration_ref=find('CALIBRATION'),n_required=3,n_policy=5)
    fill_failure(profile)
    profile['decision_mapping']=dict(rules=r.expected_conditions(profile),default='UNRESOLVED')
    value['reachable_terminals']=sorted({p.TERMINALS[x] for x in profile['decision_mapping']['rules']}|{'UNRESOLVED'},key=c.encode)
    return seal(value),pin


def fill_failure(profile):
    method=profile['verification_method'];field='evidence_class' if method=='REEXEC_BOUNDED' else 'outcome';rows=[]
    for event in r.expected_events(profile):
        values=r.OUTCOMES[method]
        outcome=values[0] if event=='POSITIVE' else values[1] if event=='NEGATIVE' else values[2]
        if event in ('VERIFIER_NONDETERMINISM_DETECTED','OBJECT_UNAVAILABLE','EQUIVALENCE_RESOURCE_EXCEEDED','SNAPSHOT_DIGEST_MISMATCH','RANDOMNESS_COMMITMENT_INVALID'):outcome='VERIFICATION_INVALIDATING'
        rows.append(dict(key=event,value={field:outcome,'attribution':'NO_ATTRIBUTION'}))
    profile['failure_mapping']=dict(entries=rows)
    if method=='REEXEC_BOUNDED':profile['failure_mapping']['max_invalid_samples']=2


def seal(value):
    if 'envelope' in value:return PREVIOUS['PREVIOUS']['seal'](value)
    return PREVIOUS['seal'](value)


def audit_fixture():
    value,pin=fixture();base,_=PREVIOUS['PREVIOUS']['fixture']()
    base['envelope']['object']=value['profile'];base['schema_lock']=value['schema_lock'];base['schema_documents']=value['schema_documents']
    return seal(base),pin


def evaluate(mode,raw,pin=b''):
    if mode=='frozen-projection':return r.project(c.decode(raw))
    return (r.inspect_audit if mode=='phase-r5' else r.inspect)(raw,pin)


def vectors():
    rows=[]
    def add(name,value,valid=True,*,pin=b'',mode='method-matrix',reseal=True):
        if reseal and mode!='frozen-projection':value=seal(value)
        raw=c.encode(value);row=dict(id=name,mode=mode,cbor_hex=raw.hex(),valid=valid)
        if mode!='frozen-projection':row['lock_pin']=pin.hex()
        if valid:row['expected']=evaluate(mode,raw,pin)
        rows.append(row)
    variants=[]
    for sound in ('SOUND','SOUND_AND_COMPLETE'):
        for cert in (False,True):variants.append(('DIRECT_VERIFIED',sound,cert))
    variants += [(m,'SOUND',False) for m in p.METHODS[1:]]
    for method,sound,cert in variants:
        suffix=method+'-'+sound+'-'+str(cert);base,pin=fixture(method,soundness=sound,certificate=cert)
        add('valid-'+suffix,copy.deepcopy(base),pin=pin)
        for i in range(len(base['profile']['failure_mapping']['entries'])):
            value=copy.deepcopy(base);event=value['profile']['failure_mapping']['entries'].pop(i)['key']
            add('missing-event-'+event+'-'+suffix,value,False,pin=pin)
        for i in range(len(base['profile']['decision_mapping']['rules'])):
            value=copy.deepcopy(base);condition=value['profile']['decision_mapping']['rules'].pop(i)
            add('missing-condition-'+condition+'-'+suffix,value,False,pin=pin)
        for label,edit in [
            ('duplicate-event',lambda v:v['profile']['failure_mapping']['entries'].insert(0,copy.deepcopy(v['profile']['failure_mapping']['entries'][0]))),
            ('event-order',lambda v:v['profile']['failure_mapping']['entries'].reverse()),
            ('duplicate-condition',lambda v:v['profile']['decision_mapping']['rules'].insert(0,v['profile']['decision_mapping']['rules'][0])),
            ('condition-order',lambda v:v['profile']['decision_mapping']['rules'].reverse()),
            ('terminal-override',lambda v:v['profile']['decision_mapping'].update(terminal='TRUSTED')),
            ('extra-parameter',lambda v:v['profile']['method_parameters'].update(projection={})),
            ('wrong-attribution',lambda v:v['profile']['failure_mapping']['entries'][0]['value'].update(attribution='UNKNOWN')),
            ('wrong-reachable',lambda v:v['reachable_terminals'].pop()),
        ]:
            value=copy.deepcopy(base);edit(value);add(label+'-'+suffix,value,False,pin=pin)
    for method in p.METHODS:
        base,pin=fixture(method)
        for key in list(base['profile']['method_parameters']):
            value=copy.deepcopy(base);value['profile']['method_parameters'].pop(key)
            add('missing-param-'+key+'-'+method,value,False,pin=pin)
        for other in p.METHODS:
            if other==method:continue
            value=copy.deepcopy(base);value['profile']['method_parameters']=fixture(other)[0]['profile']['method_parameters']
            add('swapped-params-'+method+'-'+other,value,False,pin=pin)
        for outcome in sorted({x for xs in r.OUTCOMES.values() for x in xs}-set(r.OUTCOMES[method])):
            value=copy.deepcopy(base);field='evidence_class' if method=='REEXEC_BOUNDED' else 'outcome'
            value['profile']['failure_mapping']['entries'][0]['value'][field]=outcome
            add('foreign-outcome-'+outcome+'-'+method,value,False,pin=pin)
        value=copy.deepcopy(base);value['profile']['failure_mapping']['max_invalid_samples']=0
        if method!='REEXEC_BOUNDED':add('forbidden-max-invalid-'+method,value,False,pin=pin)
        for block in ('safety_parameters','liveness_parameters'):
            value=copy.deepcopy(base)
            if method=='REEXEC_BOUNDED':value['profile'].pop(block)
            else:value['profile'][block]={}
            add('block-presence-'+block+'-'+method,value,False,pin=pin)
        value=copy.deepcopy(base);value['profile']['method_parameters']['reachable_terminals']=base['reachable_terminals']
        if method!='REEXEC_AUDIT_ONLY':add('no-invented-reachable-field-'+method,value,False,pin=pin)
    base,pin=fixture('DIRECT_VERIFIED')
    for label,key,value_ in [('effects','effects',[b'network']),('determinism','determinism','NONDETERMINISTIC'),('replication','verifier_replication_min',0),
                             ('bool','certificate_required',1),('reject-attribution','reject_attribution','PROVIDER_FAULT'),('signature-type','predicate_signature',{}),
                             ('validator-version-overflow','validator_ref','acl.val.stats@18446744073709551616.0.0')]:
        value=copy.deepcopy(base);value['profile']['method_parameters'][key]=value_;add('direct-'+label,value,False,pin=pin)
    value=copy.deepcopy(base);value['profile']['method_parameters']['certificate_required']=True;add('certificate-event-now-required',value,False,pin=pin)
    value=copy.deepcopy(base);value['profile']['method_parameters']['predicate_signature']=b'different opaque test signature'
    add('signature-semantics-not-established',value,pin=pin)
    base,pin=fixture('PROOF_VERIFIED');value=copy.deepcopy(base);value['profile']['method_parameters']['setup_kind']='TRUSTED_SETUP'
    add('proof-setup-structural-only',value,pin=pin)
    base,pin=fixture('REEXEC_BOUNDED')
    for q in ('ANCHORED_IN_CLASS','FAULT_INJECTED_IN_CLASS'):
        value=copy.deepcopy(base);value['profile']['liveness_parameters']['q_source']=q;add('q-source-'+q,value,pin=pin)
    for label,edit in [
        ('q-extrapolated',lambda v:v['profile']['liveness_parameters'].update(q_source='EXTRAPOLATED')),
        ('wrong-time-wire',lambda v:v['profile']['liveness_parameters'].update(calibration_sample_period=dict(start=1,end=2))),
        ('duplicate-mixture',lambda v:v['profile']['method_parameters']['mixture_weights'].append(copy.deepcopy(v['profile']['method_parameters']['mixture_weights'][0]))),
        ('max-invalid-bool',lambda v:v['profile']['failure_mapping'].update(max_invalid_samples=True)),
        ('missing-max-invalid',lambda v:v['profile']['failure_mapping'].pop('max_invalid_samples')),
        ('wrong-row-variant',lambda v:v['profile']['failure_mapping']['entries'][0]['value'].update(outcome='INCONCLUSIVE')),
    ]:
        value=copy.deepcopy(base);edit(value);add(label,value,False,pin=pin)
    for method in p.METHODS:
        sounds=('SOUND','SOUND_AND_COMPLETE') if method=='DIRECT_VERIFIED' else ('',)
        outcomes=r.OUTCOMES[method]+(('NULL_BOUND_EXACTLY_EXCEEDED',) if method=='REEXEC_BOUNDED' else ())
        for sound in sounds:
            for outcome in outcomes:
                for exhausted in (False,True):
                    flags=[(False,False),(True,False),(False,True),(True,True)] if method=='REEXEC_BOUNDED' else [(False,False)]
                    for threshold,null in flags:
                        value=dict(verification_method=method,outcome=outcome,aggregate_exhausted=exhausted)
                        if method=='DIRECT_VERIFIED':value['soundness_class']=sound
                        if method=='REEXEC_BOUNDED':value.update(threshold_met=threshold,null_bound_exactly_exceeded=null)
                        add('projection-'+method+'-'+sound+'-'+outcome+'-'+str((exhausted,threshold,null)),value,mode='frozen-projection')
    for method in p.METHODS:
        value=dict(verification_method=method,outcome=r.OUTCOMES[method][0],aggregate_exhausted=False)
        if method=='DIRECT_VERIFIED':value['soundness_class']='SOUND'
        if method=='REEXEC_BOUNDED':value.update(threshold_met=False,null_bound_exactly_exceeded=False)
        changed=copy.deepcopy(value);changed['projection']={};add('no-projection-override-'+method,changed,False,mode='frozen-projection')
        changed=copy.deepcopy(value);changed['aggregate_exhausted']=1;add('no-nonbool-aggregate-'+method,changed,False,mode='frozen-projection')
    audit,pin=audit_fixture();add('audit-integrated',copy.deepcopy(audit),pin=pin,mode='phase-r5')
    value=copy.deepcopy(audit);value['envelope']['object']['method_parameters']['reachable_terminals'].append('TRUSTED')
    add('audit-no-trusted-terminal',value,False,pin=pin,mode='phase-r5')
    return rows


def run(binary,rows):
    requests=''.join(row['mode']+(':'+row['lock_pin'] if 'lock_pin' in row else '')+'\t'+row['cbor_hex']+'\n' for row in rows)
    result=subprocess.run([str(binary)],input=requests,text=True,capture_output=True,check=True,timeout=180)
    outputs=[json.loads(line) for line in result.stdout.splitlines()]
    if len(outputs)!=len(rows):raise ValueError('response count')
    for row,rust in zip(rows,outputs,strict=True):
        try:python=evaluate(row['mode'],bytes.fromhex(row['cbor_hex']),bytes.fromhex(row.get('lock_pin','')))
        except c.CodecError:
            if row['valid'] or 'error' not in rust:raise ValueError('negative disagreement: '+row['id'])
        else:
            if not row['valid'] or python!=rust or python!=row['expected']:raise ValueError('positive disagreement: '+row['id'])
    return outputs


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--freeze-vectors',action='store_true');parser.add_argument('--report',type=Path);args=parser.parse_args()
    if args.freeze_vectors:
        data=vectors()
        with VECTOR.open('x') as f:json.dump(dict(scope='frozen matrices; opaque test imports and adapter reachable terminals; not complete SchemaValid',vectors=data),f,indent=2);f.write('\n')
    rows=json.loads(VECTOR.read_text())['vectors']
    with tempfile.TemporaryDirectory(prefix='aclt-methods-') as path:
        binary=Path(path)/'codec';subprocess.run([os.environ.get('RUSTC','rustc'),'--edition=2021','-D','warnings',str(ROOT/'tools/verification_profile/rust/main.rs'),'-o',str(binary)],check=True,timeout=120)
        outputs=run(binary,rows)
    names=['scripts/check-method-matrices.py','scripts/check-registration-rules.py','scripts/check-profile-references.py','scripts/check-profile-registration.py','scripts/check-profile-digest.py',
        'tools/verification_profile/method_rules.py','tools/verification_profile/registration_rules.py','tools/verification_profile/references.py','tools/verification_profile/registration.py','tools/verification_profile/profile.py','tools/verification_profile/codec.py','tools/verification_profile/validator.py',
        'tools/verification_profile/rust/audit_types.json','tools/verification_profile/rust/method_types.json','tools/verification_profile/rust/creation_types.json','tests/verification_profile/test_method_matrices.py',
        'registries/verification-profile/excluded_claims.seed.json','schemas/verification-profile/coverage.json','schemas/verification-profile/inventory.json','docs/03-protocol/verification-profile-schema.md']
    names+=[p.relative_to(ROOT).as_posix() for p in (ROOT/'tools/verification_profile/rust').glob('*.rs')]
    names+=[str(Path('tests/verification_profile/codec')/name) for name in ('method-matrix-vectors.json','registration-rules-vectors.json','profile-references-vectors.json','profile-registration-vectors.json','profile-digest-vectors.json')]
    report=dict(status='PASS',cases=len(rows),positive=sum(row['valid'] for row in rows),results_sha256=hashlib.sha256(json.dumps(outputs,sort_keys=True,separators=(',',':')).encode()).hexdigest(),hostname=socket.gethostname(),python=sys.version.split()[0],kernel=platform.release(),rustc=subprocess.check_output([os.environ.get('RUSTC','rustc'),'--version'],text=True).strip(),source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sorted(names)},full_schema_valid=False,source_authentication=False,non_audit_deployment_enabled=False)
    if args.report:args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
