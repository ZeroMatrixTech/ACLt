# SPDX-License-Identifier: Apache-2.0
"""Explicit physical dual-host Work 3 suite and offline retained-evidence verification."""
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RECOVERY_LABELS = ['lost-pay-without-reply', 'lost-refund-without-reply', 'before-commit-baseline',
                   'before-commit-rolled-back', 'after-commit-before-recovery', 'race-before-release',
                   'saved-outcome-not-submitted', 'permit-only-held', 'final']
COMPONENTS = {
    'reservation': ('aclt-funding-reservation', 22, 12, 5),
    'fixed': ('aclt-fixed-settlement', 26, 12, 6),
    'recovery': ('aclt-settlement-recovery', 16, 14, 6),
}
DEPENDENCIES = ['aclt-task-authorization', 'aclt-task-commitment', 'aclt-rir-stats-probe']
DEPLOYED = {
    'reservation': [COMPONENTS['reservation'][0], *DEPENDENCIES],
    'fixed': [COMPONENTS['fixed'][0], *DEPENDENCIES],
    'recovery': [COMPONENTS['recovery'][0], COMPONENTS['fixed'][0], *DEPENDENCIES],
}


def sha(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('regular source/evidence file required: ' + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    with path.open('x') as f:
        json.dump(value, f, indent=2)
        f.write('\n')


def retained(root, name):
    p = Path(name)
    if p.is_absolute() or '..' in p.parts or p.as_posix() != name:
        raise ValueError('invalid retained relative path')
    path = root / p
    if any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError('symlink evidence path')
    sha(path)
    return path


def inventory(root):
    files = {}
    for p in sorted(root.rglob('*')):
        rel = p.relative_to(root)
        if {'private', '__pycache__'}.intersection(rel.parts) or p.name in {'public-inventory.json', 'suite.json', 'retained-pins.json'}:
            continue
        if p.is_symlink():
            raise ValueError('symlink evidence path')
        if p.is_file():
            files[rel.as_posix()] = sha(p)
    return files


def sources():
    paths = [ROOT / 'scripts/funding-work3.py', ROOT / 'tests/workflow/test_funding_work3.py']
    for name in [*(c[0] for c in COMPONENTS.values()), *DEPENDENCIES]:
        paths += [p for p in (ROOT / 'experiments' / name).rglob('*')
                  if p.is_file() and '__pycache__' not in p.parts]
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths)}


def source_check(root):
    lock = json.loads(retained(root, 'source-lock.json').read_text())
    if lock != sources():
        raise ValueError('suite source inventory/current source drift')
    for component, names in DEPLOYED.items():
        deployed = json.loads(retained(root, component + '/source-lock.json').read_text())
        expected = {n: h for n, h in lock.items() if any(n.startswith('experiments/' + e + '/') for e in names)}
        if deployed != expected:
            raise ValueError('component deployed source drift: ' + component)
    return lock


def check_pins(pins):
    if type(pins) is not dict or set(pins) != set(COMPONENTS):
        raise ValueError('all caller-retained component pins required')
    for component in COMPONENTS:
        p = pins[component]
        labels = set(RECOVERY_LABELS) if component == 'recovery' else {'final'}
        if type(p) is not dict or set(p) != {'public_digest', 'checkpoints'} or type(p['checkpoints']) is not dict or set(p['checkpoints']) != labels:
            raise ValueError('closed caller-retained checkpoint inventory required')
        for digest in [p['public_digest'], *p['checkpoints'].values()]:
            if type(digest) is not str or re.fullmatch('[0-9a-f]{64}', digest) is None:
                raise ValueError('invalid retained digest')


def command(argv, log):
    with log.open('xb') as f:
        subprocess.run([str(x) for x in argv], stdout=f, stderr=subprocess.STDOUT, check=True, timeout=900)


