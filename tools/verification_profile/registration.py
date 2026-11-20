# SPDX-License-Identifier: Apache-2.0
"""Audit nested types, pinned opaque imports and explicit Phase R context.

The import lock pin is supplied by the caller, outside the encoded input.
Proof bytes are retained and typed here. Backend finality/authenticity is separate.
"""
import hashlib
import json
import re
from pathlib import Path
from tools.verification_profile import codec as c, profile as p

TYPES = json.loads((Path(__file__).parent/'rust/audit_types.json').read_text())
FIXED_IMPORTS = {name:'acl.schema.'+identifier+'@1' for name,identifier in [
    ('EvidenceRef','evidence-ref'),('EvidenceIssuerRef','evidence-issuer-ref'),
    ('ChannelRef','channel-ref'),('EventRef','event-ref'),('DatasetRef','dataset-ref'),
    ('ExternalVersionedObjectRef','external-versioned-object-ref'),
    ('EnvironmentClassID','environment-class-id'),('FaultDomainID','fault-domain-id'),('RegionID','region-id'),
]}
PREFIXES = dict(VERIFICATION_PROFILE='acl.vp.',CLAIM_TEMPLATE='acl.ct.',
                PROFILE_SELECTION_POLICY='acl.vps.',WEAKENING_EDGE='acl.we.',
                EXCLUDED_CLAIMS_REGISTRY='acl.ecr.',MAINNET_ASSURANCE_PROFILE='acl.map.',
                CLAIM_SPEC='acl.cs.',ASSUMPTION_SNAPSHOT='acl.ass.',CLUSTER_MAPPING='acl.cmap.',SCHEMA='acl.schema.',BINDING_FUNCTION='acl.bind.',MANIFEST='acl.cm.',PROFILE='acl.vp.',REGISTRY_SNAPSHOT='acl.rs.',FRONTIER='acl.efs.',
                CREATION_CONTEXT='acl.cctx.',PHASE_I_RECORD='acl.pir.',TASK='acl.tt.',PREDICATE='acl.pred.',VALIDATOR='acl.val.',EQUIVALENCE='acl.eq.',ENCODING='acl.enc.')
NAME = '[a-z][a-z0-9-]{0,62}'
ULID = '[0-9A-HJKMNP-TV-Z]{26}'


def identifier(value, kind):
    value = c.text(value)
    if kind == 'ASSUMPTION':
        pattern = r'ACL-ASM-[0-9]{4}'
    elif kind == 'EXCLUSION':
        pattern = r'EXC-[A-Z][A-Z0-9]*-[A-Z0-9-]+'
    else:
        suffix = NAME
        if kind in ('PROFILE','VERIFICATION_PROFILE'):
            suffix += r'\.'+NAME
        elif kind in ('REGISTRY_SNAPSHOT','FRONTIER','CREATION_CONTEXT','PHASE_I_RECORD','ASSUMPTION_SNAPSHOT','CLUSTER_MAPPING'):
            suffix = ULID
        elif kind in ('PREDICATE','VALIDATOR','BINDING_FUNCTION'):
            suffix += r'@(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)'
        elif kind in ('EQUIVALENCE','ENCODING','SCHEMA'):
            suffix += r'@(0|[1-9][0-9]*)'
        pattern = re.escape(PREFIXES[kind])+suffix
    c.need(re.fullmatch(pattern,value) is not None,'SV-80: identifier')
    if kind in ('PREDICATE','VALIDATOR','BINDING_FUNCTION'):
        parts=value.rsplit('@',1)[1].split('.')
        c.need(all(len(part)<=20 for part in parts),'reference SemVer overflow')
        c.semver([int(part) for part in parts])
    if kind=='SCHEMA':
        suffix=value.rsplit('@',1)[1];c.need(len(suffix)<=20 and int(suffix)<=2**64-1,'schema major overflow')
    return value


