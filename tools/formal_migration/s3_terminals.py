# SPDX-License-Identifier: Apache-2.0
"""Candidate S3 start-state and funding-boundary facts for opt-in audit contracts.

`rpr_entry` replaces the self-attested S3_START with S3_ENTRY: the Provider must
sign the exact pinned runtime invocation derived from the frozen Receipt, and the
authority projects AUTHORIZATION_CONSUMED, EXECUTION_STARTED and START_UNKNOWN.
`funding_boundary` records an authority FUNDING_EXHAUSTED event when the first
activation cannot reserve the Receipt from the finite prefunded test balance, and
resolves it against the deadline with the VerificationProfile ResolveBoundary rule.
Existing contracts keep their bytes and transitions. Execution closure is
s3_closure's observer-signed path. Nothing here authenticates a mainnet source.
"""
import copy
import hashlib
import struct

from tools.formal_migration import s2
from tools.verification_profile import admission, codec as c

ENTRY_SOURCE = 'VERIFIED_RPR_ENTRY_DESCRIPTOR_V1'
ENTRY_CONTRACT = 'RPR_ENTRY_DESCRIPTOR_V1'
FUNDING_CONTRACT = 'PREFUNDED_BALANCE_AT_ACTIVATION_V1'
BOUNDARY_RESOLUTION = 'RESOLVE_BOUNDARY_OVER_AUTHORITY_LOG_V1'
DOMAIN = 'ACLt/FM/S3/Terminals/1'
CALL_DEPTH_LIMIT = 8
STEP_LIMIT = 20000000


def h(value):
    return c.domain_hash(DOMAIN, c.encode(value))


# --- Verified RPR entry ---------------------------------------------------

def packed_input(bundle):
    values = c.decode(bundle['inputs'][0]['content'])
    return struct.pack('<QQ', 2, len(values)) + b''.join(struct.pack('<q', x) for x in values)


def entry_descriptor(cfg, bundle, rid, role):
    """The exact pinned runtime invocation the enrolled role must perform."""
    proposal = s2.proposal(cfg, rid, role, bundle)
    execution = bundle['receipt']['execution']
    runtime = c.decode(next(x for x in bundle['components'] if x['kind'] == 'RUNTIME')['content'])
    return dict(contract=ENTRY_CONTRACT, role=role, assignment=proposal['assignment'],
                runtime_sha256=cfg['runtime_sha256'], runtime_support=runtime['support'],
                rir_digest=proposal['rir_digest'], entry=bundle['receipt']['entry'],
                input_ref=proposal['input_ref'],
                input_sha256=hashlib.sha256(packed_input(bundle)).digest(),
                fuel=execution['fuel'], output_bytes_limit=execution['output_bytes_limit'],
                memory_pages=execution['memory_bytes'] // 65536,
                call_depth_limit=CALL_DEPTH_LIMIT, step_limit=STEP_LIMIT,
                network=execution['network'], capabilities=execution['capabilities'])


def invocation_args(descriptor, executable, artifact_path, input_path):
    """Derive the runtime argv only from an authority-verified descriptor."""
    return [str(executable), '--artifact', str(artifact_path), str(input_path),
            str(descriptor['fuel']), str(descriptor['output_bytes_limit']),
            str(descriptor['call_depth_limit']), str(descriptor['step_limit']),
            str(descriptor['memory_pages']), descriptor['rir_digest'].hex()]


def start_states(task, *, final=False):
    """AUTHORIZATION_CONSUMED becomes START_UNKNOWN once evaluation must decide."""
    states = {}
    for role in s2.ROLES:
        if role in task['audit']['starts']:
            states[role] = 'EXECUTION_STARTED'
        elif task['leases'][role]['intent'] != s2.ZERO:
            states[role] = 'START_UNKNOWN' if final else 'AUTHORIZATION_CONSUMED'
        else:
            states[role] = 'NOT_CONSUMED'
    return states


# --- Funding boundary -----------------------------------------------------

