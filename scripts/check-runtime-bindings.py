#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Independent Phase B guards over explicit TEST snapshot/randomness imports."""
from functools import lru_cache
import argparse,copy,hashlib,json,os,platform,runpy,socket,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.verification_profile import codec as c,profile as p,registration as reg,runtime_bindings as r,commitments as b
PREVIOUS=runpy.run_path(str(ROOT/'scripts/check-commitment-bindings.py'))
VECTOR_PIN=ROOT/'tests/verification_profile/codec/runtime-bindings-vectors.pin.json'

def pin(v):return hashlib.sha256(c.encode(v)).digest()

def fixture(tag='SNAPSHOT_FREEZE',method='REEXEC_BOUNDED',stages=None):
    base,lp=PREVIOUS['fixture']('claim-guard',method);q=base['payload'];profile=q['profile'];assurance=q.get('assurance_profile')
    alias='SamplingUnitID';ident='acl.schema.r9-sampling-unit-id@1';raw=c.encode(dict(alias=alias,id=ident,version=[1,0,0],representation='OPAQUE_BSTR'));ref=dict(id=ident,version=[1,0,0],digest=hashlib.sha256(raw).digest());base['schema_lock']['entries'].append(dict(alias=alias,ref=ref));base['schema_lock']['entries'].sort(key=lambda x:c.encode(x['alias']));base['schema_documents'].append(dict(ref=copy.deepcopy(ref),content=raw));lp=pin(base['schema_lock'])
    if assurance is None:assurance=PREVIOUS['fixture']('assurance-digest',method)[0]['payload']['object']
    binding=dict(receipt_id=b'r'*32,profile_ref=b.selection.profile_ref(profile),network_id=assurance['network_id'],assurance_profile_ref=b.identity(assurance))
    bounded=method=='REEXEC_BOUNDED';reference=copy.deepcopy(binding['profile_ref']);mapping=dict(id='acl.cmap.'+'0'*26,digest=b'm'*32)
    stat=r.frozen(profile) if bounded else None
    pairs={'LEASE_ACTIVATION_PRE_FREEZE':('PRE_FREEZE','PRE_FREEZE'),'LEASE_ACTIVATION_POST_FREEZE':('FROZEN_PRE_DRAW','FROZEN_PRE_DRAW'),'CLUSTER_MAPPING_FIX':('PRE_FREEZE','PRE_FREEZE'),'SNAPSHOT_FREEZE':('PRE_FREEZE','FROZEN_PRE_DRAW'),'ROUND_TRANSITION_PRE_FREEZE':('PRE_FREEZE','PRE_FREEZE'),'ROUND_TRANSITION_POST_FREEZE':('FROZEN_PRE_DRAW','RUNNING'),'ROUND_TRANSITION_NO_SNAPSHOT':('PRE_FREEZE','RUNNING')}
    a,z=stages or pairs[tag]
    def state(stage,old):
        out=dict(round_stage=stage,bound_profile_ref=copy.deepcopy(reference))
        if bounded:
            out['frozen_parameters']=copy.deepcopy(stat)
            if not (tag=='CLUSTER_MAPPING_FIX' and old):out['cluster_mapping_ref']=copy.deepcopy(mapping)
            if stage!='PRE_FREEZE':out['population_size']=stat['G']
        return out
    transition=dict(prior_round_state=state(a,True),proposed_round_state=state(z,False));payload=dict(tag=tag,transition=transition)
    source=profile['assumption_references'][0]['scope'];scope=dict(task_class=source['task_class'],rir_version=source['rir_profile_range'][0],rpr_version=source['rpr_version_range'][0],environment_class=source['environment_class'],fault_domains=copy.deepcopy(source['fault_domains']),geography=copy.deepcopy(source['geography']))
    if 'actual_bound_scope' in r.SHAPES[tag]:payload['actual_bound_scope']=copy.deepcopy(scope)
    contract=dict(name='r9-runtime-imports@1',snapshot_schema_ref=b'snapshot-schema',population_definition_ref=b'population',randomness_rule_ref=b'commitment',scheme_id='r9-pinned-commitment-test',allowed_randomness_parameters=[dict(domain=b'test-domain',bits=256)])
    G=stat['G'] if bounded else 5
    snapshot=dict(id='r9-test-snapshot',receipt_id=b'r'*32,population_definition_ref=b'population',snapshot_schema_ref=b'snapshot-schema',randomness_commitment=dict(scheme_id=contract['scheme_id'],parameters=copy.deepcopy(contract['allowed_randomness_parameters'][0])),sampling_units=[dict(id=('unit-'+str(n)).encode(),scope=copy.deepcopy(scope)) for n in range(G)],cluster_mapping_ref=copy.deepcopy(mapping))
    if 'eligibility_snapshot' in r.SHAPES[tag]:payload['eligibility_snapshot']=PREVIOUS['wrap'](base,snapshot)
    if tag=='SNAPSHOT_FREEZE':transition['snapshot_freeze_record']=dict(candidate_units_pre_scope_filter=sorted([x['id'] for x in snapshot['sampling_units']]+[b'excluded'],key=c.encode),excluded_by_scope=[b'excluded'],frozen_units=sorted([x['id'] for x in snapshot['sampling_units']],key=c.encode),cluster_mapping_ref=copy.deepcopy(mapping),cluster_mapping_fixed_event=b'fix',freeze_event=b'freeze')
    if tag=='CLUSTER_MAPPING_FIX':payload['cluster_mapping_fixed_event']=b'fix'
    if tag=='ROUND_TRANSITION_NO_SNAPSHOT' and a!=z:payload['transition_event_ref']=b'start' if z=='RUNNING' else b'terminal'
    bundle=copy.deepcopy(PREVIOUS['R6']['fixture']()[0]['envelope']['bundle']);bundle['registry_snapshot']=copy.deepcopy(q['registry_snapshot']);f=bundle['event_frontier_snapshot'];events=[]
    def event(reference,kind,subject,parents=()):return dict(event_ref=reference,event_kind=kind,parent_refs=list(parents),subject_ref=subject)
    root=copy.deepcopy(f['event_records'][0]);root['event_ref']=b'root';root['parent_refs']=[];events.append(root)
    events += [event(b'fix','CLUSTER_MAPPING_FIXED',dict(tag='CLUSTER_MAPPING',id=mapping['id']),[b'root']),event(b'freeze','SNAPSHOT_FROZEN',dict(tag='ELIGIBILITY_SNAPSHOT',id=snapshot['id']),[b'fix'])]
    frontier=b'freeze'
    if tag=='ROUND_TRANSITION_NO_SNAPSHOT':
        events=[root];parent=b'root'
        if a=='RUNNING' or z=='RUNNING':events.append(event(b'start','VERIFICATION_STARTED',dict(tag='RECEIPT',id=b'r'*32),[parent]));parent=b'start'
        if z=='TERMINAL':events.append(event(b'terminal','VERIFICATION_TERMINAL_COMMITTED',dict(tag='RECEIPT',id=b'r'*32),[parent]));parent=b'terminal'
        frontier=parent
    f['event_records']=events;f['frontier_event_ref']=frontier
    value=dict(envelope=dict(phase='B',bundle=bundle,profile=profile,assurance_profile=assurance,receipt_binding=binding,bound_profile_ref=reference,payload=payload),schema_lock=base['schema_lock'],schema_documents=base['schema_documents'],runtime_contract=contract)
    seal(value)
    return value,lp,pin(contract)

