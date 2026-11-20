// SPDX-License-Identifier: Apache-2.0
// Independent nested-type/import and Phase R bundle checks.
use super::*;
use std::collections::{BTreeMap, BTreeSet};

fn object(rows: &V) -> R<&[(V, V)]> {
    match rows {
        V::M(rows) => Ok(rows),
        _ => Err("expected object".into()),
    }
}

fn same(a: &V, b: &V) -> R<bool> {
    Ok(encode(a)? == encode(b)?)
}

fn name(value: &str) -> bool {
    !value.is_empty() && value.len() <= 63 && value.as_bytes()[0].is_ascii_lowercase()
        && value.bytes().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == b'-')
}

fn number(value: &str) -> bool {
    !value.is_empty() && (value == "0" || !value.starts_with('0'))
        && value.bytes().all(|c| c.is_ascii_digit())
}

fn ulid(value: &str) -> bool {
    value.len() == 26 && value.bytes().all(|c| b"0123456789ABCDEFGHJKMNPQRSTVWXYZ".contains(&c))
}

fn identifier(value: &V, kind: &str) -> R<()> {
    let value = txt(value)?;
    if kind == "ASSUMPTION" {
        let tail = value.strip_prefix("ACL-ASM-").ok_or("assumption ID")?;
        return need(tail.len() == 4 && tail.bytes().all(|c| c.is_ascii_digit()), "assumption ID");
    }
    if kind == "EXCLUSION" {
        let tail = value.strip_prefix("EXC-").ok_or("exclusion ID")?;
        let (category, item) = tail.split_once('-').ok_or("exclusion ID")?;
        return need(!category.is_empty() && category.as_bytes()[0].is_ascii_uppercase()
            && category.bytes().all(|c| c.is_ascii_uppercase() || c.is_ascii_digit())
            && !item.is_empty() && item.bytes().all(|c| c.is_ascii_uppercase() || c.is_ascii_digit() || c == b'-'),
            "exclusion ID");
    }
    let prefix = match kind {
        "PROFILE" | "VERIFICATION_PROFILE" => "acl.vp.",
        "CLAIM_TEMPLATE" => "acl.ct.",
        "PROFILE_SELECTION_POLICY" => "acl.vps.",
        "MANIFEST" => "acl.cm.",
        "CLAIM_SPEC" => "acl.cs.",
        "ASSUMPTION_SNAPSHOT" => "acl.ass.",
        "CLUSTER_MAPPING" => "acl.cmap.",
        "SCHEMA" => "acl.schema.",
        "BINDING_FUNCTION" => "acl.bind.",
        "WEAKENING_EDGE" => "acl.we.",
        "EXCLUDED_CLAIMS_REGISTRY" => "acl.ecr.",
        "MAINNET_ASSURANCE_PROFILE" => "acl.map.",
        "REGISTRY_SNAPSHOT" => "acl.rs.",
        "FRONTIER" => "acl.efs.",
        "CREATION_CONTEXT" => "acl.cctx.",
        "PHASE_I_RECORD" => "acl.pir.",
        "TASK" => "acl.tt.",
        "PREDICATE" => "acl.pred.",
        "VALIDATOR" => "acl.val.",
        "EQUIVALENCE" => "acl.eq.",
        "ENCODING" => "acl.enc.",
        _ => return Err("unknown identifier kind".into()),
    };
    let tail = value.strip_prefix(prefix).ok_or("identifier prefix")?;
    let valid = match kind {
        "PROFILE" | "VERIFICATION_PROFILE" => tail.split_once('.')
            .is_some_and(|(family, slug)| name(family) && name(slug)),
        "REGISTRY_SNAPSHOT" | "FRONTIER" | "CREATION_CONTEXT" | "PHASE_I_RECORD" | "ASSUMPTION_SNAPSHOT" | "CLUSTER_MAPPING" => ulid(tail),
        "PREDICATE" | "VALIDATOR" | "BINDING_FUNCTION" => tail.split_once('@').is_some_and(|(id, version)| {
            let parts: Vec<_> = version.split('.').collect();
            name(id) && parts.len() == 3 && parts.iter().all(|part| number(part) && part.parse::<u64>().is_ok())
        }),
        "SCHEMA" => tail.split_once('@').is_some_and(|(id,version)| name(id)&&number(version)&&version.parse::<u64>().is_ok()),
        "EQUIVALENCE" | "ENCODING" => tail.split_once('@')
            .is_some_and(|(id, version)| name(id) && number(version)),
        _ => name(tail),
    };
    need(valid, "identifier syntax")
}

pub(super) struct Imports {
    aliases: BTreeMap<String, V>,
    documents: BTreeMap<Vec<u8>, V>,
    references: bool,
}

impl Imports {
    fn new(lock: &V, documents: &V, pin: &[u8]) -> R<Self> {
        Self::new_mode(lock, documents, pin, false)
    }

    pub(super) fn new_mode(lock: &V, documents: &V, pin: &[u8], references: bool) -> R<Self> {
        Self::new_inner(lock, documents, pin, references, false)
    }

