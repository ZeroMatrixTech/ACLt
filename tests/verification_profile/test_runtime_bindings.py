# SPDX-License-Identifier: Apache-2.0
import copy,runpy,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
from tools.verification_profile import codec as c,runtime_bindings as r,validator
D=runpy.run_path(str(ROOT/'scripts/check-runtime-bindings.py'))

class RuntimeBindingTests(unittest.TestCase):
    def fixture(self,*args,**kwargs):return D['fixture'](*args,**kwargs)
    def inspect(self,v,lp=None,cp=None):
        return r.inspect(c.encode(v),lp or D['pin'](v['schema_lock']),cp or D['pin'](v['runtime_contract']))
    def assertRejected(self,v,rule=None,consequence=None):
        D['seal'](v);out=self.inspect(v);self.assertFalse(out['accepted'])
        if rule:self.assertEqual(out['failure_rule'],rule)
        if consequence:self.assertEqual(out['consequence'],consequence)
        self.assertFalse(out['production_admission']);self.assertFalse(out['state_committed']);return out
    def test_frozen_vectors(self):
        rows, _ = D['pinned_vectors']()
        for row in rows:
            with self.subTest(id=row['id']):
                if row['error']:
                    with self.assertRaises(c.CodecError):r.inspect(bytes.fromhex(row['cbor_hex']),bytes.fromhex(row['lock_pin']),bytes.fromhex(row['contract_pin']))
                else:self.assertEqual(r.inspect(bytes.fromhex(row['cbor_hex']),bytes.fromhex(row['lock_pin']),bytes.fromhex(row['contract_pin'])),row['expected'])
    def test_all_seven_tags_have_positive_and_negative_vectors(self):
        rows, _ = D['pinned_vectors']()
        for tag in r.SHAPES:
            self.assertTrue(any(x['id']=='valid-'+tag and x['accepted'] for x in rows))
            self.assertTrue(any(tag in x['id'] and not x['accepted'] for x in rows))
    def test_actual_scope_requires_all_six_dimensions_and_nonempty_sets(self):
        v,_,_=self.fixture();actual=v['envelope']['payload']['actual_bound_scope']
        for key in actual:
            bad=copy.deepcopy(v);bad['envelope']['payload']['actual_bound_scope'].pop(key)
            with self.subTest(key=key),self.assertRaises(c.CodecError):self.inspect(bad)
        for key in ('fault_domains','geography'):
            bad=copy.deepcopy(v);bad['envelope']['payload']['actual_bound_scope'][key]=[]
            with self.subTest(key=key),self.assertRaises(c.CodecError):self.inspect(bad)
    def test_actual_scope_not_replaced_by_declared_or_information_only(self):
        v,_,_=self.fixture();v['envelope']['payload']['actual_bound_scope']['geography']=[b'outside'];self.assertRejected(v,'SV-68')
        v,_,_=self.fixture();info=next(x for x in v['envelope']['profile']['assumption_references'] if x['role']=='INFORMATIONAL');info['scope']['geography']=[b'outside'];profile=v['envelope']['profile'];old=profile['profile_digest'];profile['profile_digest']=r.p.profile_digest(profile)
        def replace(x):
            if isinstance(x,dict):
                if x.get('digest')==old:x['digest']=profile['profile_digest']
                for child in x.values():replace(child)
            elif isinstance(x,list):
                for child in x:replace(child)
        replace(v);assurance=v['envelope']['assurance_profile'];assurance['header']['digest']=r.b.object_digest(assurance,'MainnetAssuranceProfile');v['envelope']['receipt_binding']['assurance_profile_ref']=r.b.identity(assurance)
        registry=v['envelope']['bundle']['registry_snapshot'];registry['header']['digest']=r.reg.registry_digest(registry);D['seal'](v)
        self.assertTrue(self.inspect(v)['accepted'])
    def test_scope_checks_every_population_unit(self):
        v,_,_=self.fixture();D['snapshot_edit'](v,lambda s:s['sampling_units'][-1]['scope'].update(environment_class=b'outside'));self.assertRejected(v,'SV-69')
    def test_duplicate_units_reject_without_silent_deduplication(self):
        v,_,_=self.fixture();D['snapshot_edit'](v,lambda s:s['sampling_units'].append(copy.deepcopy(s['sampling_units'][0])));self.assertRejected(v,'SV-82')
    def test_population_count_matches_frozen_G(self):
        v,_,_=self.fixture();D['snapshot_edit'](v,lambda s:s['sampling_units'].pop());self.assertRejected(v,'SV-81')
    def test_population_definition_and_schema_bind_to_profile(self):
        for key in ('population_definition_ref','snapshot_schema_ref'):
            v,_,_=self.fixture();D['snapshot_edit'](v,lambda s:s.update({key:b'other'}));self.assertRejected(v,'SV-81')
    def test_randomness_contract_and_parameters_require_external_pin(self):
        v,lp,cp=self.fixture();v['runtime_contract']['scheme_id']='attacker'
        with self.assertRaises(c.CodecError):self.inspect(v,lp,cp)
        v,_,_=self.fixture();D['snapshot_edit'](v,lambda s:s['randomness_commitment'].update(parameters=True));self.assertRejected(v,'SV-81')
    def test_native_randomness_bool_is_not_integer(self):
        v,_,_=self.fixture();v['runtime_contract']['allowed_randomness_parameters']=[1];D['snapshot_edit'](v,lambda s:s['randomness_commitment'].update(parameters=True));self.assertRejected(v,'SV-81')
    def test_receipt_and_all_four_profile_links_are_exact(self):
        v,_,_=self.fixture();D['snapshot_edit'](v,lambda s:s.update(receipt_id=b'x'*32));self.assertRejected(v,'SV-92')
        v,_,_=self.fixture();v['envelope']['payload']['transition']['prior_round_state']['bound_profile_ref']['digest']=b'x'*32;self.assertRejected(v,'SV-92')
    def test_assurance_identity_and_network_are_not_self_selected(self):
        for key in ('network_id','assurance_profile_ref'):
            v,_,_=self.fixture();binding=v['envelope']['receipt_binding'];binding[key]=b'other' if key=='network_id' else dict(binding[key],digest=b'x'*32);self.assertRejected(v,'SV-92')
    def test_mapping_first_fix_is_unique_and_requires_matching_event(self):
        v,_,_=self.fixture('CLUSTER_MAPPING_FIX');prior=v['envelope']['payload']['transition']['prior_round_state'];prior['cluster_mapping_ref']=copy.deepcopy(v['envelope']['payload']['transition']['proposed_round_state']['cluster_mapping_ref']);self.assertRejected(v,'SV-106')
        v,_,_=self.fixture('CLUSTER_MAPPING_FIX');v['envelope']['payload']['cluster_mapping_fixed_event']=b'unknown';self.assertRejected(v,'SV-106')
    def test_mapping_cannot_be_introduced_by_a_different_tag(self):
        v,_,_=self.fixture('ROUND_TRANSITION_PRE_FREEZE');v['envelope']['payload']['transition']['prior_round_state'].pop('cluster_mapping_ref');self.assertRejected(v,'SV-106')
    def test_mapping_cannot_be_removed_or_changed_after_freeze(self):
        for edit in ('remove','replace'):
            v,_,_=self.fixture('ROUND_TRANSITION_POST_FREEZE');after=v['envelope']['payload']['transition']['proposed_round_state']
            if edit=='remove':after.pop('cluster_mapping_ref');self.assertRejected(v,'SV-94')
            else:after['cluster_mapping_ref']['digest']=b'x'*32;self.assertRejected(v,'SV-106')
    def test_cluster_mapping_runtime_ref_has_no_version_and_exact_id_domain(self):
        for changes in (dict(version=[1,0,0]),dict(id='acl.ass.'+'0'*26)):
            v,_,_=self.fixture();v['envelope']['payload']['transition']['prior_round_state']['cluster_mapping_ref'].update(changes)
            with self.assertRaises(c.CodecError):self.inspect(v)
    def test_snapshot_mapping_equals_both_states_and_freeze_record(self):
        v,_,_=self.fixture();v['envelope']['payload']['transition']['snapshot_freeze_record']['cluster_mapping_ref']['digest']=b'x'*32;self.assertRejected(v,'SV-99')
    def test_scope_filter_set_difference_is_checked_before_count(self):
        v,_,_=self.fixture();v['envelope']['payload']['transition']['snapshot_freeze_record']['excluded_by_scope']=[];self.assertRejected(v,'SV-94')
    def test_filtered_set_must_equal_snapshot_units_not_only_cardinality(self):
        v,_,_=self.fixture();record=v['envelope']['payload']['transition']['snapshot_freeze_record'];old=record['frozen_units'][0];record['frozen_units'][0]=b'other';record['frozen_units'].sort(key=c.encode);record['candidate_units_pre_scope_filter'].remove(old);record['candidate_units_pre_scope_filter'].append(b'other');record['candidate_units_pre_scope_filter'].sort(key=c.encode);self.assertRejected(v,'SV-94')
    def test_frozen_parameters_bind_every_field_including_full_weights(self):
        v,_,_=self.fixture();v['envelope']['payload']['transition']['proposed_round_state']['frozen_parameters']['mixture_weights']=[dict(m=2,weight=[1,1])];self.assertRejected(v,'SV-94')
    def test_freeze_events_need_strict_causality_not_array_order(self):
        v,_,_=self.fixture();f=v['envelope']['bundle']['event_frontier_snapshot'];next(x for x in f['event_records'] if x['event_ref']==b'freeze')['parent_refs']=[b'root'];self.assertRejected(v,'SV-107')
    def test_freeze_events_bind_kind_and_subject(self):
        v,_,_=self.fixture();next(x for x in v['envelope']['bundle']['event_frontier_snapshot']['event_records'] if x['event_ref']==b'freeze')['subject_ref']['id']='foreign';self.assertRejected(v,'SV-107')
    def test_freeze_events_must_be_visible_from_frontier(self):
        v,_,_=self.fixture();v['envelope']['bundle']['event_frontier_snapshot']['frontier_event_ref']=b'root';self.assertRejected(v,'SV-107')
    def test_cyclic_or_unclosed_dag_is_structurally_rejected(self):
        for parent in (b'freeze',b'missing'):
            v,_,_=self.fixture();f=v['envelope']['bundle']['event_frontier_snapshot'];next(x for x in f['event_records'] if x['event_ref']==b'fix')['parent_refs']=[parent];D['seal'](v)
            with self.assertRaises(c.CodecError):self.inspect(v)
    def test_four_failure_consequences_do_not_mutate_input(self):
        for stage,consequence in r.CONSEQUENCES.items():
            tag='LEASE_ACTIVATION_PRE_FREEZE' if stage=='PRE_FREEZE' else 'LEASE_ACTIVATION_POST_FREEZE';v,_,_=self.fixture(tag,stages=(stage,stage));v['envelope']['bound_profile_ref']['digest']=b'x'*32;D['seal'](v);before=c.encode(v);self.assertRejected(v,'SV-92',consequence);self.assertEqual(before,c.encode(v))
    def test_no_snapshot_paths_keep_full_start_and_terminal_constraints(self):
        for method in ('DIRECT_VERIFIED','PROOF_VERIFIED','REEXEC_AUDIT_ONLY'):
            for pair in (('PRE_FREEZE','RUNNING'),('RUNNING','RUNNING'),('RUNNING','TERMINAL'),('PRE_FREEZE','TERMINAL')):
                v,_,_=self.fixture('ROUND_TRANSITION_NO_SNAPSHOT',method,pair);self.assertTrue(self.inspect(v)['accepted'])
    def test_disabled_assurance_never_becomes_admission_permission(self):
        v,_,_=self.fixture();self.assertTrue(self.inspect(v)['accepted']);self.assertEqual(v['envelope']['assurance_profile']['profile_capabilities'][0]['disposition'],'DISABLED');out=self.inspect(v);self.assertFalse(out['formal_phase_b_conformance']);self.assertFalse(out['protocol_decision_emitted']);self.assertFalse(out['production_admission'])
    def test_snapshot_digest_and_import_canonical_bytes_cannot_be_forged(self):
        v,_,_=self.fixture();v['envelope']['payload']['eligibility_snapshot']['object_digest']=b'x'*32
        with self.assertRaises(c.CodecError):self.inspect(v)
    def test_cli_reports_semantic_rejection_and_production_stays_closed(self):
        v,lp,cp=self.fixture();raw=c.encode(v);self.assertEqual(validator.validate_runtime_bindings_cbor(raw,lp,cp),[])
        v['envelope']['bound_profile_ref']['digest']=b'x'*32;self.assertTrue(validator.validate_runtime_bindings_cbor(c.encode(v),lp,cp))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'input.cbor';path.write_bytes(raw);command=[sys.executable,'-B','-m','tools.verification_profile.validator',str(path),'--runtime-bindings-cbor','--schema-lock-sha256',lp.hex(),'--runtime-contract-sha256',cp.hex()]
            self.assertEqual(subprocess.run(command,cwd=ROOT,capture_output=True).returncode,0);self.assertNotEqual(subprocess.run(command+['--production'],cwd=ROOT,capture_output=True).returncode,0)
    def test_cli_requires_both_pins_and_one_entry(self):
        command=[sys.executable,'-B','-m','tools.verification_profile.validator','unused','--runtime-bindings-cbor']
        self.assertNotEqual(subprocess.run(command,cwd=ROOT,capture_output=True).returncode,0)
        self.assertNotEqual(subprocess.run(command+['--commitment-bindings-cbor','--schema-lock-sha256','00'*32,'--runtime-contract-sha256','00'*32],cwd=ROOT,capture_output=True).returncode,0)

if __name__=='__main__':unittest.main()
