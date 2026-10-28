# FM-S1a candidate byte contract

`foundation.json` fixes a **test-only candidate** wire contract and exact test
signature suite. It does not register official PrincipalRecord, PrincipalRef,
NetworkID or a protocol digest tag. `value.schema.txt` is an immutable local
import: its exact bytes (no trailing newline) are SHA-256 pinned in both languages.
Unknown id/version/digest imports are rejected; no permissive fallback exists.

Python's `tools/formal_migration/foundation.py` shares the existing P0-1 primitive
codec. Rust's `tools/verification_profile/rust/fm.rs` uses the independent Rust
CBOR/NFC/SHA core in that directory. Each language performs its own raw parsing,
field/type checks, Schema View projection and signing-input construction. Neither
calls the other. OpenSSL is shared cryptographic infrastructure, not two
independent RSA implementations. There are no new package downloads.

## Encoding and identity

All fields are mandatory closed text-key maps in lexicographic encoded-key order.
Arrays preserve order; `members` is a strictly sorted unique Set<text>. Decimal
integers in Schema View are strings, bytes/digests are lowercase hex strings;
booleans remain JSON booleans. SemVer and Rational use their declared tuple types,
never string inference. ENUM values are exact case-sensitive text from the
schema's finite sets. This extends typed ENUM support for the FM objects only;
ClaimTemplate ENUM slot declarations and complete imported types remain pending.

Primitive ranges, NFC Unicode 16.0.0, shortest CBOR, 1 MiB raw limit, depth 48,
10,000 decoded items, no null/float/tag/indefinite encoding follow the existing
candidate `acl.enc.p0-1@1` core and the normative owners in §3.2.1/§17 of
verification-profile-schema.md. The 4 KiB imported payload limit is an additional
FM test bound. Inputs over any limit fail closed before signature execution.

Principal identity is a domain-separated digest of the public DER key. The record
also binds key digest, role, protocol version, deployment/network anchors and
validity interval. Its complete digest is supplied independently by the caller as
a trusted pin and must equal the envelope's principal_ref. A self-selected record
and a valid signature cannot grant authorization. Only Requester and Provider are
roles; a log implementation signer is not a third Principal. Fixed pins have no
implicit revocation/rotation history; changing a key/role/context requires explicit
trusted pin replacement. That operational authority is an accepted test assumption.

## Signature contract

Suite `fm.rsa2048-pkcs1v15-sha256@1` is RSASSA-PKCS1-v1_5/SHA-256, 2048-bit RSA,
exponent 65537. Public keys are exact canonical DER SubjectPublicKeyInfo, 294
bytes, rsaEncryption OID with explicit NULL parameters. Modulus is exactly 256
bytes with its high bit set and is odd. Signature is exactly 256 raw bytes.
Unknown suite, malformed DER, alternate padding/hash, wrong key or wrong width
are rejected. This selection is a test route, not a production algorithm policy.

`SigningInput = u8(len(ASCII tag)) || ASCII tag || CBOR(unsigned envelope)`;
tag is `ACLt/FM/S1a/SignatureInput/1`. Every envelope field except `signature` is
included. OpenSSL hashes that entire input once with SHA-256; it does not sign an
already-hashed digest. The header binds schema/encoding/protocol versions, suite,
principal reference, role, object type, deployment/network, caller-frozen context,
nonce, explicit validity times and pinned payload schema/bytes. Identity and
principal record digests use distinct tags listed in foundation.json.

Only FM_TEST_VALUE is supported. Requester signs REQUEST; Provider signs ACCEPT
or RESULT. These are test operations and do not stand for Receipt, Lease or
ResultSubmission schema. All time is explicit int64 UTC milliseconds; no verifier
reads protocol time from the wall clock. Time intervals are nonnegative, half-open
and contained in the pinned record interval. Both adapters fail closed on missing
OpenSSL or a 10-second crypto timeout. Temporary verification files live in new
private directories and are removed after the operation; they contain no private
keys. Driver-generated signing keys are temporary and never part of the repository.

## Verification and replay boundary

`verify({record,envelope,expected,now})` accepts an independently obtained pin and
exact caller context. `expected` must come from the consuming application, never
be copied from the peer's message to authorize that peer. A saved old envelope
fails against a new nonce/context. An identical query remains idempotently valid;
this pure function does **not** durably consume a challenge or authorize execution,
funding or settlement. Those state transitions belong to FM-S2/S3. Offline validity
is not newness, registry authority, independence or production assurance.

`fm-principal`, `fm-envelope`, `fm-signing` and `fm-value` CLI modes validate
structure and produce bytes/views/digests; only `fm-verify` additionally checks
trusted context and RSA. A structurally valid envelope alone is not an accepted
signature. Use newline-delimited `kind<TAB>lowercase-CBOR-hex` via the existing
Rust executable; `view-fm-*<TAB>JSON` performs typed inverse projection first.

Run `make check-fm-s1a` for Python regressions or `make test-fm-s1a` for independent
Rust construction and full positive/negative vectors with fresh signing. Set
`FM_S1A_REPORT=/new/report.json` to retain the report. For two-host build/encoding
checks run `python3 -B scripts/fm-s1a-dualhost.py --peer USER@B_IP --remote-root
/new/absolute/B/path --output /new/A/output`. The remote directory must not exist;
BatchMode and StrictHostKeyChecking remain enabled. This uses SSH for source and
vector transfer and remote builds; it does not exercise a task network protocol.

## Rule ownership and remaining scope

| Owner | Python / independent Rust implementation | Evidence and limit |
|---|---|---|
| SV-25 | existing codec.Reader / Rust Reader + FM common header | primitive/tag/indefinite negatives; FM envelope only, no full Profile closure |
| SV-42 | codec.project + foundation.project / Rust project + fm::proj | map order, set uniqueness, reduced Rational and typed containers; other protocol containers pending |
| SV-52 | codec typed int/uint + Reader / Rust typed integer + Reader | signed/unsigned extrema, under/overflow, shortest encoding and bignum rejection |
| SV-118 | foundation.from_view_json/inspect / fm::run + proj | fixed typed views and independent byte equality; complete five-phase Schema View pending |
| §3.2.1 / §17.5 | both independent NFC/type implementations | Unicode 16.0.0 and explicit SemVer; FM closed ENUM sets and pinned import, not all external imports |
| ADR-0007 D-4 / FM-A05 partial | principal/signing_input/verify / fm principal/message/verify | role-bound record pin, context and exact RSA vectors; full lifecycle/official objects pending |

These mappings identify the normative rule owner used by the local slice. They do
not add rules to the global implemented registry or change its 3/19/97 counts.