    pub(super) fn new_bindings(lock: &V, documents: &V, pin: &[u8]) -> R<Self> {
        Self::new_inner(lock, documents, pin, true, true)
    }

    fn new_inner(lock: &V, documents: &V, pin: &[u8], references: bool, native: bool) -> R<Self> {
        need(pin.len() == 32 && digest_consistency(sha256::hash(&encode(lock)?) == pin), "schema lock pin")?;
        fields(lock, &["version", "entries"])?;
        need(integer(get(lock, "version")?)? == 1, "schema lock version")?;
        let mut docs = BTreeMap::new();
        for row in arr(documents)? {
            fields(row, &["ref", "content"])?;
            let reference = get(row, "ref")?;
            fields(reference, &["id", "version", "digest"])?;
            semver(get(reference, "version")?)?;
            need(same(get(reference, "version")?, &V::A(vec![V::N(1), V::N(0), V::N(0)]))?, "unsupported schema version")?;
            dig(get(reference, "digest")?)?;
            let raw = bytes(get(row, "content")?)?;
            need(digest_consistency(bytes(get(reference, "digest")?)? == sha256::hash(raw)), "schema content digest")?;
            let document = decode(raw)?;
            fields(&document, &["alias", "id", "version", "representation"])?;
            need(get(&document, "id")? == get(reference, "id")?
                && get(&document, "version")? == get(reference, "version")?
                && (txt(get(&document, "representation")?)? == "OPAQUE_BSTR"
                    || (references && txt(get(&document, "representation")?)? == "VERSIONED_REF")
                    || (native && txt(get(&document, "representation")?)? == "NATIVE_CBOR")), "schema document contract")?;
            need(docs.insert(encode(&reference_identity(reference)?)?, document).is_none(), "duplicate schema document")?;
        }
        let mut aliases = BTreeMap::new();
        let mut previous: Option<Vec<u8>> = None;
        for row in arr(get(lock, "entries")?)? {
            fields(row, &["alias", "ref"])?;
            let alias = txt(get(row, "alias")?)?;
            let reference = get(row, "ref")?;
            let doc = docs.get(&encode(&reference_identity(reference)?)?).ok_or("unresolved schema document")?;
            need(txt(get(doc, "alias")?)? == alias, "schema alias binding")?;
            let id = txt(get(reference, "id")?)?;
            let tail = id.strip_prefix("acl.schema.").ok_or("schema ID")?;
            let (id_name, version) = tail.split_once('@').ok_or("schema ID")?;
            need(name(id_name) && number(version) && version == "1", "schema ID/version")?;
            let fixed = match alias {
                "EvidenceRef" => Some("evidence-ref"),
                "EvidenceIssuerRef" => Some("evidence-issuer-ref"),
                "ChannelRef" => Some("channel-ref"),
                "EventRef" => Some("event-ref"),
                "DatasetRef" => Some("dataset-ref"),
                "ExternalVersionedObjectRef" => Some("external-versioned-object-ref"),
                "EnvironmentClassID" => Some("environment-class-id"),
                "FaultDomainID" => Some("fault-domain-id"),
                "RegionID" => Some("region-id"),
                _ => None,
            };
            if let Some(fixed) = fixed {
                need(id == format!("acl.schema.{fixed}@1"), "normative import ID")?;
            }
            if references {
                need(alias != "ExternalTypedObject", "ExternalTypedObject is not an opaque import")?;
                if txt(get(doc, "representation")?)? == "VERSIONED_REF" {
                    need(alias == "ExternalVersionedObjectRef", "unsupported structured import alias")?;
                }
            }
            if native {
                let representation=txt(get(doc,"representation")?)?;
                if representation=="NATIVE_CBOR" {need(alias=="NativeValue"&&id=="acl.schema.r8-native-value@1","native schema namespace")?;}
                let fixed=match alias {"NetworkID"=>Some("network-id"),"MaintenanceAuthorityRef"=>Some("maintenance-authority-ref"),"PrincipalRef"=>Some("principal-ref"),"LogicalObjectRef"=>Some("logical-object-ref"),_=>None};
                if let Some(fixed)=fixed {need(id==format!("acl.schema.{fixed}@1")&&representation=="OPAQUE_BSTR","fixed imported alias")?;}
            }
            let encoded = encode(&s(alias))?;
            if let Some(last) = previous {
                need(last < encoded, "schema lock order")?;
            }
            previous = Some(encoded);
            need(aliases.insert(alias.to_owned(), reference.clone()).is_none(), "duplicate import alias")?;
        }
        need(aliases.len() == docs.len(), "unused schema document")?;
        if references {
            let reference = aliases.get("ExternalVersionedObjectRef").ok_or("external reference schema required")?;
            let document = docs.get(&encode(&reference_identity(reference)?)?).ok_or("external reference schema required")?;
            need(txt(get(document, "representation")?)? == "VERSIONED_REF", "structured reference schema required")?;
        }
        Ok(Self { aliases, documents: docs, references })
    }

