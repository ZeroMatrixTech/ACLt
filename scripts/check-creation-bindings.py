#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Independent fixed audit I/F TEST wiring; not full ReplayPhaseI or CreateReceipt."""
import argparse,copy,hashlib,json,os,platform,runpy,socket,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.verification_profile import codec as c,creation as r,registration as reg
PREVIOUS=runpy.run_path(str(ROOT/'scripts/check-method-matrices.py'))
VECTOR=ROOT/'tests/verification_profile/codec/creation-bindings-vectors.json'


def pin(value):return hashlib.sha256(c.encode(value)).digest()


def fixture(phase='F'):
    base,_=PREVIOUS['audit_fixture']();lock=base['schema_lock'];docs=base['schema_documents'];aliases=set()
    def walk(x):
        if isinstance(x,dict):
            if 'import_' in x:aliases.add(x['import_'])
            for v in x.values():walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(r.EXTRA);existing={x['alias'] for x in lock['entries']}
    for alias in sorted(aliases-existing):
        identifier='acl.schema.test-'+alias.lower()+'@1';raw=c.encode(dict(alias=alias,id=identifier,version=[1,0,0],representation='OPAQUE_BSTR'))
        ref=dict(id=identifier,version=[1,0,0],digest=hashlib.sha256(raw).digest())
        lock['entries'].append(dict(alias=alias,ref=copy.deepcopy(ref)));docs.append(dict(ref=ref,content=raw))
    lock['entries'].sort(key=lambda x:c.encode(x['alias']))
    profile=base['envelope']['object'];ref=dict(id=profile['profile_id'],version=profile['profile_version'],digest=profile['profile_digest'])
    bundle=base['envelope']['bundle'];registry=bundle['registry_snapshot']
    registry['entries'].append(dict(object_kind='VERIFICATION_PROFILE',**ref,state='REGISTERED'))
    registry['entries'].sort(key=lambda x:c.encode([x['object_kind'],x['id'],x['version']]))
    registry['header']['digest']=reg.registry_digest(registry)
    bundle['context']['registry_snapshot_ref']=r.identity(registry,True)
    context=dict(header=dict(schema_version=1,encoding_profile_id=c.ENCODING,id='acl.cctx.'+'0'*26,digest=b'\0'*32),
        evaluation_instant=bundle['context']['evaluation_instant'],registry_snapshot_ref=copy.deepcopy(bundle['context']['registry_snapshot_ref']))
    context['header']['digest']=r.object_digest(context,'CreationContext')
    assurance=dict(id='acl.map.test',version=[1,0,0],digest=b'a'*32)
    intent=dict(schema_version=1,encoding_profile_id=c.ENCODING,network_id=b'LOCAL_TEST_ONLY',assurance_profile_ref=assurance,
        requester_ref=b'requester',contract_tuple=b'fixed-stats-int-test-contract',program_ref=b'stats-int-v1',input_refs=[b'input-B',b'input-A',b'input-B'],output_spec=b'stats-result',profile_ref=copy.deepcopy(ref),degradation_authorized=False)
    slot=dict(index=0,profile_ref=copy.deepcopy(ref),kind='PRIMARY',enabling_triggers=[])
    envelope=dict(phase='I',bundle=bundle,creation_context=context,profile=profile,assurance_profile=b'opaque-test-assurance',intent=intent,slot=slot)
    record=dict(header=dict(schema_version=1,encoding_profile_id=c.ENCODING,id='acl.pir.'+'0'*26,digest=b'\0'*32),creation_context_ref=r.identity(context),
        intent_digest=r.object_digest(intent,'ReceiptIntent'),slot_index=0,outcome='SELECTED',failure_reasons=[],produced_by_event=b'I-event')
    record['header']['digest']=r.object_digest(record,'PhaseIRecord')
    transcript=dict(input=envelope,output=record)
    contract=dict(name='fixed-audit-if-test-v1',profile_ref=copy.deepcopy(ref),admission_predicate=profile['admission_predicate'],contract_tuple=intent['contract_tuple'],
        network_id=intent['network_id'],assurance_profile_ref=copy.deepcopy(assurance),assurance_profile=envelope['assurance_profile'])
    value=dict(schema_lock=lock,schema_documents=docs,registry_objects=base['registry_objects'],test_contract=contract)
    if phase=='I':value['transcript']=transcript
    else:
        final=copy.deepcopy(envelope);final.pop('slot');final.update(phase='F',selected_slot=copy.deepcopy(slot),phase_i_transcript=transcript,phase_f_event_ref=b'F-event')
        frontier=final['bundle']['event_frontier_snapshot'];old=frontier['event_records'][0]['event_ref'];proof=frontier['log_binding']['event_inclusion_proofs'][0]
        frontier['event_records'] += [dict(event_ref=b'I-event',event_kind='PHASE_I_VALIDATION',parent_refs=[old],subject_ref=dict(tag='PHASE_I_RECORD',id=record['header']['id'])),
                                    dict(event_ref=b'F-event',event_kind='PHASE_F_VALIDATION',parent_refs=[b'I-event'],subject_ref=dict(tag='PHASE_F_CALL',id=b'F-call'))]
        frontier['event_records'].sort(key=lambda x:c.encode(x['event_ref']));frontier['frontier_event_ref']=b'F-event'
        frontier['log_binding']['event_inclusion_proofs']=[copy.deepcopy(proof) for _ in frontier['event_records']]
        value['envelope']=final
    return reseal(value),pin(lock),pin(contract)