def seal(v):
    e=v['envelope'];bundle=e.get('bundle');
    if bundle is None:return v
    f=bundle['event_frontier_snapshot'];f['event_records'].sort(key=lambda x:c.encode(x['event_ref']))
    if f['event_records']:
        proof=copy.deepcopy(f['log_binding']['event_inclusion_proofs'][0]);f['log_binding']['event_inclusion_proofs']=[copy.deepcopy(proof) for _ in f['event_records']]
    f['header']['digest']=reg.frontier_digest(f);bundle['context']['event_frontier_ref']={k:f['header'][k] for k in ('id','digest')};bundle['context']['registry_snapshot_ref']=b.identity(bundle['registry_snapshot'])
    return v

def snapshot_edit(v,edit):
    external=v['envelope']['payload']['eligibility_snapshot'];raw=c.decode(external['canonical_bytes']);edit(raw);v['envelope']['payload']['eligibility_snapshot']=PREVIOUS['wrap'](v,raw)

def vectors():
    rows=[]
    def add(name,v,accept=True,error=False,pins=None):
        seal(v);lp,cp=pins or (pin(v['schema_lock']),pin(v['runtime_contract']));raw=c.encode(v);row=dict(id=name,cbor_hex=raw.hex(),lock_pin=lp.hex(),contract_pin=cp.hex(),accepted=accept,error=error)
        try:actual=r.inspect(raw,lp,cp)
        except c.CodecError:
            if not error:raise ValueError('unexpected error '+name)
        else:
            if error or actual['accepted']!=accept:raise ValueError('wrong fixture '+name+' '+str(actual))
            row['expected']=actual
        rows.append(row)
    for tag in r.SHAPES:
        method='REEXEC_AUDIT_ONLY' if tag=='ROUND_TRANSITION_NO_SNAPSHOT' else 'REEXEC_BOUNDED';base,lp,cp=fixture(tag,method);add('valid-'+tag,copy.deepcopy(base))
        for field in base['envelope']:v=copy.deepcopy(base);v['envelope'].pop(field);add('missing-envelope-'+tag+'-'+field,v,False,True)
        # Missing bundle is encoded separately because sealing cannot repair it.
        for field in base['envelope']['payload']:
            if field=='tag':continue
            v=copy.deepcopy(base);v['envelope']['payload'].pop(field);add('missing-payload-'+tag+'-'+field,v,False,field!='transition_event_ref')
        for where in ('root','envelope','payload','transition','prior','after'):
            v=copy.deepcopy(base);e=v['envelope'];tr=e['payload']['transition'];target={'root':v,'envelope':e,'payload':e['payload'],'transition':tr,'prior':tr['prior_round_state'],'after':tr['proposed_round_state']}[where];target['unexpected']=1;add('unknown-'+tag+'-'+where,v,False,True)
        add('lock-pin-'+tag,copy.deepcopy(base),False,True,pins=(b'x'*32,cp));add('contract-pin-'+tag,copy.deepcopy(base),False,True,pins=(lp,b'x'*32))
        for path in ('outer','receipt','prior','after'):
            v=copy.deepcopy(base);e=v['envelope'];target={'outer':e['bound_profile_ref'],'receipt':e['receipt_binding']['profile_ref'],'prior':e['payload']['transition']['prior_round_state']['bound_profile_ref'],'after':e['payload']['transition']['proposed_round_state']['bound_profile_ref']}[path];target['digest']=b'x'*32;add('profile-substitution-'+tag+'-'+path,v,False)
        for field in ('network_id','assurance_profile_ref'):
            v=copy.deepcopy(base);binding=v['envelope']['receipt_binding'];binding[field]=b'other' if field=='network_id' else dict(binding[field],digest=b'x'*32);add('receipt-assurance-'+tag+'-'+field,v,False)
    # All stage pairs and all bounded payloads, including terminal activation guards.
    for tag in tuple(r.SHAPES)[:-1]:
        for a in r.STAGES:
            for z in r.STAGES:
                v,_,_=fixture(tag,stages=(a,z));valid=(tag in ('LEASE_ACTIVATION_PRE_FREEZE','CLUSTER_MAPPING_FIX','ROUND_TRANSITION_PRE_FREEZE') and a==z=='PRE_FREEZE') or (tag=='LEASE_ACTIVATION_POST_FREEZE' and a==z and a in r.STAGES[1:]) or (tag=='SNAPSHOT_FREEZE' and (a,z)==('PRE_FREEZE','FROZEN_PRE_DRAW')) or (tag=='ROUND_TRANSITION_POST_FREEZE' and (a,z) in (('FROZEN_PRE_DRAW','RUNNING'),('RUNNING','RUNNING'),('RUNNING','TERMINAL')))
                add('stage-'+tag+'-'+a+'-'+z,v,valid)
    for method in p.METHODS:
        for stages in (('PRE_FREEZE','RUNNING'),('RUNNING','RUNNING'),('RUNNING','TERMINAL'),('PRE_FREEZE','TERMINAL')):
            v,_,_=fixture('ROUND_TRANSITION_NO_SNAPSHOT',method,stages);add('no-snapshot-'+method+'-'+'-'.join(stages),v,method!='REEXEC_BOUNDED')
        v,_,_=fixture('LEASE_ACTIVATION_PRE_FREEZE',method);add('lease-pre-'+method,v)
    base,_,_=fixture()
    for field in ('task_class','rir_version','rpr_version','environment_class','fault_domains','geography'):
        v=copy.deepcopy(base);v['envelope']['payload']['actual_bound_scope'].pop(field);add('actual-missing-'+field,v,False,True)
        v=copy.deepcopy(base);scope=v['envelope']['payload']['actual_bound_scope'];scope[field]=[b'outside'] if field in ('fault_domains','geography') else [0,0,0] if field.endswith('version') else 'acl.tt.other' if field=='task_class' else b'other';add('actual-outside-'+field,v,False)
    for field in ('fault_domains','geography'):
        v=copy.deepcopy(base);v['envelope']['payload']['actual_bound_scope'][field]=[];add('actual-empty-'+field,v,False,True)
    for n,edit in [('duplicate-id',lambda s:s['sampling_units'].append(copy.deepcopy(s['sampling_units'][0]))),('count',lambda s:s['sampling_units'].pop()),('receipt',lambda s:s.update(receipt_id=b'x'*32)),('mapping',lambda s:s['cluster_mapping_ref'].update(digest=b'x'*32)),('population',lambda s:s.update(population_definition_ref=b'other')),('schema',lambda s:s.update(snapshot_schema_ref=b'other')),('scheme',lambda s:s['randomness_commitment'].update(scheme_id='other')),('random-parameters',lambda s:s['randomness_commitment'].update(parameters=dict(bits=128))),('unit-scope',lambda s:s['sampling_units'][0]['scope'].update(geography=[b'outside']))]:
        v=copy.deepcopy(base);snapshot_edit(v,edit);add('snapshot-'+n,v,False)
    for key in ('G','B','Q','delta_min','mixture_weights'):
        for side in ('prior_round_state','proposed_round_state'):
            v=copy.deepcopy(base);stats=v['envelope']['payload']['transition'][side]['frozen_parameters'];stats[key]=stats[key]+1 if type(stats[key]) is int else [1,4] if key=='delta_min' else [dict(m=2,weight=[1,1])];add('reparameterize-'+side+'-'+key,v,False)
    for key in ('candidate_units_pre_scope_filter','excluded_by_scope','frozen_units'):
        v=copy.deepcopy(base);row=v['envelope']['payload']['transition']['snapshot_freeze_record'];row[key]=[];add('freeze-filter-'+key,v,False)
        v=copy.deepcopy(base);row=v['envelope']['payload']['transition']['snapshot_freeze_record'];row[key].append(row[key][0]);add('freeze-duplicate-'+key,v,False,True)
    for where in ('prior_round_state','proposed_round_state','snapshot_freeze_record'):
        v=copy.deepcopy(base);v['envelope']['payload']['transition'][where]['cluster_mapping_ref']['version']=[1,0,0];add('mapping-forbidden-version-'+where,v,False,True)
    v=copy.deepcopy(base);snapshot_edit(v,lambda s:s['cluster_mapping_ref'].update(version=[1,0,0]));add('snapshot-mapping-forbidden-version',v,False,True)
    for where in ('prior_round_state','proposed_round_state','snapshot_freeze_record'):
        v=copy.deepcopy(base);v['envelope']['payload']['transition'][where]['cluster_mapping_ref']['digest']=b'x'*32;add('mapping-chain-'+where,v,False)
    for side in ('cluster_mapping_fixed_event','freeze_event'):
        for case in ('missing','kind','subject','not-visible'):
            v=copy.deepcopy(base);f=v['envelope']['bundle']['event_frontier_snapshot'];tr=v['envelope']['payload']['transition'];ref=tr['snapshot_freeze_record'][side];row=next(x for x in f['event_records'] if x['event_ref']==ref)
            if case=='missing':tr['snapshot_freeze_record'][side]=b'unknown'
            elif case=='kind':row['event_kind']='EXECUTION_EXHAUSTED';row['subject_ref']=dict(tag='RECEIPT',id=b'r'*32)
            elif case=='subject':row['subject_ref']['id']='acl.cmap.'+'1'*26 if side=='cluster_mapping_fixed_event' else 'foreign-snapshot'
            else:f['frontier_event_ref']=b'root'
            add('freeze-event-'+side+'-'+case,v,False)
    v=copy.deepcopy(base);f=v['envelope']['bundle']['event_frontier_snapshot'];next(x for x in f['event_records'] if x['event_ref']==b'freeze')['parent_refs']=[b'root'];f['frontier_event_ref']=b'freeze';add('incomparable-freeze-events',v,False)
    v=copy.deepcopy(base);next(x for x in v['envelope']['bundle']['event_frontier_snapshot']['event_records'] if x['event_ref']==b'fix')['parent_refs']=[b'freeze'];add('cyclic-frontier',v,False,True)
    for stage in r.STAGES:
        tag='LEASE_ACTIVATION_PRE_FREEZE' if stage=='PRE_FREEZE' else 'LEASE_ACTIVATION_POST_FREEZE';v,_,_=fixture(tag,stages=(stage,stage));v['envelope']['bound_profile_ref']['digest']=b'x'*32;add('failure-policy-'+stage,v,False)
    for method in p.METHODS[:-1]+('REEXEC_AUDIT_ONLY',):
        if method=='REEXEC_BOUNDED':continue
        for tag in tuple(r.SHAPES)[:-1]:
            if tag=='LEASE_ACTIVATION_PRE_FREEZE':continue
            v,_,_=fixture(tag,method);add('forbidden-method-tag-'+method+'-'+tag,v,False)
    v,_,_=fixture('ROUND_TRANSITION_NO_SNAPSHOT','REEXEC_AUDIT_ONLY');v['envelope']['payload']['transition']['proposed_round_state']['frozen_parameters']=dict(G=5,B=1,Q=3,delta_min=[1,5],mixture_weights=[dict(m=3,weight=[1,1])]);add('audit-injected-statistics',v,False)
    for case in ('second-start','terminal-already','wrong-start-ref','wrong-subject','missing-transition','extraneous-transition'):
        stages=('RUNNING','RUNNING') if case=='extraneous-transition' else None;v,_,_=fixture('ROUND_TRANSITION_NO_SNAPSHOT','REEXEC_AUDIT_ONLY',stages);e=v['envelope'];f=e['bundle']['event_frontier_snapshot']
        if case in ('second-start','terminal-already'):
            f['event_records'].append(dict(event_ref=b'extra',event_kind='VERIFICATION_STARTED' if case=='second-start' else 'VERIFICATION_TERMINAL_COMMITTED',parent_refs=[b'start'],subject_ref=dict(tag='RECEIPT',id=b'r'*32)));f['frontier_event_ref']=b'extra'
        elif case=='wrong-start-ref':e['payload']['transition_event_ref']=b'freeze'
        elif case=='wrong-subject':next(x for x in f['event_records'] if x['event_ref']==b'start')['subject_ref']['id']=b'x'*32
        elif case=='missing-transition':e['payload'].pop('transition_event_ref')
        else:e['payload']['transition_event_ref']=b'start'
        add('no-snapshot-source-'+case,v,False)
    return rows

