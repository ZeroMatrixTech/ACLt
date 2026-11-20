# SPDX-License-Identifier: Apache-2.0
"""Frozen exclusion objects and a scoped audit Phase R wire entry.

Schema documents and their trust pin are explicit inputs. Imported engineering
components and log proofs are not authenticated by these structural checks.
"""
import hashlib

from tools.verification_profile import codec as c, registration as r

BASELINE = frozenset('EXC-BASE-'+name for name in (
    'INTENT','LOWERING','RIR-SPEC','RPR-SPEC','COMMON-MODE','INDEPENDENCE',
    'SYBIL','ABSOLUTE','FITNESS','AVAILABILITY','CONFIDENTIALITY','TIMELINESS',
    'LOG-BACKEND','NETWORK-TRANSFER'))


def versioned_ref(value):
    c.fields(value,('id','version','digest'))
    c.need(bool(c.text(value['id'])),'empty external reference ID')
    c.semver(value['version'])
    c.digest_bytes(value['digest'])


class Imports(r.Imports):
    representations=frozenset({'OPAQUE_BSTR','VERSIONED_REF'})

    def __init__(self,lock,documents,pin):
        super().__init__(lock,documents,pin)
        for alias,ref in self.refs.items():
            representation=self.documents[c.encode(c.reference_identity(ref))]['representation']
            if representation=='VERSIONED_REF':
                c.need(alias=='ExternalVersionedObjectRef','unsupported structured import alias')
        c.need('ExternalTypedObject' not in self.refs,'ExternalTypedObject is a wire object, not an opaque import')
        ref=self.refs.get('ExternalVersionedObjectRef')
        c.need(ref is not None and self.documents[c.encode(c.reference_identity(ref))]['representation']=='VERSIONED_REF',
               'structured external reference schema required')

    def check(self,alias,value):
        c.need(alias in self.refs,'unresolved schema import: '+alias)
        representation=self.documents[c.encode(c.reference_identity(self.refs[alias]))]['representation']
        self.payload(value,representation)

    @staticmethod
    def payload(value,representation):
        if representation=='OPAQUE_BSTR':
            c.need(type(value) is bytes,'opaque import must be canonical bstr')
        elif representation=='VERSIONED_REF':
            versioned_ref(value)
        else:
            raise c.CodecError('unsupported schema representation')

    def external_object(self,value):
        c.fields(value,('schema_ref','canonical_bytes','object_digest'))
        self.check('ExternalVersionedObjectRef',value['schema_ref'])
        key=c.encode(c.reference_identity(value['schema_ref']))
        c.need(key in self.documents,'external payload schema not in trusted lock')
        raw=value['canonical_bytes']
        c.need(type(raw) is bytes,'canonical payload bytes')
        payload=c.decode(raw)
        self.payload(payload,self.documents[key]['representation'])
        c.digest_bytes(value['object_digest'])
        c.need(c.digest_consistency(hashlib.sha256(raw).digest()==value['object_digest']),'external payload digest mismatch')


def exclusion_registry_digest(registry):
    header=registry['header']
    return c.domain_hash('ACLt/P0-1/ExcludedClaimsRegistry/1',c.encode(dict(
        schema_version=header['schema_version'],encoding_profile_id=header['encoding_profile_id'],
        entries=registry['entries'])))


def excluded_digest(selection):
    return c.domain_hash('ACLt/P0-1/ExcludedClaims/1',
                         c.encode([selection['registry_ref'],sorted(selection['exclusion_ids'],key=c.encode)]))


def check_excluded(selection,registry,snapshot):
    """Method-independent SV-07/08 checks and both unique digest owners."""
    r.typed(selection,'ExcludedClaims',None)
    r.typed(registry,'ExclusionRegistry',None)
    r.typed(snapshot,'Registry',None)
    r.check_registry(snapshot)
    header=registry['header']
    c.need(header['schema_version']==1,'unknown exclusion registry schema version')
    c.need(c.digest_consistency(header['digest']==exclusion_registry_digest(registry)),'SV-89: exclusion registry digest')
    identity={key:header[key] for key in ('id','version','digest')}
    c.need(c.reference_identity(selection['registry_ref'])==c.reference_identity(identity),'SV-08: exclusion registry identity mismatch')
    c.need(any(row['object_kind']=='EXCLUDED_CLAIMS_REGISTRY' and
               all(row[key]==identity[key] for key in identity if key!='digest') for row in snapshot['entries']),
           'SV-08: exclusion registry is not resolved in snapshot')
    ids=set(selection['exclusion_ids'])
    c.need(BASELINE<=ids,'SV-07: baseline exclusions missing')
    available={row['exclusion_id'] for row in registry['entries']}
    c.need(ids<=available,'SV-08: exclusion ID missing from registry')
    c.need(c.digest_consistency(selection['digest']==excluded_digest(selection)),'SV-72: excluded selection digest')
    return dict(excluded_digest_hex=selection['digest'].hex(),
                exclusion_registry_digest_hex=header['digest'].hex(),
                selected_ids=len(ids),baseline_ids=len(BASELINE))


def inspect_excluded(raw):
    value=c.decode(raw)
    c.fields(value,('selection','registry','registry_snapshot'))
    return check_excluded(value['selection'],value['registry'],value['registry_snapshot'])


def inspect(raw,lock_pin):
    value=c.decode(raw)
    c.fields(value,('envelope','schema_lock','schema_documents','registry_objects'))
    imports=Imports(value['schema_lock'],value['schema_documents'],lock_pin)
    envelope=value['envelope']
    c.fields(envelope,('phase','bundle','object'))
    c.need(envelope['phase']=='R','Phase R envelope')
    profile=envelope['object']
    r.check_profile(profile,imports,'ReferencesProfile')
    bundle=envelope['bundle']
    r.check_bundle(bundle,imports,'ReferencesBundle')
    r.check_supersedes(profile,bundle['registry_snapshot'])
    assets=value['registry_objects']
    c.need(type(assets) is list and len(assets)==1,'one explicit exclusion registry asset required')
    asset=assets[0]
    c.fields(asset,('object_kind','object'))
    c.need(asset['object_kind']=='EXCLUDED_CLAIMS_REGISTRY','unsupported registry asset kind')
    result=check_excluded(profile['excluded_claims'],asset['object'],bundle['registry_snapshot'])
    result.update(profile_digest_hex=profile['profile_digest'].hex(),
                  registry_digest_hex=bundle['registry_snapshot']['header']['digest'].hex(),
                  frontier_digest_hex=bundle['event_frontier_snapshot']['header']['digest'].hex(),
                  schema_lock_sha256=c.digest_record_hex(lock_pin),full_schema_valid=False,source_authentication=False)
    return result