def parts(value):
    t=value['transcript'] if 'transcript' in value else value['envelope']['phase_i_transcript'];return t,t['input'],t['output']


def reseal(value):
    t,e,record=parts(value)
    for env in ([e] if 'transcript' in value else [e,value['envelope']]):
        if 'bundle' in env:
            b=env['bundle'];f=b['event_frontier_snapshot'];f['header']['digest']=reg.frontier_digest(f)
            b['context']['event_frontier_ref']=r.identity(f)
        context=env.get('creation_context')
        if context and 'header' in context and set(context)==set(r.EXTRA['CreationContext']['fields']):
            if set(context['header'])=={'id','digest','schema_version','encoding_profile_id'}:context['header']['digest']=r.object_digest(context,'CreationContext')
    if set(record)==set(r.EXTRA['PhaseIRecord']['fields']) and set(record['header'])=={'id','digest','schema_version','encoding_profile_id'}:
        record['header']['digest']=r.object_digest(record,'PhaseIRecord')
    return value


def evaluate(mode,raw,lock_pin,contract_pin):return r.inspect(raw,lock_pin,contract_pin,phase='I' if mode=='phase-i6' else 'F')


def vectors():
    rows=[]
    def add(name,v,valid=True,*,phase='F',seal=True,pins=None):
        if seal:v=reseal(v)
        lp,cp=pins or (pin(v['schema_lock']),pin(v['test_contract']))
        mode='phase-i6' if phase=='I' else 'phase-f6';raw=c.encode(v)
        row=dict(id=name,mode=mode,cbor_hex=raw.hex(),lock_pin=lp.hex(),contract_pin=cp.hex(),valid=valid)
        if valid:row['expected']=evaluate(mode,raw,lp,cp)
        rows.append(row)
    for phase in ('I','F'):
        base,lp,cp=fixture(phase);add('valid-progressive-frontiers-'+phase,copy.deepcopy(base),phase=phase)
        for kind in ('CreationContext','ReceiptIntent','PhaseIRecord'):
            for field in r.EXTRA[kind]['fields']:
                v=copy.deepcopy(base);t,e,record=parts(v);target={'CreationContext':e['creation_context'],'ReceiptIntent':e['intent'],'PhaseIRecord':record}[kind]
                target.pop(field);add('missing-'+kind+'-'+field+'-'+phase,v,False,phase=phase,seal=False)
        for name,edit in [
            ('clock',lambda t,e,o:e['bundle']['context'].update(evaluation_instant=e['bundle']['context']['evaluation_instant']+1)),
            ('context-ref',lambda t,e,o:o['creation_context_ref'].update(digest=b'x'*32)),
            ('intent-digest',lambda t,e,o:o.update(intent_digest=b'x'*32)),
            ('slot-index',lambda t,e,o:o.update(slot_index=1)),
            ('forged-outcome',lambda t,e,o:o.update(outcome='REJECTED')),
            ('forged-reasons',lambda t,e,o:o['failure_reasons'].append(b'CONTRACT_MISMATCH')),
            ('intent-both-selectors',lambda t,e,o:e['intent'].update(selection_policy_ref=e['intent']['profile_ref'])),
            ('intent-neither-selector',lambda t,e,o:e['intent'].pop('profile_ref')),
            ('unknown-intent',lambda t,e,o:e['intent'].update(comment='ui')),
            ('unknown-context',lambda t,e,o:e['creation_context'].update(frontier_ref={})),
            ('runtime-version',lambda t,e,o:e['creation_context']['header'].update(version=[1,0,0])),
            ('record-version',lambda t,e,o:o['header'].update(version=[1,0,0])),
            ('gate',lambda t,e,o:e['slot'].update(gate=b'unsupported')),
            ('degraded',lambda t,e,o:e['slot'].update(kind='DEGRADED',degraded_from=0,enabling_triggers=['POPULATION_TOO_SMALL'])),
            ('authorized-degradation',lambda t,e,o:e['intent'].update(degradation_authorized=True)),
            ('network',lambda t,e,o:e['intent'].update(network_id=b'other')),
            ('assurance',lambda t,e,o:e.update(assurance_profile=b'other')),
            ('invalid-context-id',lambda t,e,o:e['creation_context']['header'].update(id='acl.cctx.invalid')),
            ('invalid-record-id',lambda t,e,o:o['header'].update(id='acl.pir.invalid')),
            ('intent-input-type',lambda t,e,o:e['intent'].update(input_refs=[True])),
            ('slot-bool',lambda t,e,o:o.update(slot_index=False)),
        ]:
            v=copy.deepcopy(base);edit(*parts(v));add(name+'-'+phase,v,False,phase=phase)
        for label,target in [('context','CreationContext'),('record','PhaseIRecord')]:
            v=copy.deepcopy(base);t,e,o=parts(v);item=e['creation_context'] if label=='context' else o;item['header']['digest']=b'x'*32
            add('bad-digest-'+label+'-'+phase,v,False,phase=phase,seal=False)
        for kind in ('input-order','input-duplicates','optional','empty-input'):
            v=copy.deepcopy(base);t,e,o=parts(v)
            if kind=='input-order':e['intent']['input_refs'].reverse();e['intent']['input_refs'][0]=b'C'
            if kind=='input-duplicates':e['intent']['input_refs']=[b'A',b'A']
            if kind=='empty-input':e['intent']['input_refs']=[]
            if kind=='optional':e['intent'].update(deadline=-1,execution_policy_ref=e['intent']['assurance_profile_ref'],funding_policy_ref=e['intent']['assurance_profile_ref'])
            o['intent_digest']=r.object_digest(e['intent'],'ReceiptIntent')
            if phase=='F':v['envelope']['intent']=copy.deepcopy(e['intent'])
            add(kind+'-'+phase,v,phase=phase)
        v=copy.deepcopy(base);v['test_contract']['contract_tuple']=b'changed';add('untrusted-contract-'+phase,v,False,phase=phase,pins=(lp,cp))
        v=copy.deepcopy(base);add('wrong-lock-pin-'+phase,v,False,phase=phase,pins=(b'x'*32,cp))
        if phase=='I':
            for state in ('DEPRECATED','REVOKED'):
                v=copy.deepcopy(base);t,e,o=parts(v);b=e['bundle'];entry=next(x for x in b['registry_snapshot']['entries'] if x['object_kind']=='VERIFICATION_PROFILE' and x['id']==e['profile']['profile_id']);entry['state']=state
                b['registry_snapshot']['header']['digest']=reg.registry_digest(b['registry_snapshot']);b['context']['registry_snapshot_ref']=r.identity(b['registry_snapshot'],True)
                e['creation_context']['registry_snapshot_ref']=copy.deepcopy(b['context']['registry_snapshot_ref']);e['creation_context']['header']['digest']=r.object_digest(e['creation_context'],'CreationContext');o['creation_context_ref']=r.identity(e['creation_context'])
                o.update(outcome='REJECTED',failure_reasons=[b'PROFILE_UNAVAILABLE']);add('rejected-'+state,v,phase=phase)
            v=copy.deepcopy(base);t,e,o=parts(v);e['intent']['contract_tuple']=b'wrong';o.update(outcome='REJECTED',failure_reasons=[b'CONTRACT_MISMATCH'],intent_digest=r.object_digest(e['intent'],'ReceiptIntent'));add('rejected-contract',v,phase=phase)
    base,lp,cp=fixture('F')
    for field in r.EXTRA['PhaseFEnvelope']['fields']:
        v=copy.deepcopy(base);v['envelope'].pop(field);add('missing-F-'+field,v,False,seal=False)
    for label,edit in [
        ('F-context-identity',lambda e:e['creation_context']['header'].update(id='acl.cctx.'+'1'*26)),
        ('F-intent-drift',lambda e:e['intent']['input_refs'].pop()),
        ('F-slot-drift',lambda e:e['selected_slot'].update(index=1)),
        ('F-missing-event',lambda e:e.update(phase_f_event_ref=b'absent')),
        ('F-equal-event',lambda e:e.update(phase_f_event_ref=b'I-event')),
        ('F-wrong-I-subject',lambda e:next(x for x in e['bundle']['event_frontier_snapshot']['event_records'] if x['event_ref']==b'I-event')['subject_ref'].update(id='acl.pir.'+'1'*26)),
        ('F-disconnected',lambda e:next(x for x in e['bundle']['event_frontier_snapshot']['event_records'] if x['event_ref']==b'F-event').update(parent_refs=[])),
        ('F-wrong-event-kind',lambda e:next(x for x in e['bundle']['event_frontier_snapshot']['event_records'] if x['event_ref']==b'F-event').update(event_kind='PHASE_I_VALIDATION')),
        ('F-unknown-field',lambda e:e.update(receipt_id=b'not-created')),
    ]:
        v=copy.deepcopy(base);edit(v['envelope']);add(label,v,False)
    # A different I frontier is allowed; no invented frontier equality.
    v=copy.deepcopy(base);e=v['envelope'];f=e['bundle']['event_frontier_snapshot'];i=next(x for x in f['event_records'] if x['event_ref']==b'I-event');z=next(x for x in f['event_records'] if x['event_ref']==b'F-event')
    middle=copy.deepcopy(z);middle.update(event_ref=b'M-event',parent_refs=[b'I-event']);f['event_records'].append(middle);f['event_records'].sort(key=lambda x:c.encode(x['event_ref']));z['parent_refs']=[b'M-event'];f['log_binding']['event_inclusion_proofs'].append(copy.deepcopy(f['log_binding']['event_inclusion_proofs'][0]));add('transitive-precedence',v)
    return rows


