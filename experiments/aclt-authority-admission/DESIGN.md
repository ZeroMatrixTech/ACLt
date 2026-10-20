# Experimental v2 authority boundary

The task and unit equivalence rules are inherited from `aclt-multinode-admission`.
The claim hashes the ordered integer values using `ACLT-LOCAL-CLAIM-1` and
`stats-int-v1`. Aliased tasks must bind identical chunks and enrolled unit lists;
credential aliases map to the same unit. Instance, boot and arbitrary round names
cannot create qualification. The first reservation binds its boot and random ticket.

The external SQLite database is the sole authority. Every operation reopens the
existing file, checks frozen metadata and uses a transaction. Slot transitions and
their diagnostic events commit together. `synchronous=FULL` and parent directory
fsync precede successful signed responses. A failed/lost response after commit
does not refund a slot. Signing happens after commit; a signing failure may leave
an unacknowledged durable decision.

| State | Operation | Outcome |
|---|---|---|
| Absent | reserve | Commit RESERVED, return sole ticket |
| Any existing slot | reserve | `consumed`; never disclose/reissue ticket |
| RESERVED | correct bound result | Commit accepted digest and immutable receipt |
| RESERVED | incorrect bound result | Commit failed flag; permanent rejection |
| ACCEPTED | identical bound result | Return original receipt as duplicate |
| ACCEPTED | different bound result | Mark conflict, preserve receipt and digest |
| FAILED | any result | Reject |
| Any | wrong boot/ticket/identity | Reject without creating contribution |

The authority recomputes exact rows for this fixed integer workload. This is not
a general-purpose verification, RIR/RPR or formal Receipt implementation.

The authority signs the entire response payload using a test RSA-2048 key through
OpenSSL's SHA-256 adapter. Gateways hold no signing/worker keys. Worker request
authentication uses per-credential HMAC, with new secrets distinct from v1. Worker
public key fingerprints, authority ID and config digest are provisioned through a
trusted deployment configuration. TLS, enrollment administration and production
key lifecycle remain separate work.

Worker `O_EXCL`/file fsync/directory fsync occurs before the reserve request. The
worker invokes the existing C++ program only after a verified sole grant. It saves
an immutable complete submission before transmitting. Replaying a saved packet is
permitted; recomputation and reissuing a lost ticket are forbidden. Lost grants
and incomplete tasks can sacrifice availability, preserving the established policy.

There is no automatic migration or empty-ledger recovery. V2 experimental tasks
and credentials use fresh enrollment; historical v1 records remain under v1 and
cannot be used as v2 permission. The worker's existing result directory is never
reset by a gateway restart.

Protected fault domain: gateway process, network and gateway disk snapshots. The
authority and its signing/deployment configuration remain trusted and outside
those snapshots. Availability is single-authority; failover, authority rollback,
worker clones, Sybil resistance and arbitrary malicious execution are not solved.
Protocol SemanticStatus and Gates are unchanged.
