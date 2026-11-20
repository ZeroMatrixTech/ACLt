"""Local Phase B no-snapshot guard over normalized, verified bundle inputs."""
from tools.verification_profile import codec as c
from tools.verification_profile.event_frontier import ancestors

METHODS = {'DIRECT_VERIFIED', 'PROOF_VERIFIED', 'REEXEC_AUDIT_ONLY'}
TAG = 'ROUND_TRANSITION_NO_SNAPSHOT'
STARTED = 'VERIFICATION_STARTED'
COMMITTED = 'VERIFICATION_TERMINAL_COMMITTED'
EDGES = {
    ('PRE_FREEZE', 'RUNNING'),
    ('RUNNING', 'RUNNING'),
    ('RUNNING', 'TERMINAL'),
    ('PRE_FREEZE', 'TERMINAL'),
}


def validate_no_snapshot_round(method, receipt_id, profile_ref, payload, frontier):
    """Check NS-1–NS-3 for the new tag after EF and outer Receipt binding validation.

    This pure guard takes the method from the bound Profile and a validated
    frontier projection. It has no authority to authenticate event sources,
    create events or commit a Decision.
    """
    c.need(type(method) is str and method in METHODS, 'method requires another Phase B path')
    c.need(type(payload) is dict and payload.get('tag') == TAG, 'no-snapshot payload tag')
    c.need({'tag', 'transition'} <= set(payload) <= {'tag', 'transition', 'transition_event_ref'},
           'no-snapshot payload fields')
    transition = payload['transition']
    c.need(type(transition) is dict and set(transition) == {'prior_round_state', 'proposed_round_state'},
           'no-snapshot transition fields')
    before = transition['prior_round_state']
    after = transition['proposed_round_state']
    for state in (before, after):
        c.need(type(state) is dict and set(state) == {'round_stage', 'bound_profile_ref'},
               'no-snapshot state fields')
        c.need(type(state['round_stage']) is str, 'round stage type')
        c.need(c.encode(c.reference_identity(state['bound_profile_ref'])) == c.encode(c.reference_identity(profile_ref)), 'bound Profile changed')
    prior, proposed = before['round_stage'], after['round_stage']
    c.need((prior, proposed) in EDGES, 'invalid no-snapshot stage transition')
    c.need(('transition_event_ref' in payload) == (prior != proposed), 'transition event presence')

    events = {c.encode(event['event_ref']): event for event in frontier['event_records']}
    c.need(len(events) == len(frontier['event_records']), 'duplicate event reference')
    visible = ancestors(events, c.encode(frontier['frontier_event_ref']))
    subject = dict(tag='RECEIPT', id=receipt_id)
    starts = [ref for ref in visible if events[ref].get('subject_ref') == subject
              and events[ref]['event_kind'] == STARTED]
    terminals = [ref for ref in visible if events[ref].get('subject_ref') == subject
                 and events[ref]['event_kind'] == COMMITTED]

    if proposed == 'RUNNING':
        c.need(len(starts) == 1 and not terminals, 'running requires one start and no terminal')
        if prior != proposed:
            c.need(c.encode(payload['transition_event_ref']) == starts[0], 'wrong start event')
    else:
        ref = c.encode(payload['transition_event_ref'])
        c.need(terminals == [ref], 'terminal requires one committed Decision event')
        if prior == 'RUNNING':
            c.need(len(starts) == 1 and starts[0] != ref and starts[0] in ancestors(events, ref),
                   'start must causally precede terminal')
        else:
            c.need(not starts, 'pre-start terminal conflicts with recorded start')
