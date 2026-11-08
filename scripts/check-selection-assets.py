#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Crosscheck registration assets, selection/binding rules and explicit-input test helpers."""
import argparse,copy,hashlib,json,os,platform,runpy,socket,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.verification_profile import codec as c,profile as p,registration as reg,selection as r
PREVIOUS=runpy.run_path(str(ROOT/'scripts/check-method-matrices.py'))
VECTOR=ROOT/'tests/verification_profile/codec/selection-assets-vectors.json'


def extend_imports(base):
    aliases=set()
    def walk(x):
        if isinstance(x,dict):
            if 'import_' in x:aliases.add(x['import_'])
            for y in x.values():walk(y)
        elif isinstance(x,list):
            for y in x:walk(y)
    walk(r.EXTRA);existing={x['alias'] for x in base['schema_lock']['entries']}
    for alias in sorted(aliases-existing):
        ident=reg.FIXED_IMPORTS.get(alias,'acl.schema.test-'+alias.lower()+'@1');raw=c.encode(dict(alias=alias,id=ident,version=[1,0,0],representation='OPAQUE_BSTR'))
        ref=dict(id=ident,version=[1,0,0],digest=hashlib.sha256(raw).digest());base['schema_lock']['entries'].append(dict(alias=alias,ref=copy.deepcopy(ref)));base['schema_documents'].append(dict(ref=ref,content=raw))
    base['schema_lock']['entries'].sort(key=lambda x:c.encode(x['alias']))


def fixture(operation='policy',method='REEXEC_BOUNDED'):
    base,_=PREVIOUS['fixture'](method);extend_imports(base);source=base['profile'];source['profile_id']='acl.vp.stats.bounded' if method=='REEXEC_BOUNDED' else source['profile_id']
    target=PREVIOUS['fixture']()[0]['profile'];target['profile_id']='acl.vp.stats.audit'
    snapshot=base['registry_snapshot'];profiles=[source,target] if method=='REEXEC_BOUNDED' else [source]
    if method=='REEXEC_BOUNDED':source['degradation']=dict(target=r.profile_ref(target),triggers=['POPULATION_TOO_SMALL'])
    for profile in profiles:profile['profile_digest']=p.profile_digest(profile)
    header=lambda ident:dict(schema_version=1,encoding_profile_id=c.ENCODING,id=ident,version=[1,0,0],digest=b'\0'*32)
    edge=dict(header=header('acl.we.bounded-to-audit'),source=r.profile_ref(source),target=r.profile_ref(target),edge_class='AUTO_DECIDABLE')
    policy=dict(header=header('acl.vps.test'),ordered_candidates=[dict(profile_ref=r.profile_ref(source),gate=b'gate-one')],expanded_slots=[],on_none_applicable='REJECTED_AT_CREATE')
    value=dict(operation=operation,payload={},schema_lock=base['schema_lock'],schema_documents=base['schema_documents'])
    snapshot['entries']=[x for x in snapshot['entries'] if x['id'] not in {q['profile_id'] for q in profiles}]
    for profile in profiles:snapshot['entries'].append(dict(object_kind='VERIFICATION_PROFILE',**r.profile_ref(profile),state='REGISTERED'))
    snapshot['entries'].sort(key=lambda x:c.encode([x['object_kind'],x['id'],x['version']]));snapshot['header']['digest']=reg.registry_digest(snapshot)
    slot=dict(index=0,profile_ref=r.profile_ref(source),kind='PRIMARY',enabling_triggers=[])
    if operation=='policy':
        policy['expanded_slots']=r.expand(policy['ordered_candidates'],profiles,snapshot);value['payload']=dict(policy=policy,profiles=profiles,registry_snapshot=snapshot,edges=[edge])
    elif operation=='edge':value['payload']=dict(edge=edge,profiles=profiles,registry_snapshot=snapshot)
    elif operation=='manifest':value['payload']=dict(manifest=dict(header=header('acl.cm.test'),profile_schema_id='acl.schema.verification-profile@2',covers_schema_version=2,covers_profile_digests=sorted([x['profile_digest'] for x in profiles],key=c.encode),vector_sets=[b'vector-set'],file_digests=[dict(path='vectors/test.cbor',sha256=b'v'*32)]))
    elif operation=='profile-refs':value['payload']=dict(profile=source,registry_snapshot=snapshot)
    elif operation=='profile-lookup':value['payload']=dict(profile=source,registry_snapshot=snapshot,slot=slot)
    elif operation=='events':
        schema_ref=next(x['ref'] for x in base['schema_lock']['entries'] if x['alias']=='ExternalVersionedObjectRef')
        ids={'PHASE_I_RECORD':'acl.pir.'+'0'*26,'PHASE_F_CALL':b'F-call','CLUSTER_MAPPING':'acl.cmap.'+'0'*26,'ELIGIBILITY_SNAPSHOT':'test-snapshot','RECEIPT':b'r'*32,'OPAQUE_IMPORTED':'external-ID'}
        events=[]
        for index,(kind,tag) in enumerate(reg.SUBJECTS.items()):
            subject=dict(tag=tag,id=ids[tag])
            if kind=='OTHER':subject['schema_ref']=schema_ref
            events.append(dict(event_ref=str(index).encode(),event_kind=kind,parent_refs=[],subject_ref=subject))
        value['payload']=dict(events=events)
    elif operation=='applicability-test':
        scope=source['assumption_references'][0]['scope']
        declared=dict(task_class=scope['task_class'],rir_version=scope['rir_profile_range'][0],rpr_version=scope['rpr_version_range'][0],environment_class=scope['environment_class'],fault_domains=sorted(set(scope['fault_domains']),key=c.encode),geography=sorted(set(scope['geography']),key=c.encode))
        value['payload']=dict(profile=source,declared_scope=declared,evaluation_instant=1,n_max=5,intent_effects=[],slot=slot,degradation_authorized=False,source_failure_reasons=[])
    else:raise ValueError(operation)
    return seal(value),hashlib.sha256(c.encode(value['schema_lock'])).digest()


