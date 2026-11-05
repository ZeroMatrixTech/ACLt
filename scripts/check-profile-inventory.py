#!/usr/bin/env python3
"""Check inventory traceability, not semantic conformance or test execution."""

if not __debug__:
    raise SystemExit('assert-based validation requires Python without -O/PYTHONOPTIMIZE')

import ast
import collections
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
cov = json.loads((root / 'schemas/verification-profile/coverage.json').read_text())
inv = json.loads((root / cov['inventory']).read_text())
spec = (root / cov['normative_source']).read_text()
def rows(start, end, prefix):
    return [[c.strip() for c in line.strip('|').split('|')]
            for line in spec.split(start, 1)[1].split(end, 1)[0].splitlines()
            if line.startswith(prefix)]
expected = rows('### 13.2 校验清单', '## 14.', '| SV-')
assert len(expected) == len(inv['rules']) == 127
assert len({r['id'] for r in inv['rules']}) == 127
registered = [ident for group in ('implemented', 'partial') for ids in cov[group].values() for ident in ids]
assert len(registered) == len(set(registered))
assert set(registered) <= {r['id'] for r in inv['rules'] if r['kind'] == 'A'}
for r, c in zip(inv['rules'], expected):
    assert [r['id'], r['phase'], r['layer'], r['requirement'], r['kind']] == [c[0], c[1].replace('*',''), c[2], c[3], c[4].replace('*','')]
    status = 'NOT_IMPLEMENTED' if r['kind'] == 'A' else {'SV-15':'OBSOLETE', 'SV-40':'DEFERRED'}.get(r['id'], 'TYPE_B')
    for group in ('implemented', 'partial'):
        if r['id'] in cov[group].get(r['layer'], []): status = group.upper()
    assert r['status'] == status and r['gap'], r['id']
    if status in ('IMPLEMENTED', 'PARTIAL'): assert r['implementation'] and r['tests']
    for ref in r['implementation'] + r['tests']:
        path, symbol = ref.split('#')
        assert any(isinstance(n, ast.FunctionDef) and n.name == symbol for n in ast.walk(ast.parse((root / path).read_text()))), ref
assert sum(r['kind'] == 'A' for r in inv['rules']) == 119
assert sorted(r['id'] for r in inv['rules'] if r['kind'] == 'B') == sorted(cov['type_b_excluded_from_p0_1b_closure'])
assert [r['id'] for r in inv['rules'] if r['status'] == 'DEFERRED'] == cov['deferred']
expected = rows('### 17.4 摘要与域分离', '### 17.5A', '| `')
assert len(expected) == len(inv['digests']) == 18
assert len({d['owner'] for d in inv['digests']}) == len({d['tag'] for d in inv['digests']}) == 18
for d, c in zip(inv['digests'], expected):
    assert [d['name'], d['tag'], d['input'], d['owner'], d['layer']] == [c[0], c[1].strip('`'), c[2], c[3].replace('*',''), c[4]]
    owner = next(r for r in inv['rules'] if r['id'] == d['owner'])
    assert owner['kind'] == 'A' and owner['layer'] == 'L2' and owner['status'] == d['status'] and d['gap']
print(json.dumps(dict(rules=127, type_a=dict(collections.Counter(r['status'] for r in inv['rules'] if r['kind']=='A')), digests=18)))