    pub(super) fn check(&self, alias: &str, value: &V) -> R<()> {
        need(self.aliases.contains_key(alias), "unresolved import")?;
        if self.references {
            let reference = self.aliases.get(alias).ok_or("unresolved import")?;
            let document = self.documents.get(&encode(&reference_identity(reference)?)?).ok_or("unresolved schema document")?;
            Self::payload(value, txt(get(document, "representation")?)?)
        } else {
            bytes(value)?;
            Ok(())
        }
    }

    fn payload(value: &V, representation: &str) -> R<()> {
        match representation {
            "OPAQUE_BSTR" => { bytes(value)?; Ok(()) },
            "VERSIONED_REF" => versioned_ref(value),
            "NATIVE_CBOR" => {encode(value)?;Ok(())},
            _ => Err("unsupported schema representation".into()),
        }
    }

    pub(super) fn native_schema(&self) -> Option<&V> {
        self.aliases.get("NativeValue")
    }

    pub(super) fn external_object(&self, value: &V) -> R<()> {
        need(self.references, "external object wire mode required")?;
        fields(value, &["schema_ref", "canonical_bytes", "object_digest"])?;
        let reference = get(value, "schema_ref")?;
        self.check("ExternalVersionedObjectRef", reference)?;
        let document = self.documents.get(&encode(&reference_identity(reference)?)?).ok_or("external payload schema not in lock")?;
        let raw = bytes(get(value, "canonical_bytes")?)?;
        let payload = decode(raw)?;
        Self::payload(&payload, txt(get(document, "representation")?)?)?;
        dig(get(value, "object_digest")?)?;
        need(digest_consistency(bytes(get(value, "object_digest")?)? == sha256::hash(raw)), "external payload digest mismatch")
    }
}

fn versioned_ref(value: &V) -> R<()> {
    fields(value, &["id", "version", "digest"])?;
    need(!txt(get(value, "id")?)?.is_empty(), "empty external reference ID")?;
    semver(get(value, "version")?)?;
    dig(get(value, "digest")?)
}

pub(super) fn typed(value: &V, schema: &V, types: &V, imports: &Imports) -> R<()> {
    if let V::S(kind) = schema {
        if let Ok(named) = get(types, kind) {
            return typed(value, named, types, imports);
        }
        return match kind.as_str() {
            "native" => { encode(value)?; Ok(()) },
            "text" => { txt(value)?; Ok(()) },
            "bool" => need(matches!(value, V::B(_)), "bool"),
            "uint" => uint(value),
            "int" => need((i64::MIN as i128..=i64::MAX as i128).contains(&integer(value)?), "int64"),
            "digest" => dig(value),
            "semver" => semver(value),
            "rational" | "version-range" => { project(kind, value, false)?; Ok(()) },
            "external-object" => imports.external_object(value),
            "wire-time-range" => {
                let a = arr(value)?;
                need(a.len() == 2, "wire TimeRange tuple")?;
                typed(&a[0], &s("int"), types, imports)?;
                typed(&a[1], &s("int"), types, imports)?;
                need(integer(&a[0])? < integer(&a[1])?, "validity range")
            },
            "time-range" => {
                fields(value, &["start", "end"])?;
                typed(get(value, "start")?, &s("int"), types, imports)?;
                typed(get(value, "end")?, &s("int"), types, imports)?;
                need(integer(get(value, "start")?)? < integer(get(value, "end")?)?, "validity range")
            },
            _ => Err("unknown type".into()),
        };
    }
    if let Ok(required) = get(schema, "fields") {
        let optional = get(schema, "optional")?;
        let mut keys = BTreeSet::new();
        for (key, child) in object(required)? {
            let key = txt(key)?;
            keys.insert(key);
            typed(get(value, key)?, child, types, imports)?;
        }
        for (key, child) in object(optional)? {
            let key = txt(key)?;
            keys.insert(key);
            if let Ok(field) = get(value, key) {
                typed(field, child, types, imports)?;
            }
        }
        for (key, _) in object(value)? {
            need(keys.contains(txt(key)?), "unknown nested field")?;
        }
        return Ok(());
    }
    if let Ok(values) = get(schema, "enum") {
        txt(value)?;
        return need(arr(values)?.contains(value), "unknown enum");
    }
    if let Ok(kind) = get(schema, "identifier") {
        return identifier(value, txt(kind)?);
    }
    if let Ok(alias) = get(schema, "import_") {
        return imports.check(txt(alias)?, value);
    }
    let child = get(schema, "array").or_else(|_| get(schema, "set"))?;
    let mut previous: Option<Vec<u8>> = None;
    for row in arr(value)? {
        typed(row, child, types, imports)?;
        if get(schema, "set").is_ok() {
            let encoded = encode(row)?;
            if let Some(last) = previous {
                need(last < encoded, "set order or duplicate")?;
            }
            previous = Some(encoded);
        }
    }
    Ok(())
}

