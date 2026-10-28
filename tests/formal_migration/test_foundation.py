# SPDX-License-Identifier: Apache-2.0
import copy
import hashlib
import json
from pathlib import Path
import unittest
from tools.formal_migration import foundation as f
from tools.verification_profile import codec as c
ROOT=Path(__file__).resolve().parents[2]
ROWS=json.loads((ROOT/'tests/formal_migration/vectors.json').read_text())['vectors']
def native(label):return c.decode(bytes.fromhex(next(r['cbor_hex'] for r in ROWS if r['id']==label)))
class FoundationTests(unittest.TestCase):
    def test_frozen_vectors_and_acceptance_distribution(self):
        self.assertGreater(sum(r['valid'] for r in ROWS),10)
        self.assertGreater(sum(not r['valid'] for r in ROWS),50)
        for row in ROWS:
            with self.subTest(row=row['id']):
                raw=bytes.fromhex(row['cbor_hex'])
                if row['valid']:self.assertEqual(f.inspect(row['kind'],raw),row['expected'])
                else:self.assertRaises(c.CodecError,f.inspect,row['kind'],raw)
    def test_schema_views_are_typed_and_reversible(self):
        for row in ROWS:
            if row['valid'] and row['kind']!='fm-verify':self.assertEqual(f.from_view_json(row['kind'],json.dumps(row['expected']['schema_view'])).hex(),row['cbor_hex'])
        view=next(r['expected']['schema_view'] for r in ROWS if r['id']=='typed-boundaries')
        for edit in [lambda x:x.update(count=1),lambda x:x.update(count='01'),lambda x:x.update(ratio=['0','2']),lambda x:x.update(members=['z','a']),lambda x:x.update(version=['1','0']),lambda x:x.update(operation='ISSUER')]:
            v=copy.deepcopy(view);edit(v);self.assertRaises(c.CodecError,f.from_view_json,'fm-value',json.dumps(v))
    def test_input_objects_never_mutate_on_success_or_rejection(self):
        for label in ['requester-valid','replay-wrong-nonce','wrong-signing-key']:
            req=native(label);before=copy.deepcopy(req)
            try:f.verify(req)
            except c.CodecError:pass
            self.assertEqual(req,before)
    def test_verification_is_idempotent_but_not_replay_authority(self):
        req=native('requester-valid');self.assertEqual(f.verify(req),f.verify(req));req['expected']['nonce']=b'z'*32;self.assertRaises(c.CodecError,f.verify,req)
    def test_principal_digest_binds_role_network_deployment_and_validity(self):
        rec=native('principal');digest=f.principal_digest(rec)
        for k,v in [('role','PROVIDER'),('network_id',b'x'*32),('deployment_id',b'x'*32),('valid_until',20000)]:self.assertNotEqual(digest,f.principal_digest(dict(rec,**{k:v})))
    def test_signature_input_uses_exact_domain_and_all_unsigned_fields(self):
        u=native('signing-input');prefix=bytes([len(f.SIGN_TAG)])+f.SIGN_TAG.encode();self.assertEqual(f.signing_input(u),prefix+c.encode(u));self.assertNotEqual(hashlib.sha256(c.encode(u)).digest(),hashlib.sha256(f.signing_input(u)).digest())
    def test_closed_types_import_and_contract(self):
        contract=json.loads((ROOT/'schemas/formal-migration/foundation.json').read_text());self.assertEqual(contract['types'],f.SCHEMAS);self.assertEqual(contract['enums'],{k:list(v) for k,v in f.ENUMS.items()});self.assertEqual(contract['suite']['id'],f.SUITE);self.assertEqual(hashlib.sha256((ROOT/'schemas/formal-migration/value.schema.txt').read_bytes()).digest(),f.IMPORT_DIGEST);self.assertEqual(contract['import']['digest'],f.IMPORT_DIGEST.hex());self.assertEqual(contract['domain_tags'],dict(principal=f.PRINCIPAL_TAG,key_identity=f.IDENTITY_TAG,signature_input=f.SIGN_TAG));self.assertRaises(c.CodecError,f.inspect,'official-principal',b'\0')
    def test_resource_limits(self):
        for raw in [b'x'*(c.MAX_BYTES+1),b'\x81'*50+b'\0',bytes.fromhex('9bffffffffffffffff')]:self.assertRaises(c.CodecError,f.inspect,'fm-role',raw)
        req=native('requester-valid');req['envelope']['payload']=b'x'*4097;self.assertRaises(c.CodecError,f.verify,req)
    def test_json_duplicates_constants_unicode_and_size_fail_closed(self):
        for source in ['{"a":"1","a":"2"}','NaN','null','"\\ud800"','"e\\u0301"','"'+'x'*(c.MAX_BYTES*4)+'"','\ud800']:self.assertRaises(c.CodecError,f.from_view_json,'fm-role',source)
    def test_no_issuer_principal_or_silent_lifecycle(self):
        rec=native('principal')
        for field,option in [('role','ISSUER'),('status','REVOKED'),('status','UNKNOWN'),('suite','production')]:self.assertRaises(c.CodecError,f.principal,dict(rec,**{field:option}))
        req=native('requester-valid');req['record']['valid_until']=req['now'];self.assertRaises(c.CodecError,f.verify,req)
if __name__=='__main__':unittest.main()
