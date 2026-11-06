# FM-S3 candidate terminal-coverage contract options

Namespace: `ACLt/FM/S3b/1` AUDIT_CONTRACT with opt-in fields. This is a
**test-route candidate** under [ADR-0008](../../docs/05-decisions/ADR-0008-fm-s3-interface-decisions.md),
not formal Profile registration, official admission or a closed P0-1B rule.
Normative 00–03 documents are unchanged by this contract.

Each option adds fixed fields to the canonical contract bytes, so a Receipt that
selects it has a new component reference, a new Receipt digest and a new Requester
signature. Existing OK-only and Task-trap contracts keep their exact bytes
(SHA-256 `7f196206…bd412` and `5dfc3071…872f`), transitions and replay rules.
`s3_authority.check_bundle` reconstructs the full expected contract from the field
presence and rejects any other byte string.

| Option | Contract fields | Source |
|---|---|---|
| Task outcomes | `task_outcomes=RIR_OK_ABORT_AND_TRAPS_V1` | #69 |
| Execution closure | `execution_closure=RIR_TEST_NO_RETRY_CLOSURE_V1`, `closure_observer_der` | Observer-signed closure (`s3_closure.py`) |
| Verified RPR entry | `start_source=VERIFIED_RPR_ENTRY_DESCRIPTOR_V1`, `rpr_entry=RPR_ENTRY_DESCRIPTOR_V1` | `s3_terminals.py` |
| Funding boundary | `funding_boundary=PREFUNDED_BALANCE_AT_ACTIVATION_V1`, `boundary_resolution=RESOLVE_BOUNDARY_OVER_AUTHORITY_LOG_V1` | `s3_terminals.py` |

## Verified RPR entry and start states

With `rpr_entry`, `S3_START` is rejected. The Provider sends `S3_ENTRY` with the
role binding plus an `entry` descriptor. The authority recomputes the descriptor
from the frozen Receipt and pinned config and requires byte equality:

`contract, role, assignment, runtime_sha256, runtime_support, rir_digest, entry,
input_ref, input_sha256, fuel, output_bytes_limit, memory_pages, call_depth_limit,
step_limit, network, capabilities`.

`input_sha256` is the SHA-256 of the exact packed runtime input derived from the
immutable input object. The worker checks its local input and artifact against
the descriptor and derives the runtime argv only from it
(`s3_terminals.invocation_args`). The start identity binds the descriptor, and
every later result or HostFault must cite that start.

The authority projects one state per role in QUERY results and in the Decision:

| State | Fact |
|---|---|
| `NOT_CONSUMED` | No committed CONSUME for the role |
| `AUTHORIZATION_CONSUMED` | CONSUME committed, no verified entry yet |
| `EXECUTION_STARTED` | Verified entry committed |
| `START_UNKNOWN` | At evaluation, CONSUME committed without a verified entry |

`START_UNKNOWN` adds cause `START_UNDETERMINED` and therefore
`VERIFICATION_INVALIDATING → UNRESOLVED`. The consumed attempt is retained and no
re-execution is authorized. A verified entry proves that the Provider signed the
exact pinned invocation before the guest call; it does not prove that the runtime
actually ran, because there is no attested sandbox. Worker-local stages
(`INTENT_ONLY`, `AUTHORIZATION_CONSUMED`, `EXECUTION_STARTED`,
`INVOCATION_RECORDED`) are returned after a restart for the operator only.

## Execution closure (FAILED)

`S3_CLOSE_EXECUTION` is signed by the Requester and carries an observation signed
by the contract-pinned closure observer key, which must differ from the issuer,
Requester and Provider keys. The observation binds the contract, genesis, the
executor role binding, the recorded executor start, the pinned runtime and the
runtime record `HOST_FAULT/HOST_RESOURCE_EXHAUSTED`. The authority accepts it only
when the executor attempt was consumed and started, the auditor has not consumed
a lease, the phase is still `BEFORE_VERIFICATION`, and no valid result exists.
The record (`attempts_observed=1`, `valid_submission_count=0`) is committed as the
`EXECUTION_EXHAUSTED` event; identical retries return it, and a conflicting
closure is rejected. After closure, activation, consumption and further role
submissions fail. The Decision cites the exhaustion event, and
`EXECUTION_FAILED → FAILED`.

An executor's own `S3_HOST_FAULT` is only an authenticated self-report and never
closes execution. Without an accepted closure, a faulted or interrupted executor
reaches `EXPIRED` at the deadline.

## Funding boundary (FUNDING_EXHAUSTED)

With `funding_boundary`, a first ACTIVATE that cannot reserve the Receipt's
`total_limit` from the finite prefunded test balance is not rejected. After all
ordinary ACTIVATE checks pass, the authority commits a boundary record
`{funding_exhausted, receipt, role, required, available}` and leaves the lease
`PROPOSED`. An identical retry returns the record. Any later ACTIVATE or CONSUME
for that Receipt is rejected, so no evidence can be admitted after the boundary.

At `S3_FINALIZE` the authority builds an EventFrontierSnapshot projection from the
authenticated log prefix. Only the event whose sequence, operation, Receipt and
request digest match the boundary record is `FUNDING_EXHAUSTED`. A deadline
reached at evaluation is appended as the authority's own `DEADLINE_REACHED`
observation, a child of the current head. `ResolveBoundary` from
`tools/verification_profile/admission.py` then selects `BUDGET_EXHAUSTED`,
`DEADLINE_REACHED`, nothing, or `VERIFICATION_INVALIDATING` (cause
`BOUNDARY_UNRESOLVED`) for a reference that does not resolve.
`BUDGET_EXHAUSTED → FUNDING_EXHAUSTED`. The Decision records the observation,
the resolution and the frontier digest. Settlement uses the frozen fee row; with
nothing reserved, it closes with zero rights.

S2 reserves the whole Receipt at the first activation. This boundary therefore
arises only before any reservation. Mid-process metered exhaustion is not
modeled. Because the S2 log is a single chain, the concurrent branch of
`ResolveBoundary` is unreachable here and is covered only by its pure vectors.

## Decision record additions

The base Decision fields and ordering are unchanged. Rules keep the frozen order
`VERIFICATION_INVALIDATING, EXECUTION_FAILED, BUDGET_EXHAUSTED, DEADLINE_REACHED,
EVIDENCE_EXHAUSTED` with terminals `UNRESOLVED, FAILED, FUNDING_EXHAUSTED,
EXPIRED, UNRESOLVED`. Optional keys appear only for the selecting contract:

- `execution_observation`: the closure record and its exhaustion event;
- `start_states`: the final state per role;
- `boundary`: the boundary observation, resolution and frontier digest.

## Limits

- The closure observer key, authority and auditor are on host A in the dual-host
  topology, which is one fault domain.
- The test clock is operator-supplied.
- The runtime is an honest pinned host, not an OS sandbox.
- Entry and closure facts are candidate test facts. They do not establish the
  OQ-04/OQ-05 execution-closure source or a MainnetAssuranceProfile.