fn registry_digest(registry: &V) -> R<Vec<u8>> {
    let header = get(registry, "header")?;
    Ok(domain("ACLt/P0-1/RegistrySnapshot/1", &encode(&map(vec![
        ("schema_version", get(header, "schema_version")?.clone()),
        ("encoding_profile_id", get(header, "encoding_profile_id")?.clone()),
        ("entries", get(registry, "entries")?.clone()),
    ]))?))
}

pub(super) fn check_registry(registry: &V) -> R<()> {
    need(integer(get(get(registry, "header")?, "schema_version")?)? == 1, "registry schema version")?;
    let mut previous: Option<Vec<u8>> = None;
    for row in arr(get(registry, "entries")?)? {
        identifier(get(row, "id")?, txt(get(row, "object_kind")?)?)?;
        let key = encode(&V::A(vec![get(row, "object_kind")?.clone(),
            get(row, "id")?.clone(), get(row, "version")?.clone()]))?;
        if let Some(last) = previous {
            need(last < key, "registry order or duplicate identity")?;
        }
        previous = Some(key);
    }
    need(digest_consistency(bytes(get(get(registry, "header")?, "digest")?)? == registry_digest(registry)?), "registry digest")
}

pub(super) fn frontier_digest(frontier: &V) -> R<Vec<u8>> {
    let header = get(frontier, "header")?;
    let content = map(vec![
        ("schema_version", get(header, "schema_version")?.clone()),
        ("encoding_profile_id", get(header, "encoding_profile_id")?.clone()),
        ("id", get(header, "id")?.clone()),
        ("frontier_event_ref", get(frontier, "frontier_event_ref")?.clone()),
        ("event_records", get(frontier, "event_records")?.clone()),
        ("log_binding", get(frontier, "log_binding")?.clone()),
    ]);
    Ok(domain("ACLt/P0-1/EventFrontierSnapshot/1", &encode(&content)?))
}

pub(super) fn check_frontier(frontier: &V, imports: &Imports) -> R<()> {
    let header = get(frontier, "header")?;
    let version = integer(get(header, "schema_version")?)?;
    need([1, 2].contains(&version), "frontier version")?;
    need(digest_consistency(bytes(get(header, "digest")?)? == frontier_digest(frontier)?), "frontier digest")?;
    let mut parents = BTreeMap::new();
    let mut previous: Option<Vec<u8>> = None;
    for row in arr(get(frontier, "event_records")?)? {
        let key = encode(get(row, "event_ref")?)?;
        if let Some(last) = previous {
            need(last < key, "event order or duplicate")?;
        }
        previous = Some(key.clone());
        let kind = txt(get(row, "event_kind")?)?;
        let tag = match kind {
            "PHASE_I_VALIDATION" => "PHASE_I_RECORD",
            "PHASE_F_VALIDATION" => "PHASE_F_CALL",
            "CLUSTER_MAPPING_FIXED" => "CLUSTER_MAPPING",
            "SNAPSHOT_FROZEN" => "ELIGIBILITY_SNAPSHOT",
            "FUNDING_EXHAUSTED" | "DEADLINE_REACHED" | "EXECUTION_EXHAUSTED" => "RECEIPT",
            "VERIFICATION_STARTED" | "VERIFICATION_TERMINAL_COMMITTED" => {
                need(version == 2, "event version")?; "RECEIPT"
            },
            "OTHER" => "OPAQUE_IMPORTED",
            _ => return Err("event kind".into()),
        };
        let subject = get(row, "subject_ref")?;
        need(txt(get(subject, "tag")?)? == tag, "event subject tag")?;
        need(get(subject, "schema_ref").is_ok() == (kind == "OTHER"), "event subject fields")?;
        let id = get(subject, "id")?;
        match tag {
            "RECEIPT" => dig(id)?,
            "ELIGIBILITY_SNAPSHOT" | "OPAQUE_IMPORTED" => { txt(id)?; },
            "PHASE_F_CALL" => imports.check("EventRef", id)?,
            "PHASE_I_RECORD" => need(txt(id)?.strip_prefix("acl.pir.").is_some_and(ulid), "phase record ID")?,
            "CLUSTER_MAPPING" => need(txt(id)?.strip_prefix("acl.cmap.").is_some_and(ulid), "cluster ID")?,
            _ => return Err("subject type".into()),
        }
        let refs = arr(get(row, "parent_refs")?)?.iter().map(encode).collect::<R<Vec<_>>>()?;
        need(parents.insert(key, refs).is_none(), "duplicate event")?;
    }
    need(parents.contains_key(&encode(get(frontier, "frontier_event_ref")?)?), "missing frontier")?;
    let mut children: BTreeMap<Vec<u8>, Vec<Vec<u8>>> = parents.keys().cloned().map(|key| (key, vec![])).collect();
    let mut degrees = BTreeMap::new();
    for (key, refs) in &parents {
        degrees.insert(key.clone(), refs.len());
        for parent in refs {
            children.get_mut(parent).ok_or("unresolved parent")?.push(key.clone());
        }
    }
    let mut ready: Vec<Vec<u8>> = degrees.iter().filter(|(_, degree)| **degree == 0).map(|(key, _)| key.clone()).collect();
    let mut visited = 0;
    while let Some(key) = ready.pop() {
        visited += 1;
        for child in children.get(&key).ok_or("event missing")? {
            let degree = degrees.get_mut(child).ok_or("event degree")?;
            *degree -= 1;
            if *degree == 0 { ready.push(child.clone()); }
        }
    }
    need(visited == parents.len(), "causal cycle")?;
    need(arr(get(get(frontier, "log_binding")?, "event_inclusion_proofs")?)?.len() == parents.len(),
         "proof cardinality")
}