def run(binary,rows):
    request=''.join('runtime-bindings:'+x['lock_pin']+':'+x['contract_pin']+'\t'+x['cbor_hex']+'\n' for x in rows);process=subprocess.run([str(binary)],input=request,text=True,capture_output=True,check=True,timeout=180);answers=[json.loads(x) for x in process.stdout.splitlines()]
    if len(answers)!=len(rows):raise ValueError('response count')
    for row,answer in zip(rows,answers,strict=True):
        try:actual=r.inspect(bytes.fromhex(row['cbor_hex']),bytes.fromhex(row['lock_pin']),bytes.fromhex(row['contract_pin']))
        except c.CodecError:
            if not row['error'] or 'error' not in answer:raise ValueError('error disagreement '+row['id']+' '+str(answer))
        else:
            if row['error'] or actual!=answer or actual!=row['expected']:raise ValueError('result disagreement '+row['id']+'\n'+str(actual)+'\n'+str(answer))
    return answers

def source_names():
    names=set(json.loads((ROOT/'scripts/creation-source-files.json').read_text()))|{'scripts/check-runtime-bindings.py','scripts/check-commitment-bindings.py','scripts/check-creation-bindings.py','scripts/check-selection-assets.py','tests/verification_profile/test_runtime_bindings.py','tests/verification_profile/codec/runtime-bindings-vectors.pin.json','schemas/verification-profile/runtime-imports-candidate-r9.json','docs/testing/PROFILE-RUNTIME-R9-20261108.scope.json'}
    for directory,pattern in [('tools/verification_profile','*.py'),('tools/verification_profile/rust','*.rs'),('tools/verification_profile/rust','*.json')]:names.update(x.relative_to(ROOT).as_posix() for x in (ROOT/directory).glob(pattern))
    return sorted(names)

