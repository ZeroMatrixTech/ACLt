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
        "WEAKENING_EDGE" => "acl.we.",
        "EXCLUDED_CLAIMS_REGISTRY" => "acl.ecr.",
        "MAINNET_ASSURANCE_PROFILE" => "acl.map.",
        "REGISTRY_SNAPSHOT" => "acl.rs.",
        "FRONTIER" => "acl.efs.",
        "TASK" => "acl.tt.",
        "PREDICATE" => "acl.pred.",
        "EQUIVALENCE" => "acl.eq.",
        "ENCODING" => "acl.enc.",
        _ => return Err("unknown identifier kind".into()),
    };
    let tail = value.strip_prefix(prefix).ok_or("identifier prefix")?;
    let valid = match kind {
        "PROFILE" | "VERIFICATION_PROFILE" => tail.split_once('.')
            .is_some_and(|(family, slug)| name(family) && name(slug)),
        "REGISTRY_SNAPSHOT" | "FRONTIER" => ulid(tail),
        "PREDICATE" => tail.split_once('@').is_some_and(|(id, version)| {
            let parts: Vec<_> = version.split('.').collect();
            name(id) && parts.len() == 3 && parts.iter().all(|part| number(part))
        }),
        "EQUIVALENCE" | "ENCODING" => tail.split_once('@')
            .is_some_and(|(id, version)| name(id) && number(version)),
        _ => name(tail),
    };
    need(valid, "identifier syntax")
}

struct Imports {
    aliases: BTreeMap<String, V>,
}

impl Imports {
    fn new(lock: &V, documents: &V, pin: &[u8]) -> R<Self> {
        need(pin.len() == 32 && sha256::hash(&encode(lock)?) == pin, "schema lock pin")?;
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
            need(bytes(get(reference, "digest")?)? == sha256::hash(raw), "schema content digest")?;
            let document = decode(raw)?;
            fields(&document, &["alias", "id", "version", "representation"])?;
            need(get(&document, "id")? == get(reference, "id")?
                && get(&document, "version")? == get(reference, "version")?
                && txt(get(&document, "representation")?)? == "OPAQUE_BSTR", "schema document contract")?;
            need(docs.insert(encode(reference)?, document).is_none(), "duplicate schema document")?;
        }
        let mut aliases = BTreeMap::new();
        let mut previous: Option<Vec<u8>> = None;
        for row in arr(get(lock, "entries")?)? {
            fields(row, &["alias", "ref"])?;
            let alias = txt(get(row, "alias")?)?;
            let reference = get(row, "ref")?;
            let doc = docs.get(&encode(reference)?).ok_or("unresolved schema document")?;
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
                "ExternalVersionedObjectRef" => Some("external-versioned-object-ref"),
                "EnvironmentClassID" => Some("environment-class-id"),
                "FaultDomainID" => Some("fault-domain-id"),
                "RegionID" => Some("region-id"),
                _ => None,
            };
            if let Some(fixed) = fixed {
                need(id == format!("acl.schema.{fixed}@1"), "normative import ID")?;
            }
            let encoded = encode(&s(alias))?;
            if let Some(last) = previous {
                need(last < encoded, "schema lock order")?;
            }
            previous = Some(encoded);
            need(aliases.insert(alias.to_owned(), reference.clone()).is_none(), "duplicate import alias")?;
        }
        need(aliases.len() == docs.len(), "unused schema document")?;
        Ok(Self { aliases })
    }

    fn check(&self, alias: &str, value: &V) -> R<()> {
        need(self.aliases.contains_key(alias), "unresolved import")?;
        bytes(value)?;
        Ok(())
    }
}

fn typed(value: &V, schema: &V, types: &V, imports: &Imports) -> R<()> {
    if let V::S(kind) = schema {
        if let Ok(named) = get(types, kind) {
            return typed(value, named, types, imports);
        }
        return match kind.as_str() {
            "native" => { encode(value)?; Ok(()) },
            "text" => { txt(value)?; Ok(()) },
            "uint" => uint(value),
            "int" => need((i64::MIN as i128..=i64::MAX as i128).contains(&integer(value)?), "int64"),
            "digest" => dig(value),
            "semver" => semver(value),
            "rational" | "version-range" => { project(kind, value, false)?; Ok(()) },
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

fn check_registry(registry: &V) -> R<()> {
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
    need(bytes(get(get(registry, "header")?, "digest")?)? == registry_digest(registry)?, "registry digest")
}

fn frontier_digest(frontier: &V) -> R<Vec<u8>> {
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

fn check_frontier(frontier: &V, imports: &Imports) -> R<()> {
    let header = get(frontier, "header")?;
    let version = integer(get(header, "schema_version")?)?;
    need([1, 2].contains(&version), "frontier version")?;
    need(bytes(get(header, "digest")?)? == frontier_digest(frontier)?, "frontier digest")?;
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
    typed(profile, &s("Profile"), &types, &imports)?;
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
    let bundle = get(envelope, "bundle")?;
    typed(bundle, &s("Bundle"), &types, &imports)?;
    let registry = get(bundle, "registry_snapshot")?;
    check_registry(registry)?;
    let context = get(bundle, "context")?;
    let rh = get(registry, "header")?;
    let registry_ref = map(["id", "version", "digest"].iter().map(|key| Ok((*key, get(rh, key)?.clone()))).collect::<R<_>>()?);
    need(same(get(context, "registry_snapshot_ref")?, &registry_ref)?, "registry context binding")?;
    let frontier = get(bundle, "event_frontier_snapshot")?;
    check_frontier(frontier, &imports)?;
    let fh = get(frontier, "header")?;
    let frontier_ref = map(vec![("id", get(fh, "id")?.clone()), ("digest", get(fh, "digest")?.clone())]);
    need(same(get(context, "event_frontier_ref")?, &frontier_ref)?, "frontier context binding")?;
    if let Ok(reference) = get(profile, "supersedes") {
        let mut found = false;
        for row in arr(get(registry, "entries")?)? {
            if txt(get(row, "object_kind")?)? == "VERIFICATION_PROFILE"
                && ["id", "version", "digest"].iter().all(|key| get(row, key).ok() == get(reference, key).ok()) {
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