pub(super) fn run(input: &str, pin: &str) -> R<V> {
    let value = decode(&unhex(input)?)?;
    fields(&value, &["envelope", "schema_lock", "schema_documents"])?;
    let imports = Imports::new(get(&value, "schema_lock")?, get(&value, "schema_documents")?, &unhex(pin)?)?;
    let types = parse_json(include_str!("audit_types.json"))?;
    let envelope = get(&value, "envelope")?;
    fields(envelope, &["phase", "bundle", "object"])?;
    need(txt(get(envelope, "phase")?)? == "R", "registration phase")?;
    let profile = get(envelope, "object")?;
    check_profile(profile, &types, &imports, "Profile")?;
    let bundle = get(envelope, "bundle")?;
    typed(bundle, &s("Bundle"), &types, &imports)?;
    let registry = get(bundle, "registry_snapshot")?;
    check_registry(registry)?;
    let context = get(bundle, "context")?;
    let rh = get(registry, "header")?;
    let registry_ref = map(["id", "version", "digest"].iter().map(|key| Ok((*key, get(rh, key)?.clone()))).collect::<R<_>>()?);
    need(same_reference(get(context, "registry_snapshot_ref")?, &registry_ref)?, "registry context binding")?;
    let frontier = get(bundle, "event_frontier_snapshot")?;
    check_frontier(frontier, &imports)?;
    let fh = get(frontier, "header")?;
    let frontier_ref = map(vec![("id", get(fh, "id")?.clone()), ("digest", get(fh, "digest")?.clone())]);
    need(same_reference(get(context, "event_frontier_ref")?, &frontier_ref)?, "frontier context binding")?;
    if let Ok(reference) = get(profile, "supersedes") {
        let mut found = false;
        for row in arr(get(registry, "entries")?)? {
            if txt(get(row, "object_kind")?)? == "VERIFICATION_PROFILE"
                && ["id", "version"].iter().all(|key| get(row, key).ok() == get(reference, key).ok()) {
                found = true;
            }
        }
        need(found, "unresolved supersedes")?;
    }
    Ok(map(vec![
        ("profile_digest_hex", s(&hex(bytes(get(profile, "profile_digest")?)?))),
        ("registry_digest_hex", s(&hex(bytes(get(rh, "digest")?)?))),
        ("frontier_digest_hex", s(&hex(bytes(get(fh, "digest")?)?))),
        ("schema_lock_sha256", s(pin)), ("full_schema_valid", V::B(false)),
        ("source_authentication", V::B(false)),
    ]))
}

fn check_profile(profile: &V, types: &V, imports: &Imports, kind: &str) -> R<()> {
    typed(profile, &s(kind), types, imports)?;
    profile::run("profile-digest", &hex(&encode(profile)?))?;
    profile::audit_fields(profile)?;
    let mut ids = BTreeSet::new();
    for row in arr(get(profile, "assumption_references")?)? {
        need(ids.insert(txt(get(row, "assumption_id")?)?), "duplicate assumption")?;
        if txt(get(row, "role")?)? == "SAFETY_CRITICAL" {
            let expected = map(vec![("before_verification", s("BLOCK_ADMISSION")),
                ("during_verification", s("VERIFICATION_INVALIDATING")), ("after_terminal", s("QUALIFY_REVOKED"))]);
            need(same(get(row, "revocation_mapping")?, &expected)?, "safety revocation")?;
        }
    }
    Ok(())
}

const BASE_EXCLUSIONS: &[&str] = &[
    "EXC-BASE-INTENT", "EXC-BASE-LOWERING", "EXC-BASE-RIR-SPEC", "EXC-BASE-RPR-SPEC",
    "EXC-BASE-COMMON-MODE", "EXC-BASE-INDEPENDENCE", "EXC-BASE-SYBIL", "EXC-BASE-ABSOLUTE",
    "EXC-BASE-FITNESS", "EXC-BASE-AVAILABILITY", "EXC-BASE-CONFIDENTIALITY", "EXC-BASE-TIMELINESS",
    "EXC-BASE-LOG-BACKEND", "EXC-BASE-NETWORK-TRANSFER",
];

