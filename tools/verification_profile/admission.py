"""Local EA and boundary projection checks for normalized Decision inputs."""
from graphlib import CycleError, TopologicalSorter

from tools.verification_profile import codec as c
from tools.verification_profile.event_frontier import ancestors

INVALIDATING = 'VERIFICATION_INVALIDATING'
FUNDING = 'BUDGET_EXHAUSTED'
DEADLINE = 'DEADLINE_REACHED'


def within_funding_cap(committed, increment, cap):
    """Compare nonnegative uint64 amounts without overflowing their sum."""
    for amount in (committed, increment, cap):
        c.need(type(amount) is int and 0 <= amount < 2**64, 'funding amount outside uint64')
    return committed <= cap and increment <= cap - committed


def evidence_admissible(received_at, deadline, committed, increment, cap, validation_passed):
    """Check EA-1 on authority-projected facts; obtain no time or money itself."""
    for instant in (received_at, deadline):
        c.need(type(instant) is int and -(2**63) <= instant < 2**63, 'Instant outside int64')
    c.need(type(validation_passed) is bool, 'explicit validation result required')
    affordable = within_funding_cap(committed, increment, cap)
    return validation_passed and received_at < deadline and affordable


def resolve_boundary(observation, frontier, receipt_id):
    """Project P6/P7 from a supplied, authenticated frontier's decoded fields.

    Bundle authentication, the frozen funding contract and authoritative
    production of boundary records are checked by the caller.
    """
    kinds = {'funding_event_ref': 'FUNDING_EXHAUSTED', 'deadline_event_ref': DEADLINE}
    try:
        c.need(type(observation) is dict and set(observation) <= kinds.keys(), 'boundary fields')
        records = frontier['event_records']
        events = {c.encode(event['event_ref']): event for event in records}
        c.need(len(events) == len(records), 'duplicate event reference')
        parents = {}
        for ref, event in events.items():
            refs = [c.encode(parent) for parent in event['parent_refs']]
            c.need(len(refs) == len(set(refs)) and set(refs) <= events.keys(),
                   'unresolved or duplicate parent')
            parents[ref] = refs
        tuple(TopologicalSorter(parents).static_order())
        visible = ancestors(events, c.encode(frontier['frontier_event_ref']))
        refs = {}
        subject = c.encode(dict(tag='RECEIPT', id=receipt_id))
        for key, value in observation.items():
            ref = c.encode(value)
            c.need(ref in visible, 'boundary outside visible frontier')
            event = events[ref]
            c.need(event['event_kind'] == kinds[key] and c.encode(event['subject_ref']) == subject,
                   'boundary kind or Receipt mismatch')
            refs[key] = ref
    except (c.CodecError, KeyError, TypeError, CycleError):
        return INVALIDATING

    funding = refs.get('funding_event_ref')
    deadline = refs.get('deadline_event_ref')
    if funding is None:
        return DEADLINE if deadline is not None else None
    if deadline is not None and deadline in ancestors(events, funding):
        return DEADLINE
    return FUNDING
