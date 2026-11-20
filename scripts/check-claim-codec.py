# SPDX-License-Identifier: Apache-2.0
"""Build independent Rust codec and compare raw bytes, views, hashes and rejection.

No downloaded packages. Golden bytes are checked independently of their JSON views.
Writes a report only if --report is explicitly supplied.
"""

if not __debug__:
    raise SystemExit('assert-based validation requires Python without -O/PYTHONOPTIMIZE')

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unicodedata
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.verification_profile import codec as c

DISABLED_SHA_CASES = frozenset({'template-wrong-digest', 'chain-claim-digest',
                                'chain-import-digest', 'chain-payload', 'chain-object-digest', 'chain-ref-digest'})

def run():
    """Compare independent Rust results with fixed vectors and Python outputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    vectors = json.loads((ROOT / 'tests/verification_profile/codec/vectors.json').read_text())['vectors']
    requests = []
    expected = []
    labels = []
    counts = {}

    def add(group, label, mode, wire, want):
        requests.append(mode + '\t' + wire)
        expected.append(want)
        labels.append(label)
        counts[group] = counts.get(group, 0) + 1

    def raw_case(group, label, kind, raw):
        try:
            want = c.inspect(kind, raw)
        except c.CodecError:
            want = None
        add(group, label, kind, raw.hex(), want)
    for v in vectors:
        raw = bytes.fromhex(v['cbor_hex'])
        want = None
        if v['id'] in DISABLED_SHA_CASES:
            want = c.inspect(v['kind'], raw)
            assert want['sha_consistency_policy'] == 'DISABLED'
        elif v['valid']:
            want = {k: v[k] for k in ('cbor_hex', 'schema_view', 'digest_hex') if k in v}
            want['sha_consistency_policy'] = c.SHA_CONSISTENCY_STATUS
            assert c.inspect(v['kind'], raw) == want, v['id']
            assert c.from_view_json(v['kind'], json.dumps(v['schema_view'])) == raw, v['id']
            add('golden_views', v['id'], 'view-' + v['kind'], json.dumps(v['schema_view'], ensure_ascii=True), want)
        else:
            try:
                c.inspect(v['kind'], raw)
            except c.CodecError:
                pass
            else:
                raise AssertionError(v['id'])
        add('golden_raw', v['id'], v['kind'], raw.hex(), want)

    def fixture(name):
        return c.decode(bytes.fromhex(next((v['cbor_hex'] for v in vectors if v['id'] == name))))
    base = fixture('chain')
    for label, edit in [('identity', lambda t: t['header'].update(id='acl.ct.other')), ('version', lambda t: t['header'].update(version=[2, 1, 0])), ('text', lambda t: t.update(normative_text='Changed.')), ('advisory', lambda t: t.update(translations=[]))]:
        chain = copy.deepcopy(base)
        edit(chain['template'])
        h = chain['template']['header']
        h['digest'] = c.template_digest(chain['template'])
        raw_case('binding_mutations', label + '-stale', 'chain', c.encode(chain))
        chain['claim_input'][0] = {k: h[k] for k in ('id', 'version', 'digest')}
        chain['rendered_claim_digest'] = c.claim_digest(chain['claim_input'])
        raw_case('binding_mutations', label + '-rebound', 'chain', c.encode(chain))
    rng = random.Random(20261023)
    for i in range(200):
        for kind, n in [('uint', rng.randrange(2 ** 64)), ('int', rng.randrange(-2 ** 63, 2 ** 63))]:
            raw_case('integer_grid', f'{kind}-{i}', kind, c.encode(n))
    unicode_cases = {'', 'é', '中', '😀', '가', '각', '가', '각'}
    for cp in range(1114112):
        ch = chr(cp)
        decomp = unicodedata.decomposition(ch)
        if decomp and (not decomp.startswith('<')):
            unicode_cases.add(ch)
            unicode_cases.add(''.join((chr(int(x, 16)) for x in decomp.split())))
        if unicodedata.combining(ch):
            unicode_cases.add('a' + ch + '̀')
    for i, t in enumerate(sorted(unicode_cases)):
        b = t.encode('utf-8')
        raw = c.head(3, len(b)) + b
        raw_case('unicode', f'unicode-{i}', 'text', raw)
    chain_raw = c.encode(base)
    for i in range(len(chain_raw)):
        raw_case('truncations', f'truncate-{i}', 'chain', chain_raw[:i])
    for i in range(400):
        raw = bytearray(chain_raw)
        raw[rng.randrange(len(raw))] ^= rng.randrange(1, 256)
        raw_case('byte_mutations', f'mutate-{i}', 'chain', bytes(raw))
    for i in range(800):
        raw_case('random_bytes', f'random-{i}', 'uint', rng.randbytes(rng.randrange(0, 40)))
    view_bad = [('uint', '01'), ('uint', '+1'), ('uint', '-0'), ('uint', str(2 ** 64)), ('uint', True), ('int', str(-2 ** 63 - 1)), ('bytes', 'AB'), ('digest', '00'), ('text', 'é'), ('text', '\ud800'), ('rational', ['2', '4']), ('version-range', {'min_inclusive': ['1', '0', '0'], 'max_exclusive': None}), ('template', {})]
    for i, (kind, view) in enumerate(view_bad):
        try:
            c.from_view(kind, view)
        except c.CodecError:
            pass
        else:
            raise AssertionError((kind, view))
        add('bad_views', f'view-{i}', 'view-' + kind, json.dumps(view), None)
    for raw in ['{"min_inclusive":["1","0","0"],"min_inclusive":["2","0","0"]}', '{"min_inclusive":["1","0","0"],}', 'null', 'NaN']:
        try:
            c.from_view_json('version-range', raw)
        except c.CodecError:
            pass
        else:
            raise AssertionError(raw)
        add('bad_json', raw, 'view-version-range', raw, None)
    for i, n in enumerate([0, 1, 3, 55, 56, 63, 64, 65, 127, 128, 129, 1000000]):
        raw = b'a' * n
        want = hashlib.sha256(raw).hexdigest()
        add('sha256', f'sha-{n}', 'sha256', raw.hex(), want)
    add('sha256', 'sha-abc', 'sha256', '616263', 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
    openssl_checks = 0
    for kind in ['template', 'claim']:
        obj = fixture(kind)
        payload = c.encode(c.content_map(obj) if kind == 'template' else obj)
        tag = (c.TEMPLATE_TAG if kind == 'template' else c.CLAIM_TAG).encode()
        result = subprocess.run(['openssl', 'dgst', '-sha256', '-binary'], input=bytes([len(tag)]) + tag + payload, capture_output=True, check=True)
        expected_digest = next((v['digest_hex'] for v in vectors if v['id'] == kind))
        assert result.stdout.hex() == expected_digest
        openssl_checks += 1
    with tempfile.TemporaryDirectory(prefix='aclt-codec-') as tmp:
        binary = Path(tmp) / 'codec'
        subprocess.run(['rustc', '--edition=2021', '-D', 'warnings', '-C', 'overflow-checks=yes', '-O', str(ROOT / 'tools/verification_profile/rust/main.rs'), '-o', str(binary)], check=True)
        result = subprocess.run([str(binary)], input='\n'.join(requests) + '\n', text=True, capture_output=True, check=True, timeout=120)
        lines = result.stdout.splitlines()
        assert len(lines) == len(requests), (len(lines), len(requests), result.stderr)
        for label, line, want in zip(labels, lines, expected):
            actual = json.loads(line)
            if want is None:
                assert isinstance(actual, dict) and 'error' in actual, (label, actual)
            else:
                assert actual == want, (label, actual, want)
    report = {'status': 'PASS', 'slice': 'claim-codec-candidate-1', 'seed': 20261023, 'unicode_version': unicodedata.unidata_version, 'cross_language_cases': len(requests), 'groups': counts, 'openssl_digest_generation_cases': openssl_checks, 'sha_consistency_policy': c.SHA_CONSISTENCY_STATUS, 'disabled_sha_cases': sorted(DISABLED_SHA_CASES), 'production_admission': False, 'rust_version': subprocess.check_output(['rustc', '--version'], text=True).strip(), 'python_version': sys.version.split()[0]}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False))
if __name__ == '__main__':
    run()
