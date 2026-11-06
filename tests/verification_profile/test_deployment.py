import copy
import unittest

from tools.verification_profile import codec as c, deployment as d


class NonMainnetDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.decl = dict(schema_version=1, id='acl.deploy.test', version=[1, 0, 0],
                         network_id='test-lan', genesis=b'g'*32, trust_root=b't'*32,
                         valid_from=10, valid_until=20, method='REEXEC_AUDIT_ONLY',
                         sources={key:dict(id=key, version=[1, 0, 0], digest=b's'*32)
                                  for key in d.SOURCES}, asset='TEST', funding_cap=10,
                         state_effect='TEST_COMMIT_CHECKPOINT')
        self.binding = dict(network_id='test-lan', genesis=b'g'*32,
                            deployment_ref=d.declaration_ref(self.decl))
        self.pin = dict(self.binding, trust_root=b't'*32)

    def check(self, phase='I', **changes):
        args = dict(declaration=self.decl, pin=self.pin, frozen_binding=self.binding,
                    phase_binding=self.binding, evaluation_instant=10, revocation_clear=True,
                    method='REEXEC_AUDIT_ONLY', sources=self.decl['sources'], asset='TEST',
                    authorized_funding=10)
        args.update(changes)
        d.check_nonmainnet_binding(phase, **args)

    def test_all_operational_phases_and_audit_terminals(self):
        for phase in ('I', 'F', 'B'):
            self.check(phase)
        for terminal in d.TERMINALS:
            self.check('D', terminal=terminal)
        for terminal in (None, 'TRUSTED', 'ACCEPT'):
            with self.subTest(terminal=terminal), self.assertRaises(c.CodecError):
                self.check('D', terminal=terminal)

    def test_declaration_mutation_and_cross_deployment_substitution(self):
        for field, value in [('genesis', b'x'*32), ('trust_root', b'x'*32),
                             ('funding_cap', 11), ('version', [1, 0, 1])]:
            with self.subTest(field=field), self.assertRaises(c.CodecError):
                self.check(declaration=dict(self.decl, **{field:value}))
        for binding in (dict(self.binding, network_id='other'),
                        dict(self.binding, genesis=b'x'*32),
                        dict(self.binding, deployment_ref=dict(self.binding['deployment_ref'],tag='MAINNET'))):
            for phase in ('I', 'F', 'B', 'D'):
                with self.subTest(phase=phase), self.assertRaises(c.CodecError):
                    self.check(phase, phase_binding=binding,
                               terminal='EXPIRED' if phase=='D' else None)

    def test_expiry_revocation_source_and_funding_boundaries(self):
        self.check(evaluation_instant=19)
        sources = copy.deepcopy(self.decl['sources'])
        sources['clock']['digest'] = b'x'*32
        for changes in (dict(evaluation_instant=9), dict(evaluation_instant=20),
                        dict(revocation_clear=None), dict(revocation_clear=False),
                        dict(pin=None), dict(sources=sources), dict(authorized_funding=11),
                        dict(asset='OTHER'), dict(method='REEXEC_BOUNDED')):
            with self.subTest(changes=changes), self.assertRaises(c.CodecError):
                self.check(**changes)
