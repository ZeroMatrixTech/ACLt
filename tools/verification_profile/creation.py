# SPDX-License-Identifier: Apache-2.0
"""I/F binding components and an explicitly pinned, fixed audit TEST replay.

The test admission predicate compares an opaque ContractTuple exactly. It is NOT
ReplayPhaseI for arbitrary Profiles, source authentication or CreateReceipt.
"""
import hashlib,json
from pathlib import Path
from tools.verification_profile import codec as c,registration as r,references,method_rules
EXTRA=json.loads((Path(__file__).parent/'rust/creation_types.json').read_text())
if set(EXTRA)&set(r.TYPES):raise c.CodecError('duplicate creation type')
TYPES=r.TYPES|EXTRA


def typed(value,kind,imports):
    r.typed(value,kind,imports,TYPES)


def identity(value,versioned=False):
    h=value['header'];return {key:h[key] for key in (('id','version','digest') if versioned else ('id','digest'))}


def content_map(value,kind):
    """Frozen projections. Runtime IDs remain in the hash; digest never does."""
    c.need(kind in ('CreationContext','PhaseIRecord','ReceiptIntent'),'creation digest kind')
    schema=EXTRA[kind]
    c.fields(value,schema['fields'],schema['optional'])
    if kind=='ReceiptIntent':
        c.need(('profile_ref' in value)!=('selection_policy_ref' in value),'RI-1: exactly one selection reference')
        return dict(value)
    header=value['header'];c.fields(header,('schema_version','encoding_profile_id','id','digest'))
    return {key:header[key] for key in ('schema_version','encoding_profile_id','id')}|{k:v for k,v in value.items() if k!='header'}


def object_digest(value,kind):
    tag={'CreationContext':'CreationContext','PhaseIRecord':'PhaseIValidationRecord','ReceiptIntent':'ReceiptIntent'}[kind]
    return c.domain_hash('ACLt/P0-1/'+tag+'/1',c.encode(content_map(value,kind)))


def check_object(value,kind,imports):
    typed(value,kind,imports)
    content=content_map(value,kind)
    c.need(content['schema_version']==1,'creation object schema version')
    digest=object_digest(value,kind)
    if kind!='ReceiptIntent':
        owner='SV-97' if kind=='CreationContext' else 'SV-103'
        c.need(c.digest_consistency(value['header']['digest']==digest),owner+': digest mismatch')
    return digest


def check_context(context,bundle,imports):
    digest=check_object(context,'CreationContext',imports)
    for key in ('evaluation_instant','registry_snapshot_ref'):
        c.need((c.reference_identity(context[key])==c.reference_identity(bundle['context'][key]) if key=='registry_snapshot_ref' else context[key]==bundle['context'][key]),'SV-101: CC-1 '+key)
    return digest


def check_record(record,envelope,imports):
    check_object(record,'PhaseIRecord',imports)
    c.need(c.reference_identity(record['creation_context_ref'])==c.reference_identity(identity(envelope['creation_context'])),'SV-96: CC-2I creation identity')
    c.need(c.digest_consistency(record['intent_digest']==check_object(envelope['intent'],'ReceiptIntent',imports)),'SV-102: CC-4 intent digest')
    c.need(record['slot_index']==envelope['slot']['index'],'SV-102: CC-4 slot index')


def replay_fixed_audit_test(envelope,contract):
    """Finite test projection, derived from explicit inputs; never claimed as SV-102 closure."""
    profile=envelope['profile'];slot=envelope['slot'];intent=envelope['intent']
    ref=dict(id=profile['profile_id'],version=profile['profile_version'],digest=profile['profile_digest'])
    c.need(ref==contract['profile_ref'] and profile['admission_predicate']==contract['admission_predicate'],
           'test contract Profile/predicate binding')
    c.need(slot==dict(index=0,profile_ref=ref,kind='PRIMARY',enabling_triggers=[]),
           'fixed test replay supports only implicit primary slot without gate')
    c.need(intent.get('profile_ref')==ref and not intent['degradation_authorized'],'fixed test direct Profile selection only')
    c.need('degradation' not in profile,'fixed test has no degradation')
    c.need(all(row['role']=='INFORMATIONAL' for row in profile['assumption_references']),
           'test replay does not implement safety/liveness scope evaluation')
    c.need(envelope['assurance_profile']==contract['assurance_profile'] and
           intent['network_id']==contract['network_id'] and intent['assurance_profile_ref']==contract['assurance_profile_ref'],
           'opaque test deployment binding; no assurance authenticity claim')
    reasons=[]
    if not any(row['object_kind']=='VERIFICATION_PROFILE' and all(row[k]==ref[k] for k in ref)
               and row['state'] in ('REGISTERED','ACTIVE') for row in envelope['bundle']['registry_snapshot']['entries']):
        reasons.append(b'PROFILE_UNAVAILABLE')
    if intent['contract_tuple']!=contract['contract_tuple']:reasons.append(b'CONTRACT_MISMATCH')
    return ('REJECTED' if reasons else 'SELECTED'),reasons