def continuity(root):
    # Only decode/bind/check retained bytes; no guest or live ledger imports.
    sys.path.insert(0, str(ROOT / 'experiments/aclt-task-commitment'))
    from commitment import bind, load, task_id, tagged
    from cbor_codec import decode, encode
    cases = [root / 'reservation/A/normal', root / 'fixed/A/success', root / 'recovery/A/lost-pay']
    commits = [(c / 'task.cbor').read_bytes() for c in cases]
    if len(set(commits)) != 1:
        raise ValueError('normal frozen task commitment drift')
    task = load(commits[0]); tid = task_id(commits[0])
    for case, raw in zip(cases, commits):
        bind(raw, tid, (case / 'artifact.cbor').read_bytes(), [(case / 'input.bin').read_bytes()])
    for name in ['artifact.cbor', 'input.bin']:
        if len({(c / name).read_bytes() for c in cases}) != 1:
            raise ValueError('cross-slice actual byte drift: ' + name)
    policies = [(c / 'policy.cbor').read_bytes() for c in cases]
    objects = [decode(p) for p in policies]
    if [p['schema_id'] for p in objects] != ['aclt.exp.funding-policy@1', 'aclt.exp.funding-policy@2', 'aclt.exp.funding-policy@2'] or policies[1] != policies[2]:
        raise ValueError('declared v1-to-v2 policy continuity drift')
    for field in ['task', 'requester', 'asset', 'decimal_places', 'source', 'authorized_cap', 'success_fee', 'settlement_rule', 'refund_rule', 'pending_rule']:
        if any(p[field] != objects[0][field] for p in objects[1:]):
            raise ValueError('shared funding policy field drift: ' + field)
    reports = []
    for component, name in [('fixed', 'success'), ('recovery', 'lost-pay')]:
        for side in ['A', 'B']:
            reports.append(decode((root / component / side / name / 'state/outcome.cbor').read_bytes()))
    results = [encode(p['result']) for p in reports]
    if len(set(results)) != 1 or any(p['task'].hex() != tid or p['outcome_digest'] != tagged('ACLt/RIR-0/ExecutionOutcome/1', results[0]) for p in reports):
        raise ValueError('normal two-host outcome continuity drift')
    result = reports[0]['result']
    return {'experimental_task_id': tid, 'rir_digest': task['rir_digest'].hex(),
            'profile_digest': task['execution_profile_digest'].hex(), 'execution_limits': task['execution_limits'],
            'input_sha256': sha(cases[0] / 'input.bin'), 'artifact_sha256': sha(cases[0] / 'artifact.cbor'),
            'policy_schemas': [p['schema_id'] for p in objects], 'cap': objects[0]['authorized_cap'],
            'fee': objects[0]['success_fee'], 'payee_bound_within_each_deployment': True,
            'normal_outcome_digest': reports[0]['outcome_digest'].hex(), 'normal_outcome': result['outcome'],
            'normal_gas': result['gas_used'], 'normal_output_bytes': len(result['output']),
            'scope': 'same retained fixture/reference implementation; distinct authority/reservation/entitlement scopes, no merged funds'}


def verify(root, pins_path):
    root = root.resolve(); lock = source_check(root)
    saved = json.loads(retained(root, 'public-inventory.json').read_text())
    if not saved or saved != inventory(root):
        raise ValueError('retained public evidence changed or missing')
    for name, digest in saved.items():
        if sha(retained(root, name)) != digest:
            raise ValueError('retained evidence digest mismatch: ' + name)
    pins = json.loads(pins_path.read_text()); check_pins(pins)
    reductions = {}; scenarios = {}; regression = {}
    with tempfile.TemporaryDirectory(prefix='aclt-work3-verify-') as temp:
        temp = Path(temp)
        for component, (experiment, methods, count, negatives) in COMPONENTS.items():
            report = json.loads(retained(root, component + '/report.json').read_text())
            if report['status'] != 'PASS' or report['scenarios'] != count or len(report['records']) != count or any(x['status'] != 'PASS' for x in report['records']):
                raise ValueError('component matrix incomplete: ' + component)
            if len(report['negative_controls']) != negatives or any(x['status'] != 'REJECTED' for x in report['negative_controls']):
                raise ValueError('component tamper controls incomplete: ' + component)
            for file in [component + '-local-unit.log', component + '/remote-unit.log']:
                log = retained(root, file).read_text()
                if re.findall(r'^Ran (\d+) tests? in ', log, re.M) != [str(methods)] or not log.rstrip().endswith('OK'):
                    raise ValueError('component regression evidence incomplete: ' + file)
            scenarios[component] = {'scenarios': count, 'negative_controls': negatives}
            regression[component] = {'local_methods': methods, 'remote_methods': methods}
            labels = RECOVERY_LABELS if component == 'recovery' else ['final']
            if component == 'recovery' and {x['label'] for x in report['checkpoints']} != set(labels):
                raise ValueError('recovery checkpoint inventory incomplete')
            reductions[component] = {}
            for label in labels:
                export = label + '-export.json' if component == 'recovery' else 'ledger-export.json'
                anchor = label + '-anchor.cbor' if component == 'recovery' else 'checkpoint.cbor'
                previous = label + '-reduced.json' if component == 'recovery' else 'reduced.json'
                audit = 'aclt-funding-reservation' if component == 'reservation' else 'aclt-fixed-settlement'
                dest = temp / (component + '-' + label + '.json')
                command([sys.executable, '-B', ROOT / 'experiments' / audit / 'audit.py',
                         '--bundle', root / component / export, '--anchor', root / component / anchor,
                         '--public', root / component / 'A/issuer.pub', '--public-digest', pins[component]['public_digest'],
                         '--anchor-digest', pins[component]['checkpoints'][label], '--report', dest], temp / (component + '-' + label + '.log'))
                reduced = json.loads(dest.read_text())
                if reduced != json.loads(retained(root, component + '/' + previous).read_text()):
                    raise ValueError('saved reducer result differs: ' + component + '/' + label)
                reductions[component][label] = reduced
    expected = {'reservation': (18, 50, 250), 'fixed': (30, 900, 100), 'recovery': (61, 900, 100)}
    for component, counts in expected.items():
        r = reductions[component]['final']
        if (r['events'], r['available'], r['reserved']) != counts:
            raise ValueError('final accounting scope incomplete: ' + component)
    for component, allocation in [('fixed', (30, 170, 2)), ('recovery', (150, 450, 6))]:
        r = reductions[component]['final']
        if (r['paid'], r['refunded'], r['settlements']) != allocation:
            raise ValueError('final allocations incomplete: ' + component)
    for suffix in ['export.json', 'anchor.cbor']:
        if (root / 'recovery' / ('before-commit-baseline-' + suffix)).read_bytes() != (root / 'recovery' / ('before-commit-rolled-back-' + suffix)).read_bytes():
            raise ValueError('precommit rollback differs from baseline')
    return {'status': 'PASS', 'work_item': 'FUNDING-WORK3',
            'scope': 'bounded prefunded test-asset reserve, fixed comparison/allocation and process recovery',
            'evidence_action': 'offline rehash/byte comparison/reduction; no network, guest, compiler or live ledger mutation',
            'source_files': len(lock), 'source_sha256': lock, 'public_inventory_sha256': sha(root / 'public-inventory.json'),
            'caller_pins': pins, 'regressions': regression, 'scenarios': scenarios,
            'checkpoints_reduced': sum(len(v) for v in reductions.values()),
            'continuity': continuity(root), 'reductions': reductions,
            'gate_change': False, 'OQ_10_status': 'OPEN',
            'limitations': ['independent test deployments and supplies, never aggregate their balances or count them as one production task',
                            'v1 reservation policy and v2 comparison policy are explicit versions; old stores/entries are not migrated',
                            'same Python reference implementation and accepted DUALHOST-SSH-1 physical-host assumption',
                            'honest pinned hosts/storage/config, issuer/enrollment and single non-rollback/non-forked authority',
                            'hash inventory is integrity, not authenticated provenance; retain key/checkpoint digests independently',
                            'historical checkpoint validity is not freshness, rollback protection, failover or power-cut proof',
                            'no formal objects/TRUSTED/full terminal-fault-source matrix/real assets or external payment assurance']}


