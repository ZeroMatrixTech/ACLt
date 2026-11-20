# SPDX-License-Identifier: Apache-2.0
import copy,hashlib,json,runpy,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
from tools.verification_profile import codec as c,profile as p,registration as reg,references,selection as r,validator
D=runpy.run_path(str(ROOT/'scripts/check-selection-assets.py'))


class SelectionTests(unittest.TestCase):
    def fixture(self,op='policy'):
        v,pin=D['fixture'](op);i=references.Imports(v['schema_lock'],v['schema_documents'],pin);return v,pin,i

    def test_frozen_vectors(self):
        rows=json.loads(D['VECTOR'].read_text())['vectors'];self.assertEqual(rows,D['vectors']())
        for row in rows:
            with self.subTest(id=row['id']):
                args=bytes.fromhex(row['cbor_hex']),bytes.fromhex(row['lock_pin'])
                if row['id'] in D['SHA_RECORD_ONLY_CASES']:
                    r.inspect(*args)
                elif row['valid']:self.assertEqual(r.inspect(*args),row['expected'])
                else:
                    with self.assertRaises(c.CodecError):r.inspect(*args)

    def test_assumption_refs_require_exact_class_and_role(self):
        v,_,_=self.fixture('profile-refs');profile=v['payload']['profile'];r.check_parameter_refs(profile)
        for block,key,owner in [('safety_parameters','support_capability_bound_ref','SV-12R'),('liveness_parameters','calibration_ref','SV-47')]:
            wrong=copy.deepcopy(profile);wrong[block][key]='ACL-ASM-9999'
            with self.assertRaisesRegex(c.CodecError,owner):r.check_parameter_refs(wrong)
            wrong=copy.deepcopy(profile);row=next(x for x in wrong['assumption_references'] if x['assumption_id']==wrong[block][key]);row['role']='INFORMATIONAL'
            with self.assertRaisesRegex(c.CodecError,owner):r.check_parameter_refs(wrong)

    def test_profile_lifecycle_is_not_registration_authorization(self):
        v,_,_=self.fixture('profile-lookup');q=v['payload'];entry=next(x for x in q['registry_snapshot']['entries'] if x['id']==q['profile']['profile_id'])
        for state,expected in [('REGISTERED',True),('ACTIVE',True),('DEPRECATED',False),('REVOKED',False)]:
            entry['state']=state;q['registry_snapshot']['header']['digest']=reg.registry_digest(q['registry_snapshot'])
            self.assertEqual(r.profile_admissible(q['profile'],q['registry_snapshot']),expected)

    def test_selected_slot_matches_id_version_with_digest_record(self):
        v,_,_=self.fixture('profile-lookup');q=v['payload'];r.check_selected(q['slot'],q['profile'],q['registry_snapshot'])
        for key,value in [('id','acl.vp.other.audit'),('version',[2,0,0]),('digest',b'x'*32)]:
            slot=copy.deepcopy(q['slot']);slot['profile_ref'][key]=value
            if key=='digest':r.check_selected(slot,q['profile'],q['registry_snapshot'])
            else:
                with self.assertRaisesRegex(c.CodecError,'SV-45'):r.check_selected(slot,q['profile'],q['registry_snapshot'])

    def test_expansion_keeps_gate_per_candidate_and_adjacency(self):
        v,_,i=self.fixture();q=v['payload'];policy=q['policy'];policy['ordered_candidates'].append(copy.deepcopy(policy['ordered_candidates'][0]));policy['ordered_candidates'][1]['gate']=b'other'
        slots=r.expand(policy['ordered_candidates'],q['profiles'],q['registry_snapshot']);self.assertEqual([x['index'] for x in slots],[0,1,2,3]);self.assertEqual([x['kind'] for x in slots],['PRIMARY','DEGRADED','PRIMARY','DEGRADED']);self.assertEqual(slots[0]['gate'],b'gate-one');self.assertEqual(slots[2]['gate'],b'other');self.assertNotIn('gate',slots[1]);self.assertEqual(slots[3]['degraded_from'],2)
        policy['expanded_slots']=slots;D['seal'](v);r.check_policy(policy,q['profiles'],q['registry_snapshot'],q['edges'],i)

    def test_expansion_cannot_be_chosen_by_caller(self):
        v,_,i=self.fixture();q=v['payload'];q['policy']['expanded_slots'][1]['index']=0;D['seal'](v)
        with self.assertRaisesRegex(c.CodecError,'SV-41'):r.check_policy(q['policy'],q['profiles'],q['registry_snapshot'],q['edges'],i)
        v,_,i=self.fixture();q=v['payload'];q['policy']['expanded_slots'][1]['degraded_from']=1;D['seal'](v)
        with self.assertRaisesRegex(c.CodecError,'SV-53a'):r.check_policy(q['policy'],q['profiles'],q['registry_snapshot'],q['edges'],i)

    def test_degradation_requires_one_explicit_valid_edge(self):
        v,pin,_=self.fixture();v['payload']['edges']=[]
        with self.assertRaisesRegex(c.CodecError,'weakening edge'):r.inspect(c.encode(v),pin)
        v,pin,_=self.fixture();v['payload']['edges']*=2
        with self.assertRaisesRegex(c.CodecError,'weakening edge'):r.inspect(c.encode(v),pin)

    def test_edge_four_frozen_semantic_conditions(self):
        for field in ('task_type','contract_tuple_constraints','result_equivalence','excluded_claims'):
            v,pin,_=self.fixture('edge');target=v['payload']['profiles'][1]
            if field=='task_type':target[field]='acl.tt.other'
            elif field=='contract_tuple_constraints':target[field]['allowed_effects']=[b'other']
            elif field=='result_equivalence':target[field]['equivalence_id']='acl.eq.other@1'
            else:target[field]['exclusion_ids'].pop()
            D['rebind'](v)
            with self.assertRaisesRegex(c.CodecError,'SV-21'):r.inspect(c.encode(v),pin)

    def test_edge_cannot_reverse_or_strengthen_claim(self):
        v,pin,_=self.fixture('edge');q=v['payload'];q['edge']['source'],q['edge']['target']=q['edge']['target'],q['edge']['source'];D['seal'](v)
        with self.assertRaisesRegex(c.CodecError,'SV-21'):r.inspect(c.encode(v),pin)
        v,pin,_=self.fixture('edge');v['payload']['profiles'][1]['verified_claim_spec']={};D['rebind'](v)
        with self.assertRaisesRegex(c.CodecError,'SV-21'):r.inspect(c.encode(v),pin)

    def test_three_asset_hashes_use_exact_domain_and_projection(self):
        for op,kind,tag in [('policy','PolicyR7','SelectionPolicy'),('edge','EdgeR7','WeakeningEdge'),('manifest','ManifestR7','Manifest')]:
            v,_,_=self.fixture(op);value=v['payload'][op];h=value['header'];projection={k:h[k] for k in ('schema_version','encoding_profile_id')}|{k:x for k,x in value.items() if k!='header'};prefix=('ACLt/P0-1/'+tag+'/1').encode();digest=hashlib.sha256(bytes([len(prefix)])+prefix+c.encode(projection)).digest();self.assertEqual(r.asset_digest(value,kind),digest)
            h['id']+='-other';h['version']=[9,0,0];h['digest']=b'x'*32;self.assertEqual(r.asset_digest(value,kind),digest)

    def test_policy_digest_includes_candidates_slots_and_exhaustion(self):
        v,_,_=self.fixture();q=v['payload']['policy'];old=r.asset_digest(q,'PolicyR7')
        for field,value in [('on_none_applicable','OTHER'),('ordered_candidates',[]),('expanded_slots',[])]:
            changed=copy.deepcopy(q);changed[field]=value;self.assertNotEqual(old,r.asset_digest(changed,'PolicyR7'))

    def test_asset_digest_is_recorded_with_semantic_checks(self):
        for op in ('policy','edge','manifest'):
            v,pin,_=self.fixture(op);v['payload'][op]['header']['digest']=b'x'*32
            self.assertEqual(r.inspect(c.encode(v),pin)['operation'],op)

    def test_manifest_paths_are_portable_data_not_file_reads(self):
        v,pin,_=self.fixture('manifest');q=v['payload']['manifest'];q['file_digests'][0]['path']='../nonexistent/vector.cbor';D['seal'](v);self.assertFalse(r.inspect(c.encode(v),pin)['production_admission'])
        for path in ('/absolute','C:/absolute','a\\b',''):
            q['file_digests'][0]['path']=path;D['seal'](v)
            with self.assertRaisesRegex(c.CodecError,'SV-85'):r.inspect(c.encode(v),pin)

    def test_manifest_paths_and_cover_sets_are_unique(self):
        v,pin,_=self.fixture('manifest');q=v['payload']['manifest'];q['file_digests']*=2;D['seal'](v)
        with self.assertRaises(c.CodecError):r.inspect(c.encode(v),pin)
        v,pin,_=self.fixture('manifest');q=v['payload']['manifest'];q['covers_profile_digests'].append(q['covers_profile_digests'][0]);D['seal'](v)
        with self.assertRaises(c.CodecError):r.inspect(c.encode(v),pin)

    def test_event_subject_matrix_all_kinds(self):
        v,pin,i=self.fixture('events');events=v['payload']['events'];self.assertEqual({e['event_kind'] for e in events},set(reg.SUBJECTS))
        for e in events:
            r.check_event_subject(e,i);bad=copy.deepcopy(e);bad['subject_ref']['tag']='WRONG'
            with self.assertRaisesRegex(c.CodecError,'SV-120'):r.check_event_subject(bad,i)
        self.assertEqual(r.inspect(c.encode(v),pin)['events'],10)

    def test_scope_subset_direction_and_empty_dimensions(self):
        v,_,i=self.fixture('applicability-test');q=v['payload'];scope=q['profile']['assumption_references'][0]['scope'];declared=q['declared_scope'];self.assertTrue(r.scope_contains(scope,declared,i))
        for field in ('fault_domains','geography'):
            s=copy.deepcopy(scope);s[field]=[];self.assertFalse(r.scope_contains(s,declared,i))
            d=copy.deepcopy(declared);d[field]=[]
            with self.assertRaisesRegex(c.CodecError,'SV-58'):r.scope_contains(scope,d,i)
        d=copy.deepcopy(declared);d['fault_domains']=[b'unknown'];self.assertFalse(r.scope_contains(scope,d,i))

    def test_scope_half_open_version_bounds(self):
        v,_,i=self.fixture('applicability-test');q=v['payload'];scope=copy.deepcopy(q['profile']['assumption_references'][0]['scope']);d=q['declared_scope'];scope['rir_profile_range']={0:[1,0,0],1:[2,0,0]}
        for version,expected in [([0,9,9],False),([1,0,0],True),([1,9,9],True),([2,0,0],False)]:d['rir_version']=version;self.assertEqual(r.scope_contains(scope,d,i),expected)

    def test_window_is_half_open_and_separate_from_scope(self):
        v,pin,_=self.fixture('applicability-test');q=v['payload'];a=next(x for x in q['profile']['assumption_references'] if x['assumption_id']==q['profile']['safety_parameters']['support_capability_bound_ref']);a['validity_window']=[10,20];q['profile']['profile_digest']=p.profile_digest(q['profile'])
        for instant,expected in [(9,False),(10,True),(19,True),(20,False)]:q['evaluation_instant']=instant;out=r.inspect(c.encode(v),pin);self.assertEqual(out['bound_scope_window_ok'],expected);self.assertTrue(out['scope_covered'])

    def test_population_and_invalid_sample_thresholds_are_distinct(self):
        v,pin,_=self.fixture('applicability-test');q=v['payload'];q['n_max']=2;out=r.inspect(c.encode(v),pin);self.assertFalse(out['required_draws_within_limit']);self.assertTrue(out['invalid_sample_limit_ok']);q['n_max']=1;self.assertFalse(r.inspect(c.encode(v),pin)['invalid_sample_limit_ok'])

    def test_authorization_cannot_be_coerced(self):
        for kind in ('PRIMARY','DEGRADED'):
            for auth in (False,True):self.assertEqual(r.authorized_slot(dict(kind=kind),auth),kind=='PRIMARY' or auth)
        for auth in (0,1,'true',None):
            with self.assertRaises(c.CodecError):r.authorized_slot(dict(kind='DEGRADED'),auth)

    def test_mixed_failure_reasons_cannot_enable_degradation(self):
        v,pin,_=self.fixture('applicability-test');q=v['payload'];q['slot'].update(kind='DEGRADED',degraded_from=0,enabling_triggers=['POPULATION_TOO_SMALL']);q['degradation_authorized']=True
        for reasons,expected in [([],False),(['POPULATION_TOO_SMALL'],True),(['POPULATION_TOO_SMALL','CONTRACT_MISMATCH'],False),(['CONTRACT_MISMATCH'],False)]:q['source_failure_reasons']=reasons;self.assertEqual(r.inspect(c.encode(v),pin)['test_slot_enabled'],expected)

    def test_effects_direction_and_informational_exclusion(self):
        v,pin,_=self.fixture('applicability-test');q=v['payload'];q['intent_effects']=[b'network'];self.assertFalse(r.inspect(c.encode(v),pin)['effects_covered'])
        info=q['profile']['assumption_references'][0];self.assertEqual(info['role'],'INFORMATIONAL');info['scope']['fault_domains']=[];q['profile']['profile_digest']=p.profile_digest(q['profile']);self.assertTrue(r.inspect(c.encode(v),pin)['scope_covered'])

    def test_cli_compatibility_flag_and_malformed_input(self):
        v,pin,_=self.fixture('manifest')
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'asset.cbor';f.write_bytes(c.encode(v));cmd=[sys.executable,'-B','-m','tools.verification_profile.validator',str(f),'--registration-assets-cbor','--schema-lock-sha256',pin.hex()]
            a=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True);self.assertEqual(a.returncode,0,a.stderr+a.stdout)
            self.assertEqual(subprocess.run(cmd+['--production'],cwd=ROOT,capture_output=True).returncode,0)
            self.assertTrue(validator.validate_selection_assets_cbor(b'\xff',pin))

    def test_all_outputs_disclose_scope(self):
        for op in ('policy','edge','manifest','profile-refs','profile-lookup','events','applicability-test'):
            v,pin,_=self.fixture(op);out=r.inspect(c.encode(v),pin)
            for field in ('full_schema_valid','full_phase_i_replay','source_authentication','production_admission'):self.assertFalse(out[field])

if __name__=='__main__':unittest.main()