def seal(value):
    payload=value['payload'];operation=value['operation']
    if operation in ('policy','edge'):
        for key,kind in [('edge','EdgeR7'),('policy','PolicyR7')]:
            if key in payload:payload[key]['header']['digest']=r.asset_digest(payload[key],kind)
        for edge in payload.get('edges',[]):edge['header']['digest']=r.asset_digest(edge,'EdgeR7')
    if operation=='manifest':payload['manifest']['header']['digest']=r.asset_digest(payload['manifest'],'ManifestR7')
    return value


def rebind(value):
    payload=value['payload'];profiles=payload['profiles'];snapshot=payload['registry_snapshot']
    target=next(x for x in profiles if x['profile_id']=='acl.vp.stats.audit');target['profile_digest']=p.profile_digest(target)
    for source in profiles:
        if 'degradation' in source:source['degradation']['target']=r.profile_ref(target)
        source['profile_digest']=p.profile_digest(source)
    by_id={x['profile_id']:r.profile_ref(x) for x in profiles}
    for row in snapshot['entries']:
        if row['object_kind']=='VERIFICATION_PROFILE' and row['id'] in by_id:row.update(by_id[row['id']])
    snapshot['header']['digest']=reg.registry_digest(snapshot)
    edges=[payload['edge']] if 'edge' in payload else payload['edges']
    for edge in edges:
        for k in ('source','target'):
            if edge[k]['id'] in by_id:edge[k]=copy.deepcopy(by_id[edge[k]['id']])
    if 'policy' in payload:
        policy=payload['policy']
        for candidate in policy['ordered_candidates']:candidate['profile_ref']=copy.deepcopy(by_id[candidate['profile_ref']['id']])
        policy['expanded_slots']=r.expand(policy['ordered_candidates'],profiles,snapshot)
    return seal(value)


def evaluate(raw,pin):return r.inspect(raw,pin)


