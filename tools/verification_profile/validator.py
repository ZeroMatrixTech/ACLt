"""P0-1B bootstrap validator.

This module intentionally implements only the SV identifiers recorded in
schemas/verification-profile/coverage.json.  It is fail-closed for production
use until L2 and the remaining Type A rules are implemented.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable


PROFILE_ID = re.compile(r"^acl\.vp\.[a-z][a-z0-9-]{0,62}\.[a-z][a-z0-9-]{0,62}$")
TASK_TYPE_ID = re.compile(r"^acl\.tt\.[a-z][a-z0-9-]{0,62}$")
ASSUMPTION_ID = re.compile(r"^ACL-ASM-[0-9]{4}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")

METHODS = {
    "DIRECT_VERIFIED",
    "PROOF_VERIFIED",
    "REEXEC_BOUNDED",
    "REEXEC_AUDIT_ONLY",
}

CAUSE_PRIORITY = {
    "WINDOW_EXPIRED": 1,
    "OUT_OF_SCOPE": 2,
    "REVOKED": 3,
}


@dataclass(frozen=True)
class ValidationIssue:
    sv_id: str
    path: str
    message: str


def _issue(sv_id: str, path: str, message: str) -> ValidationIssue:
    return ValidationIssue(sv_id=sv_id, path=path, message=message)


def parse_uint(value: Any) -> int:
    """Parse ACLt Schema View v1 canonical uint decimal text."""
    if not isinstance(value, str) or not re.fullmatch(r"0|[1-9][0-9]*", value):
        raise ValueError("uint must be canonical unsigned decimal text")
    if len(value) > 20:
        raise ValueError("uint exceeds uint64")
    number = int(value)
    if number > 2**64 - 1:
        raise ValueError("uint exceeds uint64")
    return number


def parse_rational(value: Any) -> Fraction:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("Rational must contain exactly two decimal strings")
    numerator_text, denominator_text = value
    if not isinstance(numerator_text, str) or not re.fullmatch(r"0|-?[1-9][0-9]*", numerator_text):
        raise ValueError("invalid canonical numerator")
    denominator = parse_uint(denominator_text)
    if denominator == 0:
        raise ValueError("denominator must be positive")
    if len(numerator_text) > 20:
        raise ValueError("numerator exceeds int64")
    numerator = int(numerator_text)
    if not -(2**63) <= numerator <= 2**63 - 1:
        raise ValueError("numerator exceeds int64")
    reduced = Fraction(numerator, denominator)
    if reduced.numerator != numerator or reduced.denominator != denominator:
        raise ValueError("Rational must be reduced")
    return reduced


def reduce_causes(cause_codes: Iterable[str]) -> str:
    """V1 reducer from a complete CauseSet to one EffectiveVerdict."""
    try:
        codes = list(cause_codes)
    except TypeError as exc:
        raise ValueError("CauseSet must be an iterable of cause strings") from exc
    if any(not isinstance(code, str) for code in codes):
        raise ValueError("CauseSet must contain cause strings")
    if len(codes) != len(set(codes)):
        raise ValueError("CauseSet contains a duplicate cause")
    unknown = set(codes) - set(CAUSE_PRIORITY)
    if unknown:
        raise ValueError(f"unknown CauseCode: {sorted(unknown)}")
    if not codes:
        return "VALID"
    return max(codes, key=CAUSE_PRIORITY.__getitem__)


def validate_l1a_bootstrap(profile: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not isinstance(profile, dict):
        return [_issue("SV-01", "$", "profile must be an object")]
    required = {
        "schema_version", "encoding_profile_id", "profile_id", "profile_version",
        "profile_digest", "task_type", "contract_tuple_constraints",
        "admission_predicate", "excluded_claims",
        "verification_method", "method_parameters", "result_equivalence",
        "cost_parameters", "assumption_references", "failure_mapping",
        "decision_mapping", "documentation",
    }
    version = profile.get("schema_version")
    if version != "2":
        required.add("verified_claim_spec")
    allowed = required | {"verified_claim_spec", "supersedes", "safety_parameters", "liveness_parameters", "degradation"}
    missing = sorted(required - set(profile))
    extra = sorted(set(profile) - allowed)
    if missing:
        issues.append(_issue("SV-01", "$", f"missing fields: {missing}"))
    if extra:
        issues.append(_issue("SV-01", "$", f"unknown fields: {extra}"))

    if version not in ("1", "2"):
        issues.append(_issue("SV-01", "$.schema_version", "unsupported schema version"))
    if profile.get("encoding_profile_id") != "acl.enc.p0-1@1":
        issues.append(_issue("SV-01", "$.encoding_profile_id", "unsupported encoding profile"))
    if not PROFILE_ID.fullmatch(str(profile.get("profile_id", ""))):
        issues.append(_issue("SV-01", "$.profile_id", "invalid ProfileID"))
    if not TASK_TYPE_ID.fullmatch(str(profile.get("task_type", ""))):
        issues.append(_issue("SV-01", "$.task_type", "invalid TaskTypeID"))
    if not DIGEST.fullmatch(str(profile.get("profile_digest", ""))):
        issues.append(_issue("SV-01", "$.profile_digest", "digest must be 32-byte lowercase hex"))

    method = profile.get("verification_method")
    if not isinstance(method, str) or method not in METHODS:
        issues.append(_issue("SV-31", "$.verification_method", "unknown verification method"))
    has_safety = "safety_parameters" in profile
    has_liveness = "liveness_parameters" in profile
    if method == "REEXEC_BOUNDED":
        if not (has_safety and has_liveness):
            issues.append(_issue("SV-31", "$", "REEXEC_BOUNDED requires safety and liveness parameters"))
    elif has_safety or has_liveness:
        issues.append(_issue("SV-31", "$", "only REEXEC_BOUNDED may carry safety/liveness parameters"))
    claim_key = "verified_claim_spec"
    claim = profile.get(claim_key)
    if version == "2":
        if method == "REEXEC_AUDIT_ONLY" and claim_key in profile:
            issues.append(_issue("SV-30", "$.verified_claim_spec", "audit-only must omit the claim key"))
        elif isinstance(method, str) and method in METHODS and method != "REEXEC_AUDIT_ONLY":
            if not isinstance(claim, dict):
                issues.append(_issue("SV-30", "$.verified_claim_spec", "method requires a claim object"))
    elif method == "REEXEC_AUDIT_ONLY" and claim != "BOTTOM":
        issues.append(_issue("SV-30", "$.verified_claim_spec", "legacy audit-only claim must be BOTTOM"))
    elif claim == "BOTTOM" and method != "REEXEC_AUDIT_ONLY":
        issues.append(_issue("SV-30", "$.verified_claim_spec", "only legacy audit-only may declare BOTTOM"))

    references = profile.get("assumption_references", [])
    if not isinstance(references, list) or any(not isinstance(row, dict) for row in references):
        issues.append(_issue("SV-01", "$.assumption_references", "assumptions must be object rows"))
    else:
        ids = [row.get("assumption_id") for row in references]
        if any(not isinstance(value, str) or not ASSUMPTION_ID.fullmatch(value) for value in ids):
            issues.append(_issue("SV-76", "$.assumption_references", "invalid AssumptionID"))
        elif len(ids) != len(set(ids)):
            issues.append(_issue("SV-76", "$.assumption_references", "duplicate AssumptionID"))
        if any(not isinstance(row.get("role"), str) or row["role"] not in {"SAFETY_CRITICAL", "LIVENESS", "INFORMATIONAL"} for row in references):
            issues.append(_issue("SV-01", "$.assumption_references", "invalid assumption role"))
    return issues


def validate_reexec_bounds(profile: dict[str, Any]) -> list[ValidationIssue]:
    if not isinstance(profile, dict) or profile.get("verification_method") != "REEXEC_BOUNDED":
        return []
    issues: list[ValidationIssue] = []
    try:
        safety = profile["safety_parameters"]
        liveness = profile["liveness_parameters"]
        g = parse_uint(safety["G"])
        b = parse_uint(safety["B"])
        q = parse_uint(liveness["Q"])
        delta_min = parse_rational(safety["delta_min"])
        if not (0 <= b < q <= g):
            issues.append(_issue("SV-10", "$", "requires 0 <= B < Q <= G"))
        elif Fraction(q - b, g) < delta_min or delta_min <= 0:
            issues.append(_issue("SV-10", "$.safety_parameters.delta_min", "delta_min exceeds the frozen gap or is non-positive"))

        weights = profile["method_parameters"]["mixture_weights"]
        parsed = [(parse_uint(row["m"]), parse_rational(row["weight"])) for row in weights]
        if [m for m, _ in parsed] != sorted({m for m, _ in parsed}):
            issues.append(_issue("SV-11", "$.method_parameters.mixture_weights", "m values must be sorted and unique"))
        if any(weight < 0 for _, weight in parsed) or sum((weight for _, weight in parsed), Fraction()) != 1:
            issues.append(_issue("SV-11", "$.method_parameters.mixture_weights", "weights must be non-negative and sum exactly to one"))
        if any(m < q for m, weight in parsed if weight > 0):
            issues.append(_issue("SV-11", "$.method_parameters.mixture_weights", "every supported m must be >= Q"))
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        issues.append(_issue("SV-10", "$", f"invalid exact parameter encoding: {exc}"))
    return issues


def validate_assumption_snapshot(
    profile: dict[str, Any],
    snapshot: dict[str, Any],
    reducer_ref: dict[str, Any],
    terminal_state: str,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not isinstance(profile, dict) or not isinstance(snapshot, dict) or not isinstance(reducer_ref, dict):
        return [_issue("SV-54a", "$", "profile, snapshot and reducer reference must be objects")]
    references=profile.get("assumption_references")
    if not isinstance(references, list) or any(not isinstance(row, dict) or not isinstance(row.get("assumption_id"), str) or not isinstance(row.get("role"), str) or row["role"] not in {"SAFETY_CRITICAL", "LIVENESS", "INFORMATIONAL"} for row in references):
        return [_issue("SV-54a", "$", "malformed assumption references")]
    ids=[row["assumption_id"] for row in references]
    if len(ids)!=len(set(ids)) or any(not ASSUMPTION_ID.fullmatch(value) for value in ids):
        return [_issue("SV-76", "$", "invalid or duplicate assumption IDs")]
    states=snapshot.get("assumption_states")
    if not isinstance(states,list) or any(not isinstance(row,dict) or not isinstance(row.get("assumption_id"),str) for row in states):
        return [_issue("SV-54a", "$", "malformed assumption states")]

    if snapshot.get("reducer_ref") != reducer_ref:
        issues.append(_issue("SV-54a", "$.snapshot.reducer_ref", "reducer ref does not match the bound MAP"))

    required_ids = sorted(
        row["assumption_id"]
        for row in profile.get("assumption_references", [])
        if row.get("role") in {"SAFETY_CRITICAL", "LIVENESS"}
    )
    states = snapshot.get("assumption_states", [])
    actual_ids = [row.get("assumption_id") for row in states]
    if actual_ids != required_ids:
        issues.append(_issue("SV-54a", "$.snapshot.assumption_states", "state rows must exactly cover required assumptions in canonical order"))

    role_by_id = {row["assumption_id"]: row.get("role") for row in profile.get("assumption_references", [])}
    for index, row in enumerate(states):
        causes = row.get("cause_set")
        if not isinstance(causes,list) or any(not isinstance(cause,dict) or not isinstance(cause.get("cause_code"),str) for cause in causes):
            issues.append(_issue("SV-54a", f"$.snapshot.assumption_states[{index}].cause_set", "malformed CauseSet"))
            continue
        codes = [cause["cause_code"] for cause in causes]
        if codes != sorted(set(codes)):
            issues.append(_issue("SV-54a", f"$.snapshot.assumption_states[{index}].cause_set", "CauseSet must be sorted and unique"))
            continue
        try:
            expected = reduce_causes(codes)
        except ValueError as exc:
            issues.append(_issue("SV-54a", f"$.snapshot.assumption_states[{index}].cause_set", str(exc)))
            continue
        if row.get("effective_verdict") != expected:
            issues.append(_issue("SV-54a", f"$.snapshot.assumption_states[{index}].effective_verdict", "does not equal the frozen reduction"))
        if terminal_state == "TRUSTED" and role_by_id.get(row.get("assumption_id")) == "SAFETY_CRITICAL" and expected != "VALID":
            issues.append(_issue("SV-57", f"$.snapshot.assumption_states[{index}]", "TRUSTED requires every safety-critical verdict to be VALID"))
    return issues


def validate(profile: dict[str, Any]) -> list[ValidationIssue]:
    return validate_l1a_bootstrap(profile) + validate_reexec_bounds(profile)



def validate_profile_cbor(raw: bytes) -> list[ValidationIssue]:
    """Formal v2 digest plus selected registration rules, without full SchemaValid."""
    from tools.verification_profile import codec, profile as profile_codec
    try:
        value = codec.decode(raw)
        profile_codec.content_map(value)
        profile_codec.verify_digest(value)
        profile_codec.decision_fields(value)
        if value['verification_method'] == 'REEXEC_AUDIT_ONLY':
            profile_codec.audit_fields(value)
    except (codec.CodecError, KeyError, TypeError, RecursionError) as exc:
        message = str(exc)
        rule = message.split(':', 1)[0] if message.startswith('SV-') else 'PROFILE_INPUT'
        return [_issue(rule, '$', message)]
    return []



def validate_registration_cbor(raw: bytes, lock_pin: bytes) -> list[ValidationIssue]:
    from tools.verification_profile import codec, registration
    try:
        registration.inspect(raw, lock_pin)
    except (codec.CodecError, KeyError, TypeError, RecursionError) as exc:
        message = str(exc)
        rule = message.split(':', 1)[0] if message.startswith('SV-') else 'REGISTRATION_INPUT'
        return [_issue(rule, '$', message)]
    return []



def validate_registration_references_cbor(raw: bytes, lock_pin: bytes) -> list[ValidationIssue]:
    """Scoped audit wire/import checks plus explicit exclusion registry assets."""
    from tools.verification_profile import codec, references
    try:
        references.inspect(raw, lock_pin)
    except (codec.CodecError, KeyError, TypeError, RecursionError) as exc:
        message = str(exc)
        rule = message.split(':', 1)[0] if message.startswith('SV-') else 'REGISTRATION_INPUT'
        return [_issue(rule, '$', message)]
    return []



def validate_registration_rules_cbor(raw: bytes, lock_pin: bytes, *, audit: bool = False) -> list[ValidationIssue]:
    """R4 selected common rules or scoped audit integration; not full ValidateR."""
    from tools.verification_profile import codec, registration_rules
    try:
        function = registration_rules.inspect_audit if audit else registration_rules.inspect
        function(raw, lock_pin)
    except (codec.CodecError, KeyError, TypeError, RecursionError) as exc:
        message = str(exc)
        rule = message.split(':', 1)[0] if message.startswith('SV-') else 'REGISTRATION_INPUT'
        return [_issue(rule, '$', message)]
    return []



def validate_method_matrix_cbor(raw: bytes, lock_pin: bytes, *, audit: bool = False) -> list[ValidationIssue]:
    """R5 frozen matrices only; unresolved imports/wire slots are not approved."""
    from tools.verification_profile import codec, method_rules
    try:
        function = method_rules.inspect_audit if audit else method_rules.inspect
        function(raw, lock_pin)
    except (codec.CodecError, KeyError, TypeError, RecursionError) as exc:
        message = str(exc)
        rule = message.split(':', 1)[0] if message.startswith('SV-') else 'METHOD_INPUT'
        return [_issue(rule, '$', message)]
    return []


def validate_creation_cbor(raw: bytes, lock_pin: bytes, contract_pin: bytes, *, phase: str) -> list[ValidationIssue]:
    from tools.verification_profile import codec, creation
    try:
        creation.inspect(raw, lock_pin, contract_pin, phase=phase)
    except (codec.CodecError, KeyError, TypeError, RecursionError) as exc:
        message = str(exc)
        return [_issue(message.split(':',1)[0] if message.startswith('SV-') else 'CREATION_TEST_INPUT', '$', message)]
    return []


def validate_selection_assets_cbor(raw: bytes, lock_pin: bytes) -> list[ValidationIssue]:
    from tools.verification_profile import codec, selection
    try:
        selection.inspect(raw, lock_pin)
    except (codec.CodecError, KeyError, TypeError, RecursionError) as exc:
        message=str(exc)
        return [_issue(message.split(':',1)[0] if message.startswith('SV-') else 'SELECTION_INPUT', '$', message)]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the P0-1B bootstrap validator")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--production", action="store_true", help="always fail while coverage is incomplete")
    parser.add_argument('--profile-cbor', action='store_true',
                        help='Profile v2 L2 digest and selected Phase R rules on raw CBOR')
    parser.add_argument('--registration-cbor', action='store_true',
                        help='nested audit types, pinned schema imports and Phase R bundle')
    parser.add_argument('--registration-references-cbor', action='store_true',
                        help='audit wire TimeRange/ExternalTypedObject and exclusion registry references')
    parser.add_argument('--registration-rules-cbor', action='store_true', help='R4 selected common registration rules only')
    parser.add_argument('--registration-r4-cbor', action='store_true', help='R4 fixed audit registration integration')
    parser.add_argument('--method-matrix-cbor', action='store_true', help='R5 selected method parameter and outcome matrices')
    parser.add_argument('--registration-r5-cbor', action='store_true', help='R5 fixed audit integration')
    parser.add_argument('--schema-lock-sha256',
                        help='caller-supplied trusted schema lock pin for --registration-cbor')
    parser.add_argument('--creation-i-cbor', action='store_true', help='R6 fixed audit TEST Phase I transcript')
    parser.add_argument('--creation-f-cbor', action='store_true', help='R6 fixed audit TEST Phase F envelope')
    parser.add_argument('--test-contract-sha256', help='external pin of the explicit test admission contract')
    parser.add_argument('--registration-assets-cbor', action='store_true', help='R7 registration/selection components and explicit TEST applicability input')
    args = parser.parse_args()
    creation_mode = args.creation_i_cbor or args.creation_f_cbor
    if creation_mode == (args.test_contract_sha256 is None):
        parser.error('I/F test entries require --test-contract-sha256; other entries forbid it')
    registration_mode = any((args.registration_cbor,args.registration_references_cbor,args.registration_rules_cbor,args.registration_r4_cbor,args.method_matrix_cbor,args.registration_r5_cbor,args.creation_i_cbor,args.creation_f_cbor,args.registration_assets_cbor))
    if registration_mode == (args.schema_lock_sha256 is None):
        parser.error('registration CBOR entries require --schema-lock-sha256')
    if sum((args.registration_cbor,args.registration_references_cbor,args.profile_cbor,args.registration_rules_cbor,args.registration_r4_cbor,args.method_matrix_cbor,args.registration_r5_cbor,args.creation_i_cbor,args.creation_f_cbor,args.registration_assets_cbor))>1:
        parser.error('choose one CBOR entry')
    def unique_object(pairs):
        result={}
        for key,value in pairs:
            if key in result: raise ValueError(f"duplicate JSON key: {key}")
            result[key]=value
        return result
    def invalid_constant(value):
        raise ValueError(f"invalid JSON constant: {value}")
    try:
        if args.registration_assets_cbor:
            issues = validate_selection_assets_cbor(args.profile.read_bytes(), bytes.fromhex(args.schema_lock_sha256))
        elif creation_mode:
            issues = validate_creation_cbor(args.profile.read_bytes(), bytes.fromhex(args.schema_lock_sha256),
                bytes.fromhex(args.test_contract_sha256), phase='I' if args.creation_i_cbor else 'F')
        elif args.method_matrix_cbor or args.registration_r5_cbor:
            pin = bytes.fromhex(args.schema_lock_sha256)
            issues = validate_method_matrix_cbor(args.profile.read_bytes(), pin, audit=args.registration_r5_cbor)
        elif args.registration_rules_cbor or args.registration_r4_cbor:
            pin = bytes.fromhex(args.schema_lock_sha256)
            issues = validate_registration_rules_cbor(args.profile.read_bytes(), pin, audit=args.registration_r4_cbor)
        elif args.registration_references_cbor:
            pin = bytes.fromhex(args.schema_lock_sha256)
            issues = validate_registration_references_cbor(args.profile.read_bytes(), pin)
        elif args.registration_cbor:
            pin = bytes.fromhex(args.schema_lock_sha256)
            issues = validate_registration_cbor(args.profile.read_bytes(), pin)
        elif args.profile_cbor:
            issues = validate_profile_cbor(args.profile.read_bytes())
        else:
            profile = json.loads(args.profile.read_text(encoding="utf-8"), object_pairs_hook=unique_object, parse_constant=invalid_constant)
            issues = validate(profile)
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        issues = [_issue("INPUT", "$", f"unreadable or malformed JSON: {exc}")]
    if args.production:
        issues.append(_issue("COVERAGE", "$", "P0-1B coverage is incomplete; production mode is fail-closed"))
    print(json.dumps([issue.__dict__ for issue in issues], ensure_ascii=False, indent=2))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