def run(args):
    out = args.output.resolve(); remote = args.remote_root.rstrip('/')
    if out.is_relative_to(ROOT) or not remote.startswith('/') or remote == '/' or '..' in Path(remote).parts:
        raise ValueError('fresh output outside repository and explicit absolute remote root required')
    if args.peer.startswith('-') or not args.peer.strip() or ipaddress.ip_address(args.a_host).is_loopback:
        raise ValueError('explicit SSH peer and real LAN A address required')
    out.mkdir(parents=True, exist_ok=False)
    ssh = ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=8', args.peer]
    try:
        dump(out / 'source-lock.json', sources())
        command([*ssh, shlex.join(['python3', '-c', 'from pathlib import Path; Path(' + repr(remote) + ').mkdir(parents=True,exist_ok=False)'])], out / 'remote-root.log')
        for component, (experiment, _, _, _) in COMPONENTS.items():
            command([sys.executable, '-B', '-W', 'error::ResourceWarning', '-m', 'unittest', 'discover',
                     '-s', ROOT / 'experiments' / experiment / 'tests', '-v'], out / (component + '-local-unit.log'))
            print('Running physical dual-host ' + component + ' matrix', flush=True)
            command([sys.executable, '-B', ROOT / 'experiments' / experiment / 'dualhost.py',
                     '--peer', args.peer, '--a-host', args.a_host, '--remote-root', remote + '/' + component,
                     '--output', out / component], out / (component + '-matrix.log'))
        pins = {}
        for component in COMPONENTS:
            r = json.loads((out / component / 'report.json').read_text())
            cps = {c['label']: c['anchor_digest'] for c in r['checkpoints']} if component == 'recovery' else {'final': r['anchor_digest']}
            pins[component] = {'public_digest': r['public_digest'], 'checkpoints': cps}
        check_pins(pins); dump(out / 'retained-pins.json', pins)
        dump(out / 'public-inventory.json', inventory(out))
        result = verify(out, out / 'retained-pins.json')
        result['execution_action'] = 'fresh independent two-host runs of all three slices, then offline verification'
        dump(out / 'suite.json', result)
        print('PASS: three fresh dual-host matrices, 11 checkpoint reductions and frozen-byte/policy continuity', flush=True)
    except BaseException as exc:
        if not (out / 'suite.json').exists(): dump(out / 'suite.json', {'status': 'FAIL', 'error': type(exc).__name__ + ': ' + str(exc)})
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='command', required=True)
    r = sub.add_parser('run', help='Explicit real LAN run in new independent test directories')
    for name in ['peer', 'a-host', 'remote-root']: r.add_argument('--' + name, required=True)
    r.add_argument('--output', type=Path, required=True)
    v = sub.add_parser('verify', help='Read-only retained source/evidence checks; no SSH or guest')
    for name in ['evidence', 'pins', 'report']: v.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    if a.command == 'run': run(a); return
    if a.report.exists() or a.report.resolve().is_relative_to(a.evidence.resolve()):
        p.error('new report outside retained evidence required')
    dump(a.report, verify(a.evidence, a.pins))
    print('PASS: retained Work 3 evidence verified without guest/network execution')


if __name__ == '__main__': main()