def vectors():
    rows=[]
    def add(name,value,valid=True,*,reseal=True,pin=None):
        if reseal:value=seal(value)
        pin=pin or hashlib.sha256(c.encode(value['schema_lock'])).digest();raw=c.encode(value)
        row=dict(id=name,mode='registration-assets',cbor_hex=raw.hex(),lock_pin=pin.hex(),valid=valid)
        if valid:row['expected']=evaluate(raw,pin)
        rows.append(row)
    for operation in ('policy','edge','manifest','profile-refs','profile-lookup','events','applicability-test'):
        base,pin=fixture(operation);add('valid-'+operation,copy.deepcopy(base))
        v=copy.deepcopy(base);v['unexpected']=1;add('unknown-root-'+operation,v,False)
        v=copy.deepcopy(base);v['payload']['unexpected']=1;add('unknown-payload-'+operation,v,False)
        add('wrong-lock-'+operation,copy.deepcopy(base),False,pin=b'x'*32)
        for field in base['payload']:
            v=copy.deepcopy(base);v['payload'].pop(field);add('missing-payload-'+operation+'-'+field,v,False,reseal=False)
    for operation,key,kind in [('policy','policy','PolicyR7'),('edge','edge','EdgeR7'),('manifest','manifest','ManifestR7')]:
        base,_=fixture(operation)
        for field in r.EXTRA[kind]['fields']:
            v=copy.deepcopy(base);v['payload'][key].pop(field);add('missing-object-'+operation+'-'+field,v,False,reseal=False)
        for field in ('schema_version','encoding_profile_id','id','version','digest'):
            v=copy.deepcopy(base);v['payload'][key]['header'].pop(field);add('missing-header-'+operation+'-'+field,v,False,reseal=False)
        for label,edit in [('flat',lambda v:v['payload'][key].update(id='duplicate')),('header-version',lambda v:v['payload'][key]['header'].update(schema_version=99)),('bad-id',lambda v:v['payload'][key]['header'].update(id='acl.unknown.test')),('unknown-field',lambda v:v['payload'][key].update(comment='unknown'))]:
            v=copy.deepcopy(base);edit(v);add(operation+'-'+label,v,False,reseal=False)
        v=copy.deepcopy(base);v['payload'][key]['header']['digest']=b'x'*32;add('bad-digest-'+operation,v,False,reseal=False)
        v=copy.deepcopy(base);v['payload'][key]['header'].update(id={'policy':'acl.vps.other','edge':'acl.we.other','manifest':'acl.cm.other'}[operation],version=[2,3,4]);add('identity-excluded-'+operation,v)
    base,_=fixture('policy')
    for label,edit in [
        ('duplicate-index',lambda q:q['expanded_slots'][1].update(index=0)),('index-gap',lambda q:q['expanded_slots'][1].update(index=2)),
        ('missing-degraded',lambda q:q['expanded_slots'].pop()),('reversed-slots',lambda q:q['expanded_slots'].reverse()),
        ('wrong-origin',lambda q:q['expanded_slots'][1].update(degraded_from=1)),('wrong-gate',lambda q:q['expanded_slots'][0].update(gate=b'different')),
        ('inherited-gate',lambda q:q['expanded_slots'][1].update(gate=b'gate-one')),('wrong-kind',lambda q:q['expanded_slots'][1].update(kind='PRIMARY')),
        ('wrong-trigger',lambda q:q['expanded_slots'][1].update(enabling_triggers=['CALIBRATION_OUT_OF_SCOPE'])),('wrong-none',lambda q:q.update(on_none_applicable='UNRESOLVED')),
    ]:
        v=copy.deepcopy(base);edit(v['payload']['policy']);add('policy-'+label,v,False)
    v=copy.deepcopy(base);q=v['payload']['policy'];q['ordered_candidates'].append(dict(profile_ref=copy.deepcopy(q['ordered_candidates'][0]['profile_ref']),gate=b'gate-two'));q['expanded_slots']=r.expand(q['ordered_candidates'],v['payload']['profiles'],v['payload']['registry_snapshot']);add('same-profile-different-gates',v)
    v=copy.deepcopy(base);q=v['payload']['policy'];q['ordered_candidates']=[];q['expanded_slots']=[];v['payload']['edges']=[];add('empty-policy-structural-only',v)
    for key in ('profiles','edges'):
        v=copy.deepcopy(base);v['payload'][key]=[];add('policy-missing-'+key,v,False)
    v=copy.deepcopy(base);v['payload']['profiles'].append(copy.deepcopy(v['payload']['profiles'][0]));add('duplicate-profile-asset',v,False)
    v=copy.deepcopy(base);v['payload']['policy']['ordered_candidates'][0]['profile_ref']['digest']=b'x'*32;add('unresolved-candidate',v,False)
    base,_=fixture('edge')
    for label,edit in [
        ('wrong-class',lambda q:q['edge'].update(edge_class='ATTESTED',evidence_ref=b'approval')),
        ('reversed',lambda q:q['edge'].update(source=q['edge']['target'],target=q['edge']['source'])),
        ('unknown-class',lambda q:q['edge'].update(edge_class='CLAIM_EQUIVALENT')),
        ('digest-only',lambda q:q['edge'].update(source=q['edge']['source']['digest'])),
    ]:
        v=copy.deepcopy(base);edit(v['payload']);add('edge-'+label,v,False)
    for key in ('task_type','contract_tuple_constraints','result_equivalence','excluded_claims'):
        v=copy.deepcopy(base);target=v['payload']['profiles'][1]
        if key=='task_type':target[key]='acl.tt.other'
        elif key=='contract_tuple_constraints':target[key]['allowed_effects']=[b'other-effect']
        elif key=='result_equivalence':target[key]['equivalence_id']='acl.eq.other@1'
        else:target[key]['exclusion_ids'].pop()
        rebind(v);add('edge-semantic-'+key,v,False)
    v=copy.deepcopy(base);v['payload']['profiles'][1]['verified_claim_spec']={};rebind(v);add('edge-target-claim',v,False)
    v=copy.deepcopy(base);v['payload']['profiles'][0]['verification_method']='DIRECT_VERIFIED';rebind(v);add('edge-source-method',v,False)
    v=copy.deepcopy(base);v['payload']['edge']['evidence_ref']=b'optional';add('edge-auto-with-opaque-evidence',v)
    base,_=fixture('manifest')
    for path in ('/absolute','C:/windows','C:relative','\\\\server\\file','a\\b',''):
        v=copy.deepcopy(base);v['payload']['manifest']['file_digests'][0]['path']=path;add('manifest-bad-path-'+repr(path),v,False)
    for path in ('../shared/vector.cbor','./vector.cbor','子目录/向量.cbor'):
        v=copy.deepcopy(base);v['payload']['manifest']['file_digests'][0]['path']=path;add('manifest-relative-data-'+path,v)
    for label,edit in [('duplicate-path',lambda q:q['file_digests'].append(copy.deepcopy(q['file_digests'][0]))),('wrong-sort',lambda q:q['file_digests'].insert(0,dict(path='z',sha256=b'z'*32))),('duplicate-digest',lambda q:q['covers_profile_digests'].append(q['covers_profile_digests'][0])),('repeated-header',lambda q:q.update(manifest_digest=q['header']['digest']))]:
        v=copy.deepcopy(base);edit(v['payload']['manifest']);add('manifest-'+label,v,False,reseal=label!='repeated-header')
    for method in p.METHODS:
        base,_=fixture('profile-refs',method);add('references-'+method,copy.deepcopy(base))
    base,_=fixture('profile-refs')
    for block,key in [('safety_parameters','support_capability_bound_ref'),('liveness_parameters','calibration_ref')]:
        for label,value_ in [('missing','ACL-ASM-9999'),('wrong-role',base['payload']['profile']['assumption_references'][0]['assumption_id'])]:
            v=copy.deepcopy(base);profile=v['payload']['profile'];profile[block][key]=value_;profile['profile_digest']=p.profile_digest(profile);add('reference-'+key+'-'+label,v,False)
    base,_=fixture('profile-lookup')
    for state in ('REGISTERED','ACTIVE','DEPRECATED','REVOKED'):
        v=copy.deepcopy(base);q=v['payload'];entry=next(x for x in q['registry_snapshot']['entries'] if x['id']==q['profile']['profile_id']);entry['state']=state;q['registry_snapshot']['header']['digest']=reg.registry_digest(q['registry_snapshot']);add('lookup-state-'+state,v)
    for field,value_ in [('id','acl.vp.other.audit'),('version',[3,0,0]),('digest',b'x'*32)]:
        v=copy.deepcopy(base);v['payload']['slot']['profile_ref'][field]=value_;add('lookup-slot-'+field,v,False)
        v=copy.deepcopy(base);q=v['payload'];entry=next(x for x in q['registry_snapshot']['entries'] if x['id']==q['profile']['profile_id']);entry[field]=value_;q['registry_snapshot']['entries'].sort(key=lambda x:c.encode([x['object_kind'],x['id'],x['version']]));q['registry_snapshot']['header']['digest']=reg.registry_digest(q['registry_snapshot']);add('lookup-snapshot-'+field,v,False)
    base,_=fixture('events')
    for n,event in enumerate(base['payload']['events']):
        for label,edit in [('wrong-tag',lambda e:e['subject_ref'].update(tag='WRONG')),('missing-subject',lambda e:e.pop('subject_ref')),('unknown-kind',lambda e:e.update(event_kind='UNKNOWN')),('unknown-subject-field',lambda e:e['subject_ref'].update(extra=1)),('wrong-id-type',lambda e:e['subject_ref'].update(id=True))]:
            v=copy.deepcopy(base);edit(v['payload']['events'][n]);add('event-'+event['event_kind']+'-'+label,v,False)
    base,_=fixture('applicability-test')
    for kind in ('PRIMARY','DEGRADED'):
        for auth in (False,True):
            for reasons in ([],['POPULATION_TOO_SMALL'],['POPULATION_TOO_SMALL','CONTRACT_MISMATCH'],['CONTRACT_MISMATCH']):
                v=copy.deepcopy(base);q=v['payload'];q['slot'].update(kind=kind,enabling_triggers=['POPULATION_TOO_SMALL'] if kind=='DEGRADED' else []);q['degradation_authorized']=auth;q['source_failure_reasons']=reasons
                if kind=='DEGRADED':q['slot']['degraded_from']=0
                add('degradation-'+str((kind,auth,reasons)),v)
    for n in (0,1,2,3,5,2**64-1):
        v=copy.deepcopy(base);v['payload']['n_max']=n;add('n-max-'+str(n),v)
    bound=next(x for x in base['payload']['profile']['assumption_references'] if x['assumption_id']==base['payload']['profile']['safety_parameters']['support_capability_bound_ref'])
    for instant in (bound['validity_window'][0]-1,bound['validity_window'][0],bound['validity_window'][1]-1,bound['validity_window'][1]):
        v=copy.deepcopy(base);v['payload']['evaluation_instant']=instant;add('window-'+str(instant),v)
    for field,value_ in [('task_class','acl.tt.other'),('environment_class',b'other'),('fault_domains',[b'outside']),('geography',[b'outside']),('rir_version',[99,0,0]),('rpr_version',[99,0,0])]:
        v=copy.deepcopy(base);v['payload']['declared_scope'][field]=value_;add('scope-outside-'+field,v)
    for field in ('fault_domains','geography'):
        v=copy.deepcopy(base);v['payload']['declared_scope'][field]=[];add('scope-empty-'+field,v,False)
        v=copy.deepcopy(base);v['payload']['declared_scope'].pop(field);add('scope-missing-'+field,v,False)
    for field in base['payload']['declared_scope']:
        v=copy.deepcopy(base);v['payload']['declared_scope'][field]=True;add('scope-wrong-type-'+field,v,False)
    for field,value_ in [('n_max',True),('n_max',-1),('evaluation_instant',True),('degradation_authorized',1),('intent_effects',[b'b',b'a']),('intent_effects',[b'a',b'a']),('source_failure_reasons',[b'wrong-wire'])]:
        v=copy.deepcopy(base);v['payload'][field]=value_;add('applicability-bad-'+field+'-'+str(value_),v,False)
    v=copy.deepcopy(base);v['payload']['intent_effects']=[b'network'];add('effect-not-covered',v)
    for operation in ('policy','edge','manifest','profile-refs','profile-lookup','events','applicability-test'):
        base,_=fixture(operation)
        for label,replacement in [('payload-array',[]),('payload-bool',True),('payload-text','wrong')]:
            v=copy.deepcopy(base);v['payload']=replacement;add('malformed-'+operation+'-'+label,v,False,reseal=False)
    base,_=fixture('policy');v=copy.deepcopy(base);v['payload']['edges']=[{}];add('malformed-edge-asset',v,False,reseal=False)
    base,_=fixture('manifest');v=copy.deepcopy(base);v['payload']['manifest']['file_digests'][0]['path']='bad\0path';add('manifest-nul-path',v,False)
    return rows