class Imports:
    representations = frozenset({'OPAQUE_BSTR'})

    def __init__(self, lock, documents, pin):
        if pin is not None:
            c.digest_bytes(pin)
        c.need(c.digest_consistency(hashlib.sha256(c.encode(lock)).digest()==pin),'schema lock pin mismatch')
        c.fields(lock, ('version','entries'))
        c.need(type(lock['version']) is int and lock['version']==1,'schema lock version')
        c.need(type(lock['entries']) is list and type(documents) is list,'schema assets')
        self.refs = {}
        self.documents = {}
        for row in documents:
            c.fields(row, ('ref','content'))
            ref = row['ref']
            c.fields(ref, ('id','version','digest'))
            c.text(ref['id'])
            c.semver(ref['version'])
            c.need(ref['version']==[1,0,0],'unsupported schema version')
            c.digest_bytes(ref['digest'])
            c.need(type(row['content']) is bytes and c.digest_consistency(hashlib.sha256(row['content']).digest() == ref['digest']),
                   'schema document digest')
            key = c.encode(c.reference_identity(ref))
            c.need(key not in self.documents,'duplicate schema document')
            document = c.decode(row['content'])
            c.fields(document, ('alias','id','version','representation'))
            c.need(document['id']==ref['id'] and document['version']==ref['version'] and
                   document['representation'] in self.representations,'unsupported import schema')
            self.documents[key] = document
        aliases = []
        for row in lock['entries']:
            c.fields(row, ('alias','ref'))
            alias,ref = row['alias'],row['ref']
            c.text(alias)
            c.need(alias not in self.refs and c.encode(c.reference_identity(ref)) in self.documents,'duplicate or unresolved import')
            document = self.documents[c.encode(c.reference_identity(ref))]
            c.need(document['alias']==alias,'schema alias binding')
            c.need(re.fullmatch(r'acl\.schema\.'+NAME+r'@(0|[1-9][0-9]*)',ref['id']) is not None,
                   'schema import ID')
            c.need(ref['id'].endswith('@1'),'unsupported schema major')
            if alias in FIXED_IMPORTS:
                c.need(ref['id']==FIXED_IMPORTS[alias],'normative schema import ID')
            self.refs[alias] = ref
            aliases.append(c.encode(alias))
        c.need(aliases==sorted(set(aliases)),'schema lock order or duplicate')
        c.need(len(self.refs)==len(self.documents),'unused or extra schema document')

    def check(self, alias, value):
        c.need(alias in self.refs,'unresolved schema import: '+alias)
        c.need(type(value) is bytes,'opaque import must be canonical bstr')


def typed(value, schema, imports, catalog=None):
    catalog=TYPES if catalog is None else catalog
    if isinstance(schema,str):
        if schema in catalog:
            return typed(value,catalog[schema],imports,catalog)
        if schema == 'native':
            c.encode(value)
        elif schema == 'text':
            c.text(value)
        elif schema == 'bool':
            c.need(type(value) is bool,'bool')
        elif schema == 'uint':
            c.uint(value)
        elif schema == 'int':
            c.need(type(value) is int and -(2**63)<=value<2**63,'int64')
        elif schema == 'digest':
            c.digest_bytes(value)
        elif schema == 'semver':
            c.semver(value)
        elif schema == 'rational':
            c.project(value,c.SCHEMAS['rational'])
        elif schema == 'version-range':
            c.project(value,c.SCHEMAS['version-range'])
        elif schema == 'external-object':
            imports.external_object(value)
        elif schema == 'wire-time-range':
            c.need(type(value) is list and len(value)==2,'wire TimeRange must be [start,end]')
            typed(value[0],'int',imports,catalog)
            typed(value[1],'int',imports,catalog)
            c.need(value[0]<value[1],'empty validity range')
        elif schema == 'time-range':
            c.fields(value,('start','end'))
            typed(value['start'],'int',imports,catalog)
            typed(value['end'],'int',imports,catalog)
            c.need(value['start']<value['end'],'empty validity range')
        else:
            raise c.CodecError('unknown type')
    elif 'fields' in schema:
        c.fields(value,schema['fields'],schema['optional'])
        for key,child in (schema['fields']|schema['optional']).items():
            if key in value:
                typed(value[key],child,imports,catalog)
    elif 'enum' in schema:
        c.need(type(value) is str and value in schema['enum'],'unknown ENUM')
    elif 'identifier' in schema:
        identifier(value,schema['identifier'])
    elif 'import_' in schema:
        imports.check(schema['import_'],value)
    else:
        c.need(type(value) is list,'array')
        child = schema.get('array',schema.get('set'))
        for item in value:
            typed(item,child,imports,catalog)
        if 'set' in schema:
            encoded = [c.encode(item) for item in value]
            c.need(encoded==sorted(set(encoded)),'set order or duplicate')