fn exclusion_registry_digest(registry: &V) -> R<Vec<u8>> {
    let header = get(registry, "header")?;
    Ok(domain("ACLt/P0-1/ExcludedClaimsRegistry/1", &encode(&map(vec![
        ("schema_version", get(header, "schema_version")?.clone()),
        ("encoding_profile_id", get(header, "encoding_profile_id")?.clone()),
        ("entries", get(registry, "entries")?.clone()),
    ]))?))
}

fn excluded_digest(selection: &V) -> R<Vec<u8>> {
    let mut ids = arr(get(selection, "exclusion_ids")?)?.iter()
        .map(|value| Ok((encode(value)?, value.clone()))).collect::<R<Vec<_>>>()?;
    ids.sort_by(|a, b| a.0.cmp(&b.0));
    Ok(domain("ACLt/P0-1/ExcludedClaims/1", &encode(&V::A(vec![
        get(selection, "registry_ref")?.clone(), V::A(ids.into_iter().map(|(_, value)| value).collect())
    ]))?))
}

fn check_excluded(selection: &V, registry: &V, snapshot: &V, types: &V, imports: &Imports) -> R<V> {
    typed(selection, &s("ExcludedClaims"), types, imports)?;
    typed(registry, &s("ExclusionRegistry"), types, imports)?;
    typed(snapshot, &s("Registry"), types, imports)?;
    check_registry(snapshot)?;
    let header = get(registry, "header")?;
    need(integer(get(header, "schema_version")?)? == 1, "exclusion registry schema version")?;
    need(digest_consistency(bytes(get(header, "digest")?)? == exclusion_registry_digest(registry)?), "SV-89: exclusion registry digest")?;
    let reference = map(["id", "version", "digest"].iter()
        .map(|key| Ok((*key, get(header, key)?.clone()))).collect::<R<_>>()?);
    need(same(get(selection, "registry_ref")?, &reference)?, "SV-08: exclusion registry identity mismatch")?;
    let mut found = false;
    for row in arr(get(snapshot, "entries")?)? {
        if txt(get(row, "object_kind")?)? == "EXCLUDED_CLAIMS_REGISTRY"
            && ["id", "version"].iter().all(|key| get(row, key).ok() == get(header, key).ok()) {
            found = true;
        }
    }
    need(found, "SV-08: exclusion registry not resolved in snapshot")?;
    let selected = arr(get(selection, "exclusion_ids")?)?.iter().map(txt).collect::<R<BTreeSet<_>>>()?;
    need(BASE_EXCLUSIONS.iter().all(|id| selected.contains(id)), "SV-07: baseline exclusions missing")?;
    let available = arr(get(registry, "entries")?)?.iter()
        .map(|row| txt(get(row, "exclusion_id")?)).collect::<R<BTreeSet<_>>>()?;
    need(selected.is_subset(&available), "SV-08: exclusion ID missing from registry")?;
    need(digest_consistency(bytes(get(selection, "digest")?)? == excluded_digest(selection)?), "SV-72: excluded selection digest")?;
    Ok(map(vec![
        ("excluded_digest_hex", s(&hex(bytes(get(selection, "digest")?)?))),
        ("exclusion_registry_digest_hex", s(&hex(bytes(get(header, "digest")?)?))),
        ("selected_ids", V::N(selected.len() as i128)),
        ("baseline_ids", V::N(BASE_EXCLUSIONS.len() as i128)),
    ]))
}

pub(super) fn run_excluded(input: &str) -> R<V> {
    let value = decode(&unhex(input)?)?;
    fields(&value, &["selection", "registry", "registry_snapshot"])?;
    let types = parse_json(include_str!("audit_types.json"))?;
    let imports = Imports { aliases: BTreeMap::new(), documents: BTreeMap::new(), references: false };
    check_excluded(get(&value, "selection")?, get(&value, "registry")?, get(&value, "registry_snapshot")?, &types, &imports)
}