@lru_cache(maxsize=1)
def pinned_vectors():
    rows = vectors()
    data = dict(
        scope='explicit runtime guards with pinned TEST snapshot/randomness imports; not formal Phase B conformance',
        vectors=rows,
    )
    raw = (json.dumps(data, indent=2) + '\n').encode('utf-8')
    expected = json.loads(VECTOR_PIN.read_text())
    actual = dict(schema='aclt.r9-vector-pin@1', cases=len(rows), bytes=len(raw),
                  sha256=hashlib.sha256(raw).hexdigest())
    c.need(actual == expected, 'R9 generated vector bytes differ from historical pin')
    return rows, raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-vectors', type=Path, metavar='OUTPUT',
                        help='export exact historical vector bytes without running the compilers')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.freeze_vectors and args.report:
        parser.error('--freeze-vectors and --report are mutually exclusive')
    rows, raw = pinned_vectors()
    if args.freeze_vectors:
        with args.freeze_vectors.open('xb') as stream:
            stream.write(raw)
        return
    with tempfile.TemporaryDirectory(prefix='aclt-runtime-bindings-') as tmp:
        binary=Path(tmp)/'codec';subprocess.run([os.environ.get('RUSTC','rustc'),'--edition=2021','-D','warnings',str(ROOT/'tools/verification_profile/rust/main.rs'),'-o',str(binary)],check=True,timeout=120);answers=run(binary,rows)
    report=dict(status='PASS',cases=len(rows),positive=sum(x['accepted'] for x in rows),negative=sum(not x['accepted'] for x in rows),structural_rejects=sum(x['error'] for x in rows),results_sha256=hashlib.sha256(json.dumps(answers,sort_keys=True,separators=(',',':')).encode()).hexdigest(),hostname=socket.gethostname(),python=sys.version.split()[0],kernel=platform.release(),rustc=subprocess.check_output([os.environ.get('RUSTC','rustc'),'--version'],text=True).strip(),source_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in source_names()},full_schema_valid=False,formal_phase_b_conformance=False,source_authentication=False,production_admission=False,state_committed=False)
    if args.report:
        with args.report.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