def registry_digest(registry):
    header = registry['header']
    return c.domain_hash('ACLt/P0-1/RegistrySnapshot/1',c.encode(dict(
        schema_version=header['schema_version'],encoding_profile_id=header['encoding_profile_id'],
        entries=registry['entries'])))


def check_registry(registry):
    c.need(registry['header']['schema_version']==1,'registry schema version')
    keys=[]
    for row in registry['entries']:
        identifier(row['id'],row['object_kind'])
        keys.append(c.encode([row['object_kind'],row['id'],row['version']]))
    c.need(keys==sorted(set(keys)),'SV-79: registry order or duplicate identity')
    c.need(c.digest_consistency(registry['header']['digest']==registry_digest(registry)),'SV-75b: registry digest')


def frontier_digest(frontier):
    header = frontier['header']
    return c.domain_hash('ACLt/P0-1/EventFrontierSnapshot/1',c.encode(dict(
        schema_version=header['schema_version'],encoding_profile_id=header['encoding_profile_id'],id=header['id'],
        frontier_event_ref=frontier['frontier_event_ref'],event_records=frontier['event_records'],
        log_binding=frontier['log_binding'])))


SUBJECTS = dict(PHASE_I_VALIDATION='PHASE_I_RECORD',PHASE_F_VALIDATION='PHASE_F_CALL',
                CLUSTER_MAPPING_FIXED='CLUSTER_MAPPING',SNAPSHOT_FROZEN='ELIGIBILITY_SNAPSHOT',
                FUNDING_EXHAUSTED='RECEIPT',DEADLINE_REACHED='RECEIPT',EXECUTION_EXHAUSTED='RECEIPT',
                VERIFICATION_STARTED='RECEIPT',VERIFICATION_TERMINAL_COMMITTED='RECEIPT',OTHER='OPAQUE_IMPORTED')