def run(binary,rows):
    requests=''.join(x['mode']+':'+x['lock_pin']+'\t'+x['cbor_hex']+'\n' for x in rows)
    result=subprocess.run([str(binary)],input=requests,text=True,capture_output=True,check=True,timeout=180);outputs=[json.loads(x) for x in result.stdout.splitlines()]
    if len(outputs)!=len(rows):raise ValueError('response count')
    for row,rust in zip(rows,outputs,strict=True):
        try:python=evaluate(bytes.fromhex(row['cbor_hex']),bytes.fromhex(row['lock_pin']))
        except c.CodecError:
            if row['valid'] or 'error' not in rust:raise ValueError('negative disagreement '+row['id']+' '+str(rust))
        else:
            if not row['valid'] or python!=rust or python!=row['expected']:raise ValueError('positive disagreement '+row['id']+' '+str(rust))
    return outputs


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--freeze-vectors',action='store_true');parser.add_argument('--report',type=Path);args=parser.parse_args()
    if args.freeze_vectors:
        data=vectors()
        with VECTOR.open('x') as f:json.dump(dict(scope='frozen registration components and explicit TEST applicability facts; no full SchemaValid/ReplayPhaseI',vectors=data),f,indent=2);f.write('\n')
    rows=json.loads(VECTOR.read_text())['vectors']
    with tempfile.TemporaryDirectory(prefix='aclt-selection-') as tmp:
        binary=Path(tmp)/'codec';subprocess.run([os.environ.get('RUSTC','rustc'),'--edition=2021','-D','warnings',str(ROOT/'tools/verification_profile/rust/main.rs'),'-o',str(binary)],check=True,timeout=120);outputs=run(binary,rows)
    names=set(json.loads((ROOT/'scripts/creation-source-files.json').read_text()))|{'scripts/check-selection-assets.py','tools/verification_profile/selection.py','tools/verification_profile/rust/selection_types.json','tools/verification_profile/rust/binding_types.json','tools/verification_profile/rust/runtime_types.json','tools/verification_profile/rust/creation_types.json','tests/verification_profile/test_selection.py','tests/verification_profile/codec/selection-assets-vectors.json'}
    names.update(x.relative_to(ROOT).as_posix() for x in (ROOT/'tools/verification_profile/rust').glob('*.rs'))
    report=dict(status='PASS',cases=len(rows),positive=sum(x['valid'] for x in rows),results_sha256=hashlib.sha256(json.dumps(outputs,sort_keys=True,separators=(',',':')).encode()).hexdigest(),hostname=socket.gethostname(),python=sys.version.split()[0],kernel=platform.release(),rustc=subprocess.check_output([os.environ.get('RUSTC','rustc'),'--version'],text=True).strip(),source_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in sorted(names)},full_schema_valid=False,full_phase_i_replay=False,source_authentication=False,production_admission=False)
    if args.report:args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
