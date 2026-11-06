"""Local verification of a normalized non-mainnet audit deployment binding."""
from tools.verification_profile import admission, codec as c

TAG = 'NONMAINNET_TEST'
DOMAIN = 'ACLt/P0-1/NonMainnetDeployment/1'
SOURCES = {'clock', 'log_backend', 'result_validator', 'rpr_entry',
           'execution_capability', 'assumption_reducer', 'execution_closure'}
FIELDS = {'schema_version', 'id', 'version', 'network_id', 'genesis', 'trust_root',
          'valid_from', 'valid_until', 'method', 'sources', 'asset', 'funding_cap',
          'state_effect'}
TERMINALS = ('UNRESOLVED', 'EXPIRED', 'FAILED', 'FUNDING_EXHAUSTED')


def declaration_ref(declaration):
    return dict(tag=TAG, ref=dict(id=declaration['id'], version=declaration['version'],
                                  digest=c.domain_hash(DOMAIN, c.encode(declaration))))


def check_nonmainnet_binding(phase, declaration, pin, frozen_binding, phase_binding, *,
                             evaluation_instant, revocation_clear, method, sources,
                             asset, authorized_funding, terminal=None):
    """Check explicit facts after source authentication and outer phase decoding.

    Pin, time and revocation inputs come from the trusted deployment resolver.
    The caller owns signature, checkpoint and actual source-use verification.
    """
    c.need(phase in ('I', 'F', 'B', 'D'), 'deployment phase')
    c.need(type(declaration) is dict and set(declaration) == FIELDS and
           type(declaration['schema_version']) is int and declaration['schema_version'] == 1,
           'deployment declaration fields or version')
    for name in ('id', 'network_id', 'asset'):
        c.need(type(declaration[name]) is str and declaration[name], 'deployment text field')
    version = declaration['version']
    c.need(type(version) is list and len(version) == 3 and
           all(type(x) is int and 0 <= x < 2**64 for x in version), 'deployment SemVer')
    for name in ('genesis', 'trust_root'):
        c.need(type(declaration[name]) is bytes and len(declaration[name]) == 32, 'deployment pin digest')
    ref = declaration_ref(declaration)
    context = dict(network_id=declaration['network_id'], genesis=declaration['genesis'],
                   deployment_ref=ref)
    c.need(c.encode(pin) == c.encode(dict(context, trust_root=declaration['trust_root'])),
           'deployment does not match out-of-band pin')
    c.need(c.encode(frozen_binding) == c.encode(phase_binding) == c.encode(context),
           'deployment binding changed')
    start, end = declaration['valid_from'], declaration['valid_until']
    c.need(all(type(t) is int and -(2**63) <= t < 2**63
               for t in (start, end, evaluation_instant)) and start <= evaluation_instant < end,
           'deployment validity window')
    c.need(revocation_clear is True, 'deployment revoked or revocation status unavailable')
    c.need(method == declaration['method'] == 'REEXEC_AUDIT_ONLY' and
           declaration['state_effect'] == 'TEST_COMMIT_CHECKPOINT', 'deployment scope')
    declared_sources = declaration['sources']
    c.need(type(declared_sources) is dict and set(declared_sources) == SOURCES,
           'deployment sources')
    for source in declared_sources.values():
        c.need(type(source) is dict and set(source) == {'id', 'version', 'digest'} and
               type(source['id']) is str and source['id'] and
               type(source['version']) is list and len(source['version']) == 3 and
               all(type(x) is int and 0 <= x < 2**64 for x in source['version']) and
               type(source['digest']) is bytes and len(source['digest']) == 32,
               'deployment source reference')
    c.need(c.encode(sources) == c.encode(declared_sources), 'deployment source binding changed')
    c.need(asset == declaration['asset'] and
           admission.within_funding_cap(0, authorized_funding, declaration['funding_cap']),
           'deployment funding scope')
    c.need((phase == 'D' and terminal in TERMINALS) or (phase != 'D' and terminal is None),
           'non-mainnet terminal or phase')
