# SPDX-License-Identifier: Apache-2.0
"""Frozen matrix coverage, explicit wire gaps and scoped audit regressions."""
import copy,json,runpy,subprocess,sys,tempfile,unittest
from pathlib import Path
from tools.verification_profile import codec as c,profile as p,method_rules as r
from tools.verification_profile.validator import validate_method_matrix_cbor
ROOT=Path(__file__).resolve().parents[2]
DRIVER=runpy.run_path(str(ROOT/'scripts/check-method-matrices.py'))


class MethodMatrixTests(unittest.TestCase):
    def test_frozen_vectors(self):
        rows=json.loads((ROOT/'tests/verification_profile/codec/method-matrix-vectors.json').read_text())['vectors']
        self.assertEqual(len(rows),len({x['id'] for x in rows}))
        for row in rows:
            with self.subTest(id=row['id']):
                args=(row['mode'],bytes.fromhex(row['cbor_hex']),bytes.fromhex(row.get('lock_pin','')))
                if row['valid']:self.assertEqual(DRIVER['evaluate'](*args),row['expected'])
                else:
                    with self.assertRaises(c.CodecError):DRIVER['evaluate'](*args)

    def test_event_sets_match_frozen_spec_table(self):
        spec=(ROOT/'docs/03-protocol/verification-profile-schema.md').read_text()
        table=spec.split('#### 方法 × 事件适用矩阵（冻结）',1)[1].split('三条推论：',1)[0]
        for method_index,method in enumerate(p.METHODS):
            for cert in ((False,True) if method=='DIRECT_VERIFIED' else (False,)):
                expected=set()
                for line in table.splitlines():
                    if not line.startswith('| `'):continue
                    fields=[x.strip() for x in line.strip('|').split('|')]
                    if '✓' not in fields[method_index+1]:continue
                    import re
                    for event in re.findall(r'`([A-Z_]+)`',fields[0]):
                        if event=='CERTIFICATE_ABSENT' and not cert:continue
                        expected.add(event)
                value,pin=DRIVER['fixture'](method,certificate=cert)
                self.assertEqual(set(r.expected_events(value['profile'])),expected)
                r.inspect(c.encode(value),pin)

    def test_condition_sets_match_spec_and_soundness(self):
        spec=(ROOT/'docs/03-protocol/verification-profile-schema.md').read_text()
        table=spec.split('#### 11.3.3 方法 × DecisionCondition',1)[1].split('三条说明：',1)[0]
        for i,method in enumerate(p.METHODS):
            for sound in (('SOUND','SOUND_AND_COMPLETE') if method=='DIRECT_VERIFIED' else ('SOUND',)):
                expected=[]
                for line in table.splitlines():
                    if not line.startswith('| `'):continue
                    fields=[x.strip() for x in line.strip('|').split('|')];condition=fields[0].strip('`')
                    if '✓' not in fields[i+1]:continue
                    if method=='DIRECT_VERIFIED' and condition.startswith('REJECT_'):
                        if condition!=('REJECT_COMPLETE' if sound=='SOUND_AND_COMPLETE' else 'REJECT_SOUND_ONLY'):continue
                    expected.append(condition)
                value,pin=DRIVER['fixture'](method,soundness=sound)
                self.assertEqual(r.expected_conditions(value['profile']),expected)
                self.assertIn('EXECUTION_FAILED',expected)
                value['profile']['decision_mapping']['rules'].remove('EXECUTION_FAILED');DRIVER['seal'](value)
                with self.assertRaisesRegex(c.CodecError,'SV-51:'):r.inspect(c.encode(value),pin)

    def test_conditional_certificate_event_and_block_matrix(self):
        value,pin=DRIVER['fixture']('DIRECT_VERIFIED')
        self.assertNotIn('CERTIFICATE_ABSENT',r.expected_events(value['profile']))
        value['profile']['method_parameters']['certificate_required']=True;DRIVER['seal'](value)
        with self.assertRaisesRegex(c.CodecError,'SV-18:'):r.inspect(c.encode(value),pin)
        DRIVER['fill_failure'](value['profile']);DRIVER['seal'](value);r.inspect(c.encode(value),pin)
        for method in p.METHODS:
            value,pin=DRIVER['fixture'](method)
            for key in ('safety_parameters','liveness_parameters'):
                changed=copy.deepcopy(value)
                if method=='REEXEC_BOUNDED':changed['profile'].pop(key)
                else:changed['profile'][key]={}
                DRIVER['seal'](changed)
                with self.assertRaisesRegex(c.CodecError,'SV-31:'):r.inspect(c.encode(changed),pin)

    def test_failure_mapping_variants_do_not_mix_outcome_classes(self):
        for method in p.METHODS:
            value,pin=DRIVER['fixture'](method);mapping=value['profile']['failure_mapping']
            if method=='REEXEC_BOUNDED':
                mapping.pop('max_invalid_samples');DRIVER['seal'](value)
                with self.assertRaisesRegex(c.CodecError,'SV-29R:'):r.inspect(c.encode(value),pin)
            else:
                mapping['entries'][0]['value']['outcome']='INVALID_SAMPLE';DRIVER['seal'](value)
                with self.assertRaisesRegex(c.CodecError,'SV-19:'):r.inspect(c.encode(value),pin)

    def test_direct_declarations_and_q_source(self):
        for key,bad in [('determinism','NONDETERMINISTIC'),('effects',[b'network'])]:
            value,pin=DRIVER['fixture']('DIRECT_VERIFIED');value['profile']['method_parameters'][key]=bad;DRIVER['seal'](value)
            with self.assertRaisesRegex(c.CodecError,'SV-16:'):r.inspect(c.encode(value),pin)
        value,pin=DRIVER['fixture']('REEXEC_BOUNDED');value['profile']['liveness_parameters']['q_source']='EXTRAPOLATED';DRIVER['seal'](value)
        with self.assertRaisesRegex(c.CodecError,'SV-13:'):r.inspect(c.encode(value),pin)

    def test_method_parameter_variant_mismatch_is_rejected_by_discriminant(self):
        for method in p.METHODS:
            for other in p.METHODS:
                if other==method:continue
                value,pin=DRIVER['fixture'](method)
                foreign=DRIVER['fixture'](other)[0]['profile']['method_parameters']
                if method=='DIRECT_VERIFIED':
                    masked=copy.deepcopy(value);masked['profile']['method_parameters']=copy.deepcopy(foreign);DRIVER['seal'](masked)
                    with self.assertRaisesRegex(c.CodecError,'SV-16:'):r.inspect(c.encode(masked),pin)
                    foreign['determinism']='DETERMINISTIC';foreign['effects']=[]
                value['profile']['method_parameters']=copy.deepcopy(foreign);DRIVER['seal'](value)
                with self.assertRaises(c.CodecError) as caught:r.inspect(c.encode(value),pin)
                self.assertIn('unknown/missing field',str(caught.exception))
                self.assertNotIn('SV-16:',str(caught.exception))

    def test_native_bool_uint_and_validator_reference_bounds(self):
        for key,bad in [('certificate_required',1),('verifier_replication_min',True),('validator_ref','acl.val.stats@18446744073709551616.0.0')]:
            value,pin=DRIVER['fixture']('DIRECT_VERIFIED');value['profile']['method_parameters'][key]=bad;DRIVER['seal'](value)
            with self.assertRaises(c.CodecError):r.inspect(c.encode(value),pin)
        value,pin=DRIVER['fixture']('DIRECT_VERIFIED');value['profile']['method_parameters']['validator_ref']='acl.val.stats@18446744073709551615.0.0';DRIVER['seal'](value)
        r.inspect(c.encode(value),pin)

    def test_unfrozen_signature_semantics_are_not_claimed(self):
        value,pin=DRIVER['fixture']('DIRECT_VERIFIED')
        value['profile']['method_parameters']['predicate_signature']=b'opaque changed signature';DRIVER['seal'](value)
        output=r.inspect(c.encode(value),pin)
        self.assertFalse(output['full_schema_valid']);self.assertFalse(output['source_authentication'])
        value['profile']['method_parameters']['predicate_signature']={};DRIVER['seal'](value)
        with self.assertRaises(c.CodecError):r.inspect(c.encode(value),pin)

    def test_reachable_terminals_do_not_invent_non_audit_wire_fields(self):
        for method in p.METHODS:
            value,pin=DRIVER['fixture'](method);out=r.inspect(c.encode(value),pin)
            self.assertEqual(out['reachable_terminals'],value['reachable_terminals'])
            if method!='REEXEC_AUDIT_ONLY':
                self.assertNotIn('reachable_terminals',value['profile']['method_parameters'])
                value['profile']['method_parameters']['reachable_terminals']=out['reachable_terminals'];DRIVER['seal'](value)
                with self.assertRaises(c.CodecError):r.inspect(c.encode(value),pin)
            else:self.assertNotIn('TRUSTED',out['reachable_terminals'])

    def test_projection_outcome_rows_and_invalidation_priority(self):
        base=dict(aggregate_exhausted=False)
        for sound,expected in [('SOUND','REJECT_SOUND_ONLY'),('SOUND_AND_COMPLETE','REJECT_COMPLETE')]:
            self.assertEqual(r.project(base|dict(verification_method='DIRECT_VERIFIED',outcome='REJECT',soundness_class=sound))['condition'],expected)
        for method,outcome in [('PROOF_VERIFIED','INCONCLUSIVE'),('REEXEC_AUDIT_ONLY','DISCORDANT')]:
            self.assertEqual(r.project(base|dict(verification_method=method,outcome=outcome)),dict(condition_present=False))
            self.assertEqual(r.project(base|dict(verification_method=method,outcome=outcome,aggregate_exhausted=True))['condition'],'EVIDENCE_EXHAUSTED')
        value=base|dict(verification_method='REEXEC_BOUNDED',outcome='SUPPORT',threshold_met=True,null_bound_exactly_exceeded=False)
        self.assertEqual(r.project(value)['condition'],'ACCEPT')
        value['outcome']='VERIFICATION_INVALIDATING';self.assertEqual(r.project(value)['condition'],'VERIFICATION_INVALIDATING')
        for method in p.METHODS:
            value=base|dict(verification_method=method,outcome=r.OUTCOMES[method][0],projection={})
            with self.assertRaises(c.CodecError):r.project(value)

    def test_audit_integration_and_no_mutation(self):
        value,pin=DRIVER['audit_fixture']();before=copy.deepcopy(value)
        out=r.inspect_audit(c.encode(value),pin);self.assertEqual(value,before);self.assertEqual(out['verification_method'],'REEXEC_AUDIT_ONLY')
        with self.assertRaises(c.CodecError):r.inspect_audit(c.encode(value),b'x'*32)
        self.assertEqual(value,before)

    def test_cli_modes_and_production_are_fail_closed(self):
        for audit in (False,True):
            value,pin=DRIVER['audit_fixture']() if audit else DRIVER['fixture']()
            self.assertEqual(validate_method_matrix_cbor(c.encode(value),pin,audit=audit),[])
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'matrix.cbor';path.write_bytes(c.encode(value));flag='--registration-r5-cbor' if audit else '--method-matrix-cbor'
                cmd=[sys.executable,'-B','-m','tools.verification_profile.validator',str(path),flag,'--schema-lock-sha256',pin.hex()]
                output=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True);self.assertEqual(output.returncode,0,output.stderr)
                output=subprocess.run(cmd+['--production'],cwd=ROOT,capture_output=True,text=True);self.assertEqual(output.returncode,1);self.assertEqual(json.loads(output.stdout)[0]['sv_id'],'COVERAGE')
                output=subprocess.run(cmd+['--registration-r4-cbor'],cwd=ROOT,capture_output=True,text=True);self.assertEqual(output.returncode,2)
                for raw in (b'\xa0',b'\x80',b'\x01',b'\xf6'):
                    path.write_bytes(raw);output=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True);self.assertEqual(output.returncode,1);self.assertNotIn('Traceback',output.stderr)

    def test_old_deployments_carry_transitive_rust_assets(self):
        for name in ('fm-s1a-dualhost.py','fm-s1b-dualhost.py','rir-independent-dualhost.py'):
            files=runpy.run_path(str(ROOT/'scripts'/name))['FILES']
            for name in ('method_types.json','method_rules.rs'):self.assertIn('tools/verification_profile/rust/'+name,files)

if __name__=='__main__':unittest.main()