def activation(cfg, state, req, now, task, events):
    """Record FUNDING_EXHAUSTED instead of rejecting an under-funded first activation.

    Returns None when the ordinary S2 ACTIVATE path applies (funds are available or
    already reserved). Every S2 ACTIVATE precondition is checked before recording.
    The first activation reserves the whole Receipt, so this candidate boundary can
    only arise before any reservation; mid-process metered exhaustion is not modeled.
    """
    boundary = task['audit'].get('funding_boundary')
    if task['funding_held'] and boundary is None:
        return None
    amount = task['bundle']['funding']['total_limit']
    if boundary is None and state['free'] >= amount:
        return None
    record = s2.verify_request(cfg, req, now)
    c.need(now >= state['last_time'], 'authority clock rollback')
    nonce = req['actor'].hex() + ':' + req['nonce'].hex()
    previous = state['nonces'].get(nonce)
    body = req['body']
    deadline = task['bundle']['receipt']['execution']['deadline']
    if previous is not None:
        c.need(previous['request'] == s2.h(req), 'idempotency conflict')
        c.need(not task['fenced'] and now < deadline, 'stale lease/deadline')
        return state, previous['result'], now
    c.need(boundary is None, 'S3 funding boundary recorded')
    s2.pin(body['assignment'])
    s2.uint(body['epoch'])
    c.need(body['epoch'] == 1 and not task['fenced'] and now < deadline, 'stale epoch/lease/deadline')
    role = next((r for r in s2.ROLES
                 if task['leases'][r]['proposal']['assignment'] == body['assignment']), None)
    c.need(role is not None, 'foreign assignment')
    lease = task['leases'][role]
    c.need(req['actor'] == lease['proposal']['provider'] and record['role'] == 'PROVIDER',
           'accept/consume role')
    c.need(lease['state'] == 'PROPOSED', 'lease already activated')
    result = dict(funding_exhausted=True, receipt=task['rid'], role=role,
                  required=amount, available=state['free'])
    nxt = copy.deepcopy(state)
    nxt['tasks'][task['rid'].hex()]['audit']['funding_boundary'] = dict(
        result, seq=len(events) + 1, received_at=now, request=s2.h(req))
    nxt['last_time'] = now
    nxt['nonces'][nonce] = dict(request=s2.h(req), result=copy.deepcopy(result))
    s2.check_funding_conservation(cfg, nxt)
    c.decode(c.encode(nxt))
    return nxt, result, now


def _subject(event):
    body = event['request']['body']
    if 'receipt' in body:
        return dict(tag='RECEIPT', id=body['receipt'])
    return dict(tag='DEPLOYMENT', id=event['genesis'])


def frontier_view(task, events, deadline_at=None):
    """Build an EventFrontierSnapshot projection from the authenticated log prefix.

    Only the event whose sequence, operation and Receipt match the recorded funding
    boundary is classified as FUNDING_EXHAUSTED. The S2 log is a single parent chain;
    a deadline reached at evaluation is the authority's own observation, appended as
    a child of the current head.
    """
    funding = task['audit'].get('funding_boundary')
    records = []
    refs = {}
    head = None
    for raw in events:
        event = c.decode(raw)
        ref = s2.h(event)
        kind = 'AUTHORITY_EVENT'
        request = event['request']
        if (funding and event['seq'] == funding['seq'] and request['op'] == 'ACTIVATE'
                and request['body'].get('receipt') == task['rid'] and s2.h(request) == funding['request']):
            kind = 'FUNDING_EXHAUSTED'
            refs[kind] = ref
        records.append(dict(event_ref=ref, parent_refs=list(event['parents']),
                            event_kind=kind, subject_ref=_subject(event)))
        head = ref
    c.need(head is not None, 'evaluation requires an authority event prefix')
    frontier_ref = head
    if deadline_at is not None:
        ref = h(['DEADLINE_OBSERVATION', task['rid'], head, deadline_at])
        records.append(dict(event_ref=ref, parent_refs=[head], event_kind='DEADLINE_REACHED',
                            subject_ref=dict(tag='RECEIPT', id=task['rid'])))
        refs['DEADLINE_REACHED'] = ref
        frontier_ref = ref
    return dict(event_records=records, frontier_event_ref=frontier_ref), refs


def resolve(task, events, now):
    """Return (condition or None, observation, frontier digest) for P6/P7."""
    deadline = now >= task['bundle']['receipt']['execution']['deadline']
    frontier, refs = frontier_view(task, events, now if deadline else None)
    observation = {}
    if task['audit'].get('funding_boundary') is not None:
        # A missing event reference stays in the observation and fails closed.
        observation['funding_event_ref'] = refs.get('FUNDING_EXHAUSTED', s2.ZERO)
    if deadline:
        observation['deadline_event_ref'] = refs['DEADLINE_REACHED']
    resolved = admission.resolve_boundary(observation, frontier, task['rid'])
    return resolved, observation, h(frontier)