def check_frontier(frontier, imports):
    version=frontier['header']['schema_version']
    c.need(version in (1,2),'frontier schema version')
    c.need(c.digest_consistency(frontier['header']['digest']==frontier_digest(frontier)),'SV-108: frontier digest')
    events={}
    ordered=[]
    for row in frontier['event_records']:
        key=c.encode(row['event_ref'])
        c.need(key not in events,'SV-109: duplicate event')
        ordered.append(key)
        kind=row['event_kind']
        c.need(kind in SUBJECTS and (version==2 or kind not in ('VERIFICATION_STARTED','VERIFICATION_TERMINAL_COMMITTED')),
               'SV-109: event kind/version')
        subject=row['subject_ref']
        c.need(subject['tag']==SUBJECTS[kind],'SV-109: event subject tag')
        c.need(('schema_ref' in subject)==(kind=='OTHER'),'SV-109: event subject fields')
        if subject['tag'] in ('ELIGIBILITY_SNAPSHOT','OPAQUE_IMPORTED'):
            c.text(subject['id'])
        elif subject['tag']=='RECEIPT':
            c.digest_bytes(subject['id'])
        # Remaining subject IDs use their declared textual/runtime aliases.
        elif subject['tag']=='PHASE_I_RECORD':
            c.need(re.fullmatch(r'acl\.pir\.'+ULID,c.text(subject['id'])) is not None,'phase record ID')
        elif subject['tag']=='PHASE_F_CALL':
            imports.check('EventRef',subject['id'])
        elif subject['tag']=='CLUSTER_MAPPING':
            c.need(re.fullmatch(r'acl\.cmap\.'+ULID,c.text(subject['id'])) is not None,'cluster mapping ID')
        events[key]=row
    c.need(ordered==sorted(ordered),'SV-109: event order')
    root=c.encode(frontier['frontier_event_ref'])
    c.need(root in events,'SV-109: missing frontier')
    # Kahn's algorithm establishes closure and acyclicity without recursion.
    children={key:[] for key in events}
    degrees={}
    for key,row in events.items():
        parents=[c.encode(parent) for parent in row['parent_refs']]
        c.need(all(parent in events for parent in parents),'SV-109: unresolved parent')
        degrees[key]=len(parents)
        for parent in parents:children[parent].append(key)
    ready=[key for key,count in degrees.items() if count==0]
    visited=0
    while ready:
        key=ready.pop()
        visited+=1
        for child in children[key]:
            degrees[child]-=1
            if degrees[child]==0:ready.append(child)
    c.need(visited==len(events),'SV-109: causal cycle')
    c.need(len(frontier['log_binding']['event_inclusion_proofs'])==len(events),'proof/event cardinality')


def check_bundle(bundle, imports, kind='Bundle'):
    typed(bundle,kind,imports)
    registry=bundle['registry_snapshot']
    check_registry(registry)
    ref=bundle['context']['registry_snapshot_ref']
    header=registry['header']
    c.need(c.encode(c.reference_identity(ref))==c.encode({key:header[key] for key in ('id','version')}),
           'SV-75a: registry context binding')
    frontier=bundle['event_frontier_snapshot']
    check_frontier(frontier,imports)
    c.need(c.encode(c.reference_identity(bundle['context']['event_frontier_ref']))==
           c.encode({key:frontier['header'][key] for key in ('id',)}),
           'SV-109: frontier context binding')


def inspect(raw, lock_pin):
    value=c.decode(raw)
    c.fields(value,('envelope','schema_lock','schema_documents'))
    imports=Imports(value['schema_lock'],value['schema_documents'],lock_pin)
    envelope=value['envelope']
    c.fields(envelope,('phase','bundle','object'))
    c.need(envelope['phase']=='R','Phase R envelope')
    profile=envelope['object']
    check_profile(profile,imports)
    check_bundle(envelope['bundle'],imports)
    check_supersedes(profile,envelope['bundle']['registry_snapshot'])
    return dict(profile_digest_hex=profile['profile_digest'].hex(),
                registry_digest_hex=envelope['bundle']['registry_snapshot']['header']['digest'].hex(),
                frontier_digest_hex=envelope['bundle']['event_frontier_snapshot']['header']['digest'].hex(),
                schema_lock_sha256=c.digest_record_hex(lock_pin),full_schema_valid=False,source_authentication=False)


def check_profile(profile, imports, kind='Profile'):
    typed(profile,kind,imports)
    p.verify_digest(profile)
    p.audit_fields(profile)
    ids=[row['assumption_id'] for row in profile['assumption_references']]
    c.need(len(ids)==len(set(ids)),'SV-76: duplicate assumption')
    for row in profile['assumption_references']:
        if row['role']=='SAFETY_CRITICAL':
            c.need(row['revocation_mapping']==dict(before_verification='BLOCK_ADMISSION',
                during_verification='VERIFICATION_INVALIDATING',after_terminal='QUALIFY_REVOKED'),'SV-37: safety revocation')


def check_supersedes(profile, registry):
    if 'supersedes' in profile:
        ref=profile['supersedes']
        c.need(any(row['object_kind']=='VERIFICATION_PROFILE' and
            all(row[key]==ref[key] for key in ('id','version'))
            for row in registry['entries']),'SV-84: unresolved supersedes')