def check_causal(record,event_ref,frontier):
    events={c.encode(row['event_ref']):row for row in frontier['event_records']}
    before,after=c.encode(record['produced_by_event']),c.encode(event_ref)
    c.need(before in events and after in events,'SV-110: missing I/F event')
    i,f=events[before],events[after]
    c.need(i['event_kind']=='PHASE_I_VALIDATION' and i['subject_ref']==dict(tag='PHASE_I_RECORD',id=record['header']['id']),
           'SV-110: I event kind/subject')
    c.need(f['event_kind']=='PHASE_F_VALIDATION','SV-110: F event kind')
    # Strict ancestry, not array position or clock order. DAG closure checked by bundle.
    seen=set();todo=[c.encode(x) for x in f['parent_refs']]
    while todo:
        key=todo.pop()
        if key in seen:continue
        seen.add(key);todo.extend(c.encode(x) for x in events[key]['parent_refs'])
    c.need(before!=after and before in seen,'SV-110: strict I-before-F ancestry')
    root=c.encode(frontier['frontier_event_ref']);seen={root};todo=[root]
    while todo:
        key=todo.pop()
        for parent in events[key]['parent_refs']:
            encoded=c.encode(parent)
            if encoded not in seen:seen.add(encoded);todo.append(encoded)
    c.need(after in seen,'test frontier must include F in its causal past')


def inspect(raw,lock_pin,contract_pin,*,phase):
    c.need(phase in ('I','F'),'I/F phase required')
    value=c.decode(raw);key='transcript' if phase=='I' else 'envelope'
    c.fields(value,(key,'schema_lock','schema_documents','registry_objects','test_contract'))
    if contract_pin is not None:
        c.digest_bytes(contract_pin)
    c.need(c.digest_consistency(hashlib.sha256(c.encode(value['test_contract'])).digest()==contract_pin),'external test contract pin mismatch')
    imports=references.Imports(value['schema_lock'],value['schema_documents'],lock_pin)
    contract=value['test_contract'];typed(contract,'FixedAuditTestContract',imports)
    if phase=='I':
        transcript=value[key];typed(transcript,'PhaseITranscript',imports);envelope=transcript['input']
    else:
        envelope=value[key];typed(envelope,'PhaseFEnvelope',imports);transcript=envelope['phase_i_transcript']
    original=transcript['input'];record=transcript['output']
    # Reuse the entire scoped R5 path for each supplied bundle/Profile.
    for e in ([original] if phase=='I' else [original,envelope]):
        shadow=dict(envelope=dict(phase='R',bundle=e['bundle'],object=e['profile']),schema_lock=value['schema_lock'],
                    schema_documents=value['schema_documents'],registry_objects=value['registry_objects'])
        method_rules.inspect_audit(c.encode(shadow),lock_pin)
        check_context(e['creation_context'],e['bundle'],imports)
        check_object(e['intent'],'ReceiptIntent',imports)
    check_record(record,original,imports)
    outcome,reasons=replay_fixed_audit_test(original,contract)
    c.need((record['outcome'],record['failure_reasons'])==(outcome,reasons),'SV-102: fixed TEST replay mismatch')
    if phase=='F':
        c.need(c.reference_identity(record['creation_context_ref'])==c.reference_identity(identity(envelope['creation_context'])),'SV-96: CC-2F context identity')
        a,b=original['profile'],envelope['profile']
        c.need(all(a[k]==b[k] for k in ('profile_id','profile_version')),'SV-96: CC-3 Profile identity')
        c.need(content_map(original['intent'],'ReceiptIntent')==content_map(envelope['intent'],'ReceiptIntent') and
               original['slot']==envelope['selected_slot'],'SV-96: CC-3 Intent/slot')
        projected=dict(envelope,slot=envelope['selected_slot'])
        c.need(replay_fixed_audit_test(projected,contract)==(record['outcome'],record['failure_reasons']),
               'SV-102: fixed TEST F replay mismatch')
        c.need(record['outcome']=='SELECTED','SV-102: F requires SELECTED')
        check_causal(record,envelope['phase_f_event_ref'],envelope['bundle']['event_frontier_snapshot'])
    return dict(phase=phase,outcome=outcome,failure_reasons_hex=[x.hex() for x in reasons],
        context_digest_hex=envelope['creation_context']['header']['digest'].hex(),intent_digest_hex=record['intent_digest'].hex(),
        phase_i_record_digest_hex=record['header']['digest'].hex(),schema_lock_sha256=c.digest_record_hex(lock_pin),
        test_contract_sha256=c.digest_record_hex(contract_pin),full_schema_valid=False,full_phase_i_replay=False,
        source_authentication=False,production_admission=False,receipt_created=False)
