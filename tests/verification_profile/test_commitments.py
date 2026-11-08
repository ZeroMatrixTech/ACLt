# SPDX-License-Identifier: Apache-2.0
import copy,hashlib,json,runpy,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
from tools.verification_profile import codec as c,profile as p,registration as reg,commitments as r,validator
D=runpy.run_path(str(ROOT/'scripts/check-commitment-bindings.py'))


class CommitmentTests(unittest.TestCase):
    def fixture(self,op='registration',method='DIRECT_VERIFIED'):
        v,pin=D['fixture'](op,method);return v,pin,r.Imports(v['schema_lock'],v['schema_documents'],pin)

    def test_reducer_references_and_fixtures_are_isolated(self):
        a=r.default_reducer_ref();a['digest']=b'x'*32
        self.assertNotEqual(a,r.default_reducer_ref())
        first,_,_=self.fixture('state');second,_,_=self.fixture('state')
        first['payload']['result']['snapshot']['reducer_ref']['digest']=b'x'*32
        self.assertEqual(second['payload']['result']['snapshot']['reducer_ref'],r.default_reducer_ref())

    def test_frozen_vectors(self):
        rows=json.loads(D['VECTOR'].read_text())['vectors'];self.assertEqual(rows,D['vectors']())
        for row in rows:
            with self.subTest(id=row['id']):
                raw=bytes.fromhex(row['cbor_hex']);pin=bytes.fromhex(row['lock_pin'])
                if row['valid']:self.assertEqual(r.inspect(raw,pin),row['expected'])
                else:
                    with self.assertRaises(c.CodecError):r.inspect(raw,pin)

    def test_registration_all_methods_and_audit_omission(self):
        for method in p.METHODS:
            v,pin,_=self.fixture(method=method);self.assertFalse(r.inspect(c.encode(v),pin)['full_schema_valid'])
        v,pin,_=self.fixture(method='REEXEC_AUDIT_ONLY');v['payload']['profile']['verified_claim_spec']={};D['reseal'](v)
        with self.assertRaises(c.CodecError):r.inspect(c.encode(v),pin)

    def test_method_specific_exclusions_not_baseline_only(self):
        for method in p.METHODS[:-1]:
            v,pin,_=self.fixture(method=method);profile=v['payload']['profile'];profile['excluded_claims']['exclusion_ids'].remove(next(iter(r.SPECIFIC[method])));profile['excluded_claims']['digest']=r.references.excluded_digest(profile['excluded_claims']);profile['profile_digest']=p.profile_digest(profile)
            with self.assertRaisesRegex(c.CodecError,'SV-09'):r.inspect(c.encode(v),pin)

    def test_template_mapping_and_registry_identity(self):
        v,pin,_=self.fixture();v['payload']['profile']['verified_claim_spec']['claim_template_ref']['id']='acl.ct.wrong';D['reseal'](v)
        with self.assertRaisesRegex(c.CodecError,'SV-05'):r.inspect(c.encode(v),pin)
        for key,value in [('digest',b'x'*32),('version',[2,0,0])]:
            v,pin,_=self.fixture();v['payload']['profile']['verified_claim_spec']['claim_template_ref'][key]=value;D['reseal'](v)
            with self.assertRaisesRegex(c.CodecError,'SV-48'):r.inspect(c.encode(v),pin)

    def test_deprecated_or_revoked_template_cannot_register_spec(self):
        for state in ('DEPRECATED','REVOKED'):
            v,pin,_=self.fixture();snap=v['payload']['registry_snapshot'];next(x for x in snap['entries'] if x['object_kind']=='CLAIM_TEMPLATE')['state']=state;snap['header']['digest']=reg.registry_digest(snap)
            with self.assertRaisesRegex(c.CodecError,'SV-48'):r.inspect(c.encode(v),pin)

    def test_binding_schema_and_runtime_static_overlap(self):
        v,pin,_=self.fixture();profile=v['payload']['profile'];profile['verified_claim_spec']['binding_schema'].pop();D['reseal'](v)
        with self.assertRaisesRegex(c.CodecError,'SV-06'):r.inspect(c.encode(v),pin)
        v,pin,_=self.fixture();spec=v['payload']['profile']['verified_claim_spec'];spec['static_bindings'].append(dict(slot='output_ref',value=spec['static_bindings'][0]['value']));spec['static_bindings'].sort(key=lambda x:c.encode(x['slot']));D['reseal'](v)
        with self.assertRaisesRegex(c.CodecError,'SV-06'):r.inspect(c.encode(v),pin)

    def test_static_values_are_exact_native_frozen_fields(self):
        for method in p.METHODS[:-1]:
            v,pin,_=self.fixture(method=method);spec=v['payload']['profile']['verified_claim_spec'];spec['static_bindings'][0]['value']=D['wrap'](v,b'forged');D['reseal'](v)
            with self.assertRaisesRegex(c.CodecError,'SV-44'):r.inspect(c.encode(v),pin)
        v,_,_=self.fixture(method='PROOF_VERIFIED');values=r.static_values(v['payload']['profile']);self.assertEqual(values['params_ref'],v['payload']['profile']['method_parameters']['public_params_ref'])

    def test_native_declarations_compare_canonical_bytes_not_python_equality(self):
        v,pin,_=self.fixture()
        next(x for x in v['payload']['template']['slot_decls'] if x['slot']=='soundness_class')['decl']['value_type']=True
        next(x for x in v['payload']['profile']['verified_claim_spec']['binding_schema'] if x['slot']=='soundness_class')['decl']['value_type']=1
        D['rebind_registration'](v)
        with self.assertRaisesRegex(c.CodecError,'SV-06'):r.inspect(c.encode(v),pin)

    def test_version_range_slots_must_be_runtime(self):
        for slot in ('protocol_version','rir_version','rpr_profile_version','frontend_profile_version'):
            v,pin,_=self.fixture(method='REEXEC_BOUNDED');q=v['payload'];q['profile']['contract_tuple_constraints']['frontend_profile_version_range']={0:[1,0,0]}
            for rows in (q['template']['slot_decls'],q['profile']['verified_claim_spec']['binding_schema']):
                row=next((x for x in rows if x['slot']==slot),None)
                if row is None:rows.append(dict(slot=slot,decl=dict(kind='STATIC',value_type='VERSION',source='PROFILE')))
                else:row['decl'].update(kind='STATIC',source='PROFILE')
                rows.sort(key=lambda x:c.encode(x['slot']))
            D['rebind_registration'](v)
            with self.assertRaisesRegex(c.CodecError,'SV-49'):r.inspect(c.encode(v),pin)

    def test_concrete_static_substitution_fails_even_with_new_claim_hash(self):
        v,pin,_=self.fixture('claim-guard');q=v['payload'];b=q['claim_binding'];next(x for x in b['concrete_bindings'] if x['slot_id']=='predicate_ref')['value']=D['wrap'](v,'acl.pred.other@1.0.0');b['rendered_claim_digest']=r.rendered_digest(b['claim_template_ref'],b['concrete_bindings'])
        with self.assertRaisesRegex(c.CodecError,'SV-35'):r.inspect(c.encode(v),pin)

    def test_trusted_requires_complete_claim_binding(self):
        v,pin,_=self.fixture('claim-guard');v['payload'].pop('claim_binding')
        with self.assertRaisesRegex(c.CodecError,'SV-36'):r.inspect(c.encode(v),pin)
        v,pin,_=self.fixture('claim-guard','REEXEC_AUDIT_ONLY');v['payload']['terminal_state']='TRUSTED'
        with self.assertRaisesRegex(c.CodecError,'SV-36'):r.inspect(c.encode(v),pin)

    def test_hashes_against_independent_domain_prefix_and_projection(self):
        def digest(tag,value):
            raw=tag.encode();return hashlib.sha256(bytes([len(raw)])+raw+c.encode(value)).digest()
        for op,kind in [('template-digest','ClaimTemplate'),('assurance-digest','MainnetAssuranceProfile')]:
            v,_,_=self.fixture(op);obj=v['payload']['object'];h=obj['header'];projection={k:h[k] for k in ('schema_version','encoding_profile_id')}|{k:x for k,x in obj.items() if k not in ('header','translations','human_summary')};self.assertEqual(r.object_digest(obj,kind),digest('ACLt/P0-1/'+kind+'/1',projection))
        v,_,_=self.fixture('state');snapshot=v['payload']['result']['snapshot'];h=snapshot['header'];projection={k:h[k] for k in ('schema_version','encoding_profile_id','id')}|{k:x for k,x in snapshot.items() if k!='header'};self.assertEqual(r.object_digest(snapshot,'AssumptionStateSnapshot'),digest('ACLt/P0-1/AssumptionStateSnapshot/1',projection));self.assertEqual(r.state_digest(snapshot),digest('ACLt/P0-1/AssumptionState/1',[snapshot['reducer_ref'],sorted(snapshot['assumption_states'],key=lambda x:c.encode(x['assumption_id']))]))
        v,_,_=self.fixture('rendered-digest');q=v['payload'];self.assertEqual(q['digest'],digest('ACLt/P0-1/RenderedClaim/1',[q['template_ref'],q['bindings']]))
        v,_,i=self.fixture('decision-input-digest');self.assertEqual(r.decision_input_digest(v['payload']['evaluation_input'],i),digest('ACLt/P0-1/DecisionEvaluationInput/1',v['payload']['evaluation_input']))

    def test_snapshot_identity_and_state_digest_are_different_commitments(self):
        v,_,_=self.fixture('state');s=v['payload']['result']['snapshot'];a=r.object_digest(s,'AssumptionStateSnapshot');b=r.state_digest(s)
        s['header']['id']='acl.ass.'+'1'*26;self.assertNotEqual(a,r.object_digest(s,'AssumptionStateSnapshot'));self.assertEqual(b,r.state_digest(s));s['receipt_id']=b'x'*32;self.assertEqual(b,r.state_digest(s))

    def test_versioned_identity_and_advisory_do_not_change_digest(self):
        for op,kind,field,value in [('template-digest','ClaimTemplate','translations',[dict(lang='en',text='different')]),('assurance-digest','MainnetAssuranceProfile','human_summary',b'different')]:
            v,_,_=self.fixture(op);x=v['payload']['object'];old=r.object_digest(x,kind);x[field]=value;x['header']['version']=[3,0,0];self.assertEqual(old,r.object_digest(x,kind))

    def test_template_enum_contents_are_hashed_without_inventing_semantics(self):
        v,_,i=self.fixture('template-digest');obj=v['payload']['object'];old=r.object_digest(obj,'ClaimTemplate');row=next(x for x in obj['slot_decls'] if x['slot']=='soundness_class');row['decl']['value_type']={'enum':['SOUND','DIFFERENT']};new=r.object_digest(obj,'ClaimTemplate');self.assertNotEqual(old,new);obj['header']['digest']=new;r.check_digest(obj,'ClaimTemplate',i)

    def test_payload_schema_digest_and_canonical_bytes_are_bound(self):
        v,pin,_=self.fixture();row=v['payload']['profile']['verified_claim_spec']['static_bindings'][0]['value'];row['canonical_bytes']=c.encode(b'changed');D['reseal'](v)
        with self.assertRaisesRegex(c.CodecError,'digest'):r.inspect(c.encode(v),pin)

    def test_state_rows_cover_exact_noninformational_assumptions(self):
        v,pin,_=self.fixture('state','REEXEC_BOUNDED');s=v['payload']['result']['snapshot'];self.assertEqual(len(s['assumption_states']),5);s['assumption_states'].pop();s['header']['digest']=r.object_digest(s,'AssumptionStateSnapshot');v['payload']['assumption_state_digest']=r.state_digest(s)
        with self.assertRaisesRegex(c.CodecError,'SV-54a'):r.inspect(c.encode(v),pin)

    def test_cause_order_uses_encoded_bytes_and_keeps_all_facts(self):
        v,pin,_=self.fixture('state','REEXEC_BOUNDED');s=v['payload']['result']['snapshot'];row=s['assumption_states'][0];row['cause_set']=sorted([dict(cause_code=x,evidence_ref=b'cause',observed_event_ref=x.encode()) for x in r.CAUSE_ORDER],key=lambda x:c.encode(x['cause_code']));row['effective_verdict']='REVOKED';s['header']['digest']=r.object_digest(s,'AssumptionStateSnapshot');v['payload']['assumption_state_digest']=r.state_digest(s);r.inspect(c.encode(v),pin);self.assertEqual([x['cause_code'] for x in row['cause_set']],['REVOKED','OUT_OF_SCOPE','WINDOW_EXPIRED']);row['cause_set'].sort(key=lambda x:x['cause_code']);s['header']['digest']=r.object_digest(s,'AssumptionStateSnapshot');v['payload']['assumption_state_digest']=r.state_digest(s)
        with self.assertRaises(c.CodecError):r.inspect(c.encode(v),pin)

    def test_forged_valid_verdict_does_not_survive_rehash(self):
        v,pin,_=self.fixture('state');s=v['payload']['result']['snapshot'];row=s['assumption_states'][0];row['cause_set']=[dict(cause_code='REVOKED',evidence_ref=b'evidence',observed_event_ref=b'event')];row['effective_verdict']='VALID';s['header']['digest']=r.object_digest(s,'AssumptionStateSnapshot');v['payload']['assumption_state_digest']=r.state_digest(s)
        with self.assertRaisesRegex(c.CodecError,'SV-54a'):r.inspect(c.encode(v),pin)

    def test_evidence_version_and_reducer_cannot_be_substituted(self):
        for key,value in [('evidence_version',[9,0,0]),('evidence_ref',b'other')]:
            v,pin,_=self.fixture('state');s=v['payload']['result']['snapshot'];s['assumption_states'][0][key]=value;s['header']['digest']=r.object_digest(s,'AssumptionStateSnapshot')
            with self.assertRaisesRegex(c.CodecError,'evidence'):r.inspect(c.encode(v),pin)
        v,pin,_=self.fixture('state');s=v['payload']['result']['snapshot'];s['reducer_ref']['digest']=b'x'*32;s['header']['digest']=r.object_digest(s,'AssumptionStateSnapshot')
        with self.assertRaisesRegex(c.CodecError,'reducer'):r.inspect(c.encode(v),pin)

    def test_invalidating_failure_needs_neither_snapshot_nor_digest(self):
        v,pin,_=self.fixture('state');q=v['payload'];q.pop('assumption_state_digest');q['result']=dict(tag='INVALIDATING',failure=dict(assumption_id='ACL-ASM-0002',failure_class='EVIDENCE_UNAVAILABLE',observed_at=1));r.inspect(c.encode(v),pin);q['assumption_state_digest']=b'x'*32
        with self.assertRaises(c.CodecError):r.inspect(c.encode(v),pin)

    def test_receipt_and_snapshot_identity_match_full_reference(self):
        v,pin,_=self.fixture('claim-guard');q=v['payload'];s=q['assumption_result']['snapshot'];s['receipt_id']=b'x'*32;s['header']['digest']=r.object_digest(s,'AssumptionStateSnapshot');q['claim_binding']['assumption_state_snapshot_ref']={k:s['header'][k] for k in ('id','digest')}
        with self.assertRaisesRegex(c.CodecError,'SV-78'):r.inspect(c.encode(v),pin)

    def test_safety_failure_prevents_trusted_even_with_consistent_hashes(self):
        v,pin,_=self.fixture('claim-guard');q=v['payload'];s=q['assumption_result']['snapshot'];s['assumption_states'][0]['cause_set']=[dict(cause_code='REVOKED',evidence_ref=b'e',observed_event_ref=b'event')];s['assumption_states'][0]['effective_verdict']='REVOKED';s['header']['digest']=r.object_digest(s,'AssumptionStateSnapshot');q['claim_binding']['assumption_state_snapshot_ref']={k:s['header'][k] for k in ('id','digest')};q['claim_binding']['assumption_state_digest']=r.state_digest(s)
        with self.assertRaisesRegex(c.CodecError,'SV-57'):r.inspect(c.encode(v),pin)

    def test_input_digest_binds_every_explicit_field(self):
        v,_,i=self.fixture('decision-input-digest');value=v['payload']['evaluation_input'];old=r.decision_input_digest(value,i)
        for field in value:
            altered=copy.deepcopy(value);altered.pop(field)
            with self.assertRaises(c.CodecError):r.decision_input_digest(altered,i)
        altered=copy.deepcopy(value);altered['boundary_observation']={'funding_event_ref':b'funding'};self.assertNotEqual(old,r.decision_input_digest(altered,i))

    def test_reference_only_method_input_is_rejected_even_if_rehashed(self):
        v,pin,_=self.fixture('decision-input-digest');q=v['payload'];q['evaluation_input']['method_evaluation']['canonical_input']=b'reference';q['input_digest']=c.domain_hash('ACLt/P0-1/DecisionEvaluationInput/1',c.encode(q['evaluation_input']))
        with self.assertRaises(c.CodecError):r.inspect(c.encode(v),pin)

    def test_all_runtime_references_are_unversioned_and_typed(self):
        v,pin,i=self.fixture();prefixes={'AssumptionStateSnapshot':'acl.ass.','CreationValidationContext':'acl.cctx.','PhaseIValidationRecord':'acl.pir.','EventFrontierSnapshot':'acl.efs.'}
        for kind,prefix in prefixes.items():
            ref=dict(id=prefix+'0'*26,digest=b'x'*32);r.runtime_ref(kind,ref,i)
            with self.assertRaises(c.CodecError):r.runtime_ref(kind,ref|{'version':[1,0,0]},i)
            with self.assertRaises(c.CodecError):r.runtime_ref(kind,dict(id='acl.cctx.'+'0'*26 if prefix!='acl.cctx.' else 'acl.ass.'+'0'*26,digest=b'x'*32),i)

    def test_candidate_derives_fields_from_one_committed_capsule(self):
        v,pin,_=self.fixture('candidate-input');out=r.inspect(c.encode(v),pin);capsule=v['payload']['candidate'];scope=c.decode(bytes.fromhex(out['declared_scope_cbor_hex']));self.assertEqual(scope['task_class'],capsule['task_type']);self.assertEqual(scope['rpr_version'],capsule['contract_tuple']['rpr_version']);self.assertEqual(out['n_max_decimal'],'5');self.assertFalse(out['normative_intent_upgrade']);old=out['candidate_digest_hex'];capsule['n_max']=6;self.assertNotEqual(old,r.inspect(c.encode(v),pin)['candidate_digest_hex']);capsule['declared_scope']={}
        with self.assertRaises(c.CodecError):r.inspect(c.encode(v),pin)

    def test_candidate_contract_copy_cannot_drift_from_base_intent(self):
        v,pin,_=self.fixture('candidate-input');v['payload']['candidate']['contract_tuple']['rpr_version']=[2,0,0]
        with self.assertRaisesRegex(c.CodecError,'ContractTuple'):r.inspect(c.encode(v),pin)

    def test_candidate_scope_empty_and_limit_bool_fail_closed(self):
        for field,value in [('fault_domains',[]),('geography',[]),('n_max',True),('n_max',-1)]:
            v,pin,_=self.fixture('candidate-input');v['payload']['candidate'][field]=value
            with self.assertRaises(c.CodecError):r.inspect(c.encode(v),pin)

    def test_native_import_is_explicit_and_namespace_restricted(self):
        v,pin,_=self.fixture();doc=next(x for x in v['schema_documents'] if c.decode(x['content'])['alias']=='NativeValue');body=c.decode(doc['content']);body['id']='acl.schema.other@1';raw=c.encode(body);ref=dict(id=body['id'],version=[1,0,0],digest=hashlib.sha256(raw).digest());doc.update(ref=ref,content=raw);next(x for x in v['schema_lock']['entries'] if x['alias']=='NativeValue')['ref']=ref
        with self.assertRaisesRegex(c.CodecError,'namespace'):r.Imports(v['schema_lock'],v['schema_documents'],D['pin'](v['schema_lock']))

    def test_binding_check_does_not_emit_decision_or_enable_disabled_map(self):
        v,pin,_=self.fixture('claim-guard');self.assertEqual(v['payload']['assurance_profile']['profile_capabilities'][0]['disposition'],'DISABLED');out=r.inspect(c.encode(v),pin)
        for field in ('full_schema_valid','full_phase_i_replay','source_authentication','production_admission','protocol_decision_emitted'):self.assertFalse(out[field])

    def test_cli_and_optimization_mode_keep_production_closed(self):
        v,pin,_=self.fixture('assurance-digest')
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'input.cbor';f.write_bytes(c.encode(v));cmd=[sys.executable,'-B','-m','tools.verification_profile.validator',str(f),'--commitment-bindings-cbor','--schema-lock-sha256',pin.hex()];result=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stdout+result.stderr);self.assertNotEqual(subprocess.run(cmd+['--production'],cwd=ROOT,capture_output=True).returncode,0)
            f.write_bytes(b'\xff');self.assertNotEqual(subprocess.run([sys.executable,'-O',*cmd[1:]],cwd=ROOT,capture_output=True).returncode,0)

if __name__=='__main__':unittest.main()