def run(binary,rows):
    requests=''.join(x['mode']+':'+x['lock_pin']+':'+x['contract_pin']+'\t'+x['cbor_hex']+'\n' for x in rows)
    result=subprocess.run([str(binary)],input=requests,text=True,capture_output=True,check=True,timeout=180);outputs=[json.loads(x) for x in result.stdout.splitlines()]
    if len(outputs)!=len(rows):raise ValueError('response count')
    for row,rust in zip(rows,outputs,strict=True):
        try:python=evaluate(row['mode'],bytes.fromhex(row['cbor_hex']),bytes.fromhex(row['lock_pin']),bytes.fromhex(row['contract_pin']))
        except (c.CodecError,KeyError,TypeError):
            if row['valid'] or 'error' not in rust:raise ValueError('negative disagreement: '+row['id']+' '+str(rust))
        else:
            if not row['valid'] or python!=rust or python!=row['expected']:raise ValueError('positive disagreement: '+row['id']+' '+str(rust))
    return outputs


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--freeze-vectors',action='store_true');parser.add_argument('--report',type=Path);args=parser.parse_args()
    if args.freeze_vectors:
        with VECTOR.open('x') as f:json.dump(dict(scope='I/F components and fixed audit TEST replay; opaque imports; not full ReplayPhaseI',vectors=vectors()),f,indent=2);f.write('\n')
    rows=json.loads(VECTOR.read_text())['vectors']
    with tempfile.TemporaryDirectory(prefix='aclt-creation-') as path:
        binary=Path(path)/'codec';subprocess.run([os.environ.get('RUSTC','rustc'),'--edition=2021','-D','warnings',str(ROOT/'tools/verification_profile/rust/main.rs'),'-o',str(binary)],check=True,timeout=120);outputs=run(binary,rows)
    names={'scripts/check-creation-bindings.py','tools/verification_profile/creation.py','tools/verification_profile/rust/creation_types.json','tools/verification_profile/rust/binding_types.json','tests/verification_profile/test_creation.py','tests/verification_profile/codec/creation-bindings-vectors.json'}
    names.update(json.loads((ROOT/'scripts/creation-source-files.json').read_text()))
    names.update(x.relative_to(ROOT).as_posix() for x in (ROOT/'tools/verification_profile/rust').glob('*.rs'))
    report=dict(status='PASS',cases=len(rows),positive=sum(x['valid'] for x in rows),results_sha256=hashlib.sha256(json.dumps(outputs,sort_keys=True,separators=(',',':')).encode()).hexdigest(),hostname=socket.gethostname(),python=sys.version.split()[0],kernel=platform.release(),rustc=subprocess.check_output([os.environ.get('RUSTC','rustc'),'--version'],text=True).strip(),source_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in sorted(names)},full_schema_valid=False,full_phase_i_replay=False,production_admission=False,source_authentication=False,receipt_created=False)
    if args.report:args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
