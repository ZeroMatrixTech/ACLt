import copy
import json
from pathlib import Path
import unittest

from tools.verification_profile import codec
from tools.verification_profile.validator import (
    parse_rational,
    reduce_causes,
    validate,
    validate_assumption_snapshot,
)


ZERO_DIGEST = "00" * 32
REDUCER_REF = {
    "id": "acl.reducer.assumption-verdict",
    "version": ["1", "0", "0"],
    "digest": "11" * 32,
}


def bounded_profile():
    return {
        "schema_version": "1",
        "encoding_profile_id": "acl.enc.p0-1@1",
        "profile_id": "acl.vp.test.reexec-bounded",
        "profile_version": ["1", "0", "0"],
        "profile_digest": ZERO_DIGEST,
        "task_type": "acl.tt.test",
        "contract_tuple_constraints": {},
        "admission_predicate": "acl.pred.always@1.0.0",
        "verified_claim_spec": {},
        "excluded_claims": {},
        "verification_method": "REEXEC_BOUNDED",
        "method_parameters": {
            "mixture_weights": [
                {"m": "4", "weight": ["1", "2"]},
                {"m": "5", "weight": ["1", "2"]},
            ]
        },
        "result_equivalence": {},
        "safety_parameters": {"G": "5", "B": "2", "delta_min": ["1", "5"]},
        "liveness_parameters": {"Q": "4"},
        "cost_parameters": {},
        "assumption_references": [
            {"assumption_id": "ACL-ASM-0001", "role": "SAFETY_CRITICAL"},
            {"assumption_id": "ACL-ASM-0002", "role": "LIVENESS"},
            {"assumption_id": "ACL-ASM-0003", "role": "INFORMATIONAL"},
        ],
        "failure_mapping": {},
        "decision_mapping": {},
        "documentation": {},
    }


class BootstrapValidatorTests(unittest.TestCase):
    def test_valid_bounded_profile(self):
        self.assertEqual(validate(bounded_profile()), [])

    def test_bounded_gap_is_exact(self):
        profile = bounded_profile()
        profile["safety_parameters"]["delta_min"] = ["1", "2"]
        self.assertIn("SV-10", {issue.sv_id for issue in validate(profile)})

    def test_non_reexec_must_not_carry_safety_parameters(self):
        profile = bounded_profile()
        profile["verification_method"] = "DIRECT_VERIFIED"
        self.assertIn("SV-31", {issue.sv_id for issue in validate(profile)})

    def test_rational_must_be_reduced(self):
        with self.assertRaises(ValueError):
            parse_rational(["2", "4"])

    def test_cause_reducer_preserves_multiple_facts(self):
        self.assertEqual(reduce_causes(["OUT_OF_SCOPE", "WINDOW_EXPIRED"]), "OUT_OF_SCOPE")
        self.assertEqual(reduce_causes(["REVOKED", "OUT_OF_SCOPE"]), "REVOKED")

    def test_assumption_snapshot_accepts_complete_cause_set(self):
        profile = bounded_profile()
        snapshot = {
            "reducer_ref": REDUCER_REF,
            "assumption_states": [
                {"assumption_id": "ACL-ASM-0001", "cause_set": [], "effective_verdict": "VALID"},
                {
                    "assumption_id": "ACL-ASM-0002",
                    "cause_set": [
                        {"cause_code": "OUT_OF_SCOPE"},
                        {"cause_code": "WINDOW_EXPIRED"},
                    ],
                    "effective_verdict": "OUT_OF_SCOPE",
                },
            ],
        }
        self.assertEqual(validate_assumption_snapshot(profile, snapshot, REDUCER_REF, "UNRESOLVED"), [])

    def test_trusted_rejects_invalid_safety_assumption(self):
        profile = bounded_profile()
        snapshot = {
            "reducer_ref": REDUCER_REF,
            "assumption_states": [
                {
                    "assumption_id": "ACL-ASM-0001",
                    "cause_set": [{"cause_code": "REVOKED"}],
                    "effective_verdict": "REVOKED",
                },
                {"assumption_id": "ACL-ASM-0002", "cause_set": [], "effective_verdict": "VALID"},
            ],
        }
        self.assertIn("SV-57", {issue.sv_id for issue in validate_assumption_snapshot(profile, snapshot, REDUCER_REF, "TRUSTED")})

    def test_reducer_mismatch_is_rejected(self):
        profile = bounded_profile()
        snapshot = {
            "reducer_ref": {**REDUCER_REF, "digest": "22" * 32},
            "assumption_states": [
                {"assumption_id": "ACL-ASM-0001", "cause_set": [], "effective_verdict": "VALID"},
                {"assumption_id": "ACL-ASM-0002", "cause_set": [], "effective_verdict": "VALID"},
            ],
        }
        self.assertIn("SV-54a", {issue.sv_id for issue in validate_assumption_snapshot(profile, snapshot, REDUCER_REF, "UNRESOLVED")})

    def test_duplicate_assumption_id_is_rejected(self):
        profile = bounded_profile()
        profile["assumption_references"].append(copy.deepcopy(profile["assumption_references"][0]))
        self.assertIn("SV-76", {issue.sv_id for issue in validate(profile)})



class ProfileV2ClaimPresenceTests(unittest.TestCase):
    def test_fixed_cbor_projection_and_schema_view_presence(self):
        path = Path(__file__).with_name('codec') / 'profile-v2-claim-presence.json'
        for vector in json.loads(path.read_text())['vectors']:
            with self.subTest(vector=vector['id']):
                raw = bytes.fromhex(vector['cbor_hex'])
                if vector.get('decode_reject'):
                    with self.assertRaises(codec.CodecError):
                        codec.decode(raw)
                    continue
                fragment = codec.decode(raw)
                self.assertEqual(codec.encode(fragment), raw)
                profile = bounded_profile()
                del profile['verified_claim_spec']
                profile.update(fragment, schema_version=str(fragment['schema_version']))
                if profile['verification_method'] != 'REEXEC_BOUNDED':
                    del profile['safety_parameters']
                    del profile['liveness_parameters']
                issues = validate(profile)
                self.assertEqual(not issues, vector['accepted'], issues)
                if issues:
                    self.assertEqual({issue.sv_id for issue in issues}, {'SV-30'})

    def test_schema_view_null_is_not_absence(self):
        profile = bounded_profile()
        del profile['safety_parameters']
        del profile['liveness_parameters']
        profile.update(schema_version='2', verification_method='REEXEC_AUDIT_ONLY',
                       verified_claim_spec=None)
        self.assertEqual({issue.sv_id for issue in validate(profile)}, {'SV-30'})


if __name__ == "__main__":
    unittest.main()