pub(super) fn run_references(input: &str, pin: &str) -> R<V> {
    let value = decode(&unhex(input)?)?;
    fields(&value, &["envelope", "schema_lock", "schema_documents", "registry_objects"])?;
    let imports = Imports::new_mode(get(&value, "schema_lock")?, get(&value, "schema_documents")?, &unhex(pin)?, true)?;
    let types = parse_json(include_str!("audit_types.json"))?;
    let envelope = get(&value, "envelope")?;
    fields(envelope, &["phase", "bundle", "object"])?;
    need(txt(get(envelope, "phase")?)? == "R", "registration phase")?;
    let profile = get(envelope, "object")?;
    check_profile(profile, &types, &imports, "ReferencesProfile")?;
    let bundle = get(envelope, "bundle")?;
    typed(bundle, &s("ReferencesBundle"), &types, &imports)?;
    let registry = get(bundle, "registry_snapshot")?;
    check_registry(registry)?;
    let context = get(bundle, "context")?;
    let rh = get(registry, "header")?;
    let registry_ref = map(["id", "version", "digest"].iter().map(|key| Ok((*key, get(rh, key)?.clone()))).collect::<R<_>>()?);
    need(same_reference(get(context, "registry_snapshot_ref")?, &registry_ref)?, "registry context binding")?;
    let frontier = get(bundle, "event_frontier_snapshot")?;
    check_frontier(frontier, &imports)?;
    let fh = get(frontier, "header")?;
    let frontier_ref = map(vec![("id", get(fh, "id")?.clone()), ("digest", get(fh, "digest")?.clone())]);
    need(same_reference(get(context, "event_frontier_ref")?, &frontier_ref)?, "frontier context binding")?;
    if let Ok(reference) = get(profile, "supersedes") {
        let mut found = false;
        for row in arr(get(registry, "entries")?)? {
            if txt(get(row, "object_kind")?)? == "VERIFICATION_PROFILE"
                && ["id", "version"].iter().all(|key| get(row, key).ok() == get(reference, key).ok()) {
                found = true;
            }
        }
        need(found, "unresolved supersedes")?;
    }
    let assets = arr(get(&value, "registry_objects")?)?;
    need(assets.len() == 1, "one explicit exclusion registry asset required")?;
    fields(&assets[0], &["object_kind", "object"])?;
    need(txt(get(&assets[0], "object_kind")?)? == "EXCLUDED_CLAIMS_REGISTRY", "unsupported registry asset kind")?;
    let excluded = check_excluded(get(profile, "excluded_claims")?, get(&assets[0], "object")?, registry, &types, &imports)?;
    let mut output = object(&excluded)?.to_vec();
    for (key, value) in [
        ("profile_digest_hex", s(&hex(bytes(get(profile, "profile_digest")?)?))),
        ("registry_digest_hex", s(&hex(bytes(get(rh, "digest")?)?))),
        ("frontier_digest_hex", s(&hex(bytes(get(fh, "digest")?)?))),
        ("schema_lock_sha256", s(pin)),
        ("full_schema_valid", V::B(false)), ("source_authentication", V::B(false)),
    ] { output.push((s(key), value)); }
    Ok(V::M(output))
}

fn rule_method(profile: &V) -> R<&str> {
    object(profile)?;
    need(get(profile, "post_execution_predicate").is_err(), "SV-32: removed post_execution_predicate")?;
    let method = match get(profile, "verification_method").map_err(|_| "SV-03: verification method")? {
        V::S(value) => value.as_str(),
        _ => return Err("SV-03: verification method".into()),
    };
    need(["DIRECT_VERIFIED", "PROOF_VERIFIED", "REEXEC_BOUNDED", "REEXEC_AUDIT_ONLY"].contains(&method),
         "SV-03: verification method")?;
    Ok(method)
}

pub(super) fn rule_assumptions(assumptions: &V, types: &V, imports: &Imports) -> R<()> {
    let mut ids = BTreeSet::new();
    for row in arr(assumptions)? {
        object(row)?;
        let mapping = get(row, "revocation_mapping").map_err(|_| "SV-33: missing revocation mapping")?;
        fields(mapping, &["before_verification", "during_verification", "after_terminal"])
            .map_err(|_| "SV-33: three closed revocation stages required")?;
        fields(get(row, "scope").map_err(|_| "SV-59: missing scope")?,
               &["task_class", "rir_profile_range", "rpr_version_range", "environment_class", "fault_domains", "geography"])
            .map_err(|_| "SV-59: six closed scope dimensions required")?;
        if get(row, "role").ok() == Some(&s("SAFETY_CRITICAL")) {
            let expected = map(vec![("before_verification", s("BLOCK_ADMISSION")),
                ("during_verification", s("VERIFICATION_INVALIDATING")), ("after_terminal", s("QUALIFY_REVOKED"))]);
            need(same(mapping, &expected)?, "SV-37: safety-critical revocation mapping")?;
        }
        typed(row, &s("ReferencesAssumption"), types, imports)?;
        need(ids.insert(txt(get(row, "assumption_id")?)?), "SV-76: duplicate assumption ID")?;
    }
    Ok(())
}

fn rule_required(method: &str, assumptions: &V) -> R<()> {
    let required: &[(&str, &str)] = match method {
        "DIRECT_VERIFIED" => &[("PREDICATE_SOUNDNESS", "SAFETY_CRITICAL")],
        "PROOF_VERIFIED" => &[("PROOF_SYSTEM", "SAFETY_CRITICAL")],
        "REEXEC_BOUNDED" => &[("SUPPORT_CAPABILITY_BOUND", "SAFETY_CRITICAL"),
            ("RANDOMNESS", "SAFETY_CRITICAL"), ("SNAPSHOT", "SAFETY_CRITICAL"),
            ("CORRECTNESS_BRIDGE", "SAFETY_CRITICAL"), ("CALIBRATION", "LIVENESS")],
        "REEXEC_AUDIT_ONLY" => &[],
        _ => return Err("SV-03: verification method".into()),
    };
    let present = arr(assumptions)?.iter().map(|row| Ok((txt(get(row, "assumption_class")?)?,
        txt(get(row, "role")?)?))).collect::<R<BTreeSet<_>>>()?;
    need(required.iter().all(|pair| present.contains(pair)), "SV-38: required assumption class/role missing")
}

