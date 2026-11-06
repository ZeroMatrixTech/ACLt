"""Causal traversal over supplied event records."""
from tools.verification_profile import codec as c


def ancestors(events, root):
    """Include root and follow only parent links supplied by the frontier."""
    seen = set()
    pending = [root]
    while pending:
        ref = pending.pop()
        if ref not in seen:
            c.need(ref in events, 'unresolved event reference')
            seen.add(ref)
            pending.extend(c.encode(parent) for parent in events[ref]['parent_refs'])
    return seen