fn rule_degradation(value: &V, types: &V, imports: &Imports) -> R<()> {
    fields(value, &["target", "triggers"])?;
    typed(get(value, "target")?, &s("ProfileRef"), types, imports)?;
    for trigger in arr(get(value, "triggers")?)? {
        let trigger = match trigger { V::S(value) => value.as_str(), _ => return Err("SV-22: degradation trigger".into()) };
        need(["SUPPORT_CAPABILITY_BOUND_UNAVAILABLE", "POPULATION_TOO_SMALL", "CALIBRATION_OUT_OF_SCOPE"].contains(&trigger),
             "SV-22: unknown degradation trigger")?;
    }
    Ok(())
}

pub(super) fn assumption_set_digest(value: &V) -> R<Vec<u8>> {
    let mut rows = Vec::new();
    for row in arr(value)? {
        identifier(get(row, "assumption_id")?, "ASSUMPTION")?;
        dig(get(row, "statement_digest")?)?;
        let pair = V::A(vec![get(row, "assumption_id")?.clone(), get(row, "statement_digest")?.clone()]);
        rows.push((encode(&pair)?, pair));
    }
    rows.sort_by(|a, b| a.0.cmp(&b.0));
    Ok(domain("ACLt/P0-1/AssumptionSet/1", &encode(&V::A(rows.into_iter().map(|(_, pair)| pair).collect()))?))
}

pub(super) fn common_rules(profile: &V, registry: &V, types: &V, imports: &Imports) -> R<V> {
    let method = rule_method(profile)?;
    profile::run("profile-digest", &hex(&encode(profile)?))?;
    let assumptions = get(profile, "assumption_references")?;
    rule_assumptions(assumptions, types, imports)?;
    rule_required(method, assumptions)?;
    typed(registry, &s("Registry"), types, imports)?;
    check_registry(registry)?;
    if let Ok(reference) = get(profile, "supersedes") {
        typed(reference, &s("ProfileRef"), types, imports)?;
        let mut found = false;
        for row in arr(get(registry, "entries")?)? {
            if txt(get(row, "object_kind")?)? == "VERIFICATION_PROFILE"
                && ["id", "version"].iter().all(|key| get(row, key).ok() == get(reference, key).ok()) { found = true; }
        }
        need(found, "SV-84: unresolved supersedes")?;
    }
    if let Ok(declaration) = get(profile, "degradation") { rule_degradation(declaration, types, imports)?; }
    Ok(map(vec![
        ("verification_method", s(method)), ("assumptions", V::N(arr(assumptions)?.len() as i128)),
        ("assumption_set_digest_hex", s(&hex(&assumption_set_digest(assumptions)?))),
        ("full_schema_valid", V::B(false)), ("source_authentication", V::B(false)),
    ]))
}

pub(super) fn run_rules(input: &str, pin: &str, audit: bool) -> R<V> {
    let value = decode(&unhex(input)?)?;
    let types = parse_json(include_str!("audit_types.json"))?;
    if audit {
        fields(&value, &["envelope", "schema_lock", "schema_documents", "registry_objects"])?;
    } else {
        fields(&value, &["profile", "registry_snapshot", "schema_lock", "schema_documents", "assumption_set_digest"])?;
    }
    let imports = Imports::new_mode(get(&value, "schema_lock")?, get(&value, "schema_documents")?, &unhex(pin)?, true)?;
    if audit {
        let envelope = get(&value, "envelope")?;
        fields(envelope, &["phase", "bundle", "object"])?;
        need(txt(get(envelope, "phase")?)? == "R", "Phase R envelope")?;
        fields(get(envelope, "bundle")?, &["context", "registry_snapshot", "event_frontier_snapshot"])?;
        let profile = get(envelope, "object")?;
        need(rule_method(profile)? == "REEXEC_AUDIT_ONLY", "audit-only integration scope")?;
        let common = common_rules(profile, get(get(envelope, "bundle")?, "registry_snapshot")?, &types, &imports)?;
        need(get(profile, "degradation").is_err(), "fixed audit integration excludes degradation")?;
        let output = run_references(input, pin)?;
        let mut rows = object(&output)?.to_vec();
        rows.push((s("assumption_set_digest_hex"), get(&common, "assumption_set_digest_hex")?.clone()));
        Ok(V::M(rows))
    } else {
        let output = common_rules(get(&value, "profile")?, get(&value, "registry_snapshot")?, &types, &imports)?;
        dig(get(&value, "assumption_set_digest")?)?;
        need(digest_consistency(hex(bytes(get(&value, "assumption_set_digest")?)?) == txt(get(&output, "assumption_set_digest_hex")?)?),
             "SV-73: assumption set digest mismatch")?;
        Ok(output)
    }
}
