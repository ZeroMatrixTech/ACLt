# SPDX-License-Identifier: Apache-2.0
"""Opt-in physical dual-host Work 2 suite, or offline retained-evidence verification."""
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ['aclt-task-commitment', 'aclt-task-authorization', 'aclt-task-replay', 'aclt-rir-stats-probe']


def sha(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('regular source/evidence file required: ' + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    paths = [ROOT / 'scripts/task-work2.py', ROOT / 'tests/workflow/test_task_work2.py']
    for name in EXPERIMENTS:
        paths += [p for p in (ROOT / 'experiments' / name).rglob('*')
                  if p.is_file() and '__pycache__' not in p.parts]
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths)}


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
    result = {}
    for p in sorted(root.rglob('*')):
        rel = p.relative_to(root)
        if 'private' in rel.parts or '__pycache__' in rel.parts or p.name in {
            'public-inventory.json', 'suite.json', 'retained-pins.json'}:
            continue
        if p.is_symlink():
            raise ValueError('symlink evidence path')
        if p.is_file():
            result[rel.as_posix()] = sha(p)
    return result


def source_check(root):
    lock = json.loads(retained(root, 'source-lock.json').read_text())
    if lock != sources():
        raise ValueError('suite source inventory/current source drift')
    for component, names in [('authorization', EXPERIMENTS[:2] + EXPERIMENTS[3:]),
                             ('replay', EXPERIMENTS)]:
        deployed = json.loads(retained(root, component + '/source-lock.json').read_text())
        expected = {n: h for n, h in lock.items() if any(n.startswith('experiments/' + e + '/') for e in names)}
        if deployed != expected:
            raise ValueError('component deployed source drift: ' + component)
    return lock


def command(argv, log, timeout=900):
    with log.open('xb') as f:
        subprocess.run([str(x) for x in argv], stdout=f, stderr=subprocess.STDOUT,
                       check=True, timeout=timeout)


def verify(root, pins_path):
    """No network, database mutation, matrix rerun or guest execution."""
    root = root.resolve()
    lock = source_check(root)
    saved = json.loads(retained(root, 'public-inventory.json').read_text())
    if not saved or saved != inventory(root):
        raise ValueError('retained public evidence changed or missing')
    for name, digest in saved.items():
        if sha(retained(root, name)) != digest:
            raise ValueError('retained evidence digest mismatch: ' + name)
    pins = json.loads(pins_path.read_text())
    if set(pins) != {'public_digest', 'pending-ack', 'final'}:
        raise ValueError('caller-retained key/checkpoint pins required')
    auth = json.loads(retained(root, 'authorization/report.json').read_text())
    replay = json.loads(retained(root, 'replay/report.json').read_text())
    if auth['status'] != 'PASS' or auth['scenarios'] != 16 or auth['completed_guest_executions'] != 2:
        raise ValueError('authorization matrix incomplete')
    if replay['status'] != 'PASS' or replay['scenarios'] != 12 or len(replay['negative_controls']) != 7:
        raise ValueError('replay matrix incomplete')
    if any(r['status'] != 'PASS' for r in auth['scenario_records'] + replay['records']):
        raise ValueError('scenario failed')
    if any(r['status'] != 'REJECTED' for r in replay['negative_controls']):
        raise ValueError('tamper control accepted')
    # Dedicated subprocesses avoid cross-experiment module aliasing and run only
    # the retained binding checker and independent byte-driven state reducer.
    with tempfile.TemporaryDirectory(prefix='aclt-work2-verify-') as temp:
        temp = Path(temp)
        command([sys.executable, '-B', ROOT / 'experiments/aclt-task-commitment/compare.py',
                 root / 'commitment-A', root / 'commitment-B', '--report', temp / 'binding.json'], temp / 'binding.log')
        binding = json.loads((temp / 'binding.json').read_text())
        reductions = {}
        for label in ['pending-ack', 'final']:
            command([sys.executable, '-B', ROOT / 'experiments/aclt-task-replay/offline.py',
                     '--bundle', root / ('replay/' + label + '-bundle.cbor'),
                     '--anchor', root / ('replay/' + label + '-anchor.cbor'),
                     '--public', root / 'replay/A/issuer.pub', '--public-digest', pins['public_digest'],
                     '--expected-anchor-digest', pins[label], '--report', temp / (label + '.json')], temp / (label + '.log'))
            reductions[label] = json.loads((temp / (label + '.json')).read_text())
            if reductions[label] != json.loads((root / ('replay/' + label + '-reduced.json')).read_text()):
                raise ValueError('saved reducer result differs')
    final = reductions['final']
    if (binding['records'], final['authority_events'], final['worker_events'], final['accepted'], final['consumed']) != (48, 34, 55, 4, 5):
        raise ValueError('incomplete combined evidence')
    if not any(w['accepted'] and not w['acknowledged'] for w in reductions['pending-ack']['workers']):
        raise ValueError('missing accepted/pending ACK checkpoint')
    # Continuity means unchanged runtime/profile/input; separate fixtures/deployments
    # intentionally have distinct task IDs, grants, keys and ledgers.
    sys.path.insert(0, str(ROOT / 'experiments/aclt-task-commitment'))
    from commitment import load
    sample = load((root / 'commitment-A/commitment.cbor').read_bytes())
    for component in ['authorization', 'replay']:
        case = root / component / 'A/normal'
        c = load((case / 'task.cbor').read_bytes())
        for field in ['rir_digest', 'execution_profile_digest', 'execution_limits', 'inputs', 'result_equivalence']:
            if c[field] != sample[field]:
                raise ValueError('cross-slice binding continuity drift: ' + field)
        for name in ['artifact.cbor', 'input.bin']:
            if (case / name).read_bytes() != (root / 'commitment-A' / name).read_bytes():
                raise ValueError('cross-slice actual byte drift: ' + name)
    return {'status': 'PASS', 'work_item': 'TASK-WORK2',
            'scope': 'bounded experimental commitment, authorization and causal submission/ACK replay',
            'evidence_action': 'offline rehash/reduce only; no guest or network execution during verify',
            'source_files': len(lock), 'source_sha256': lock, 'public_inventory_sha256': sha(root / 'public-inventory.json'),
            'caller_pins': pins, 'commitment': binding,
            'authorization': {'scenarios': auth['scenarios'], 'completed_guest_executions': 2,
                              'verification': 'retained matrix assertions and evidence hashes; not independent slice-2 transition reduction'},
            'replay': {'scenarios': replay['scenarios'], 'negative_controls': replay['negative_controls'],
                       'checkpoints': reductions},
            'cross_slice_continuity': ['RIR bytes/digest', 'input bytes/references', 'Profile', 'limits', 'equivalence'],
            'gate_change': False, 'ADR_status': 'PROPOSED',
            'limitations': ['two physical hosts under accepted DUALHOST-SSH-1 assumption',
                            'separate regression deployments, not one shared ledger or formal object migration',
                            'hash inventory is integrity, not authenticated provenance; retain key/checkpoint pins independently',
                            'valid historical anchors do not establish freshness or prevent issuer rollback/equivocation',
                            'honest pinned worker/config/filesystem and single trusted issuer/key/clock/enrollment',
                            'acceptance is not arithmetic correctness, verification verdict/TRUSTED or settlement',
                            'no formal ComputeReceipt/Lease/ExecutionCapability/EventRecord or production conformance']}


def run(args):
    out = args.output.resolve()
    remote = args.remote_root.rstrip('/')
    if out.is_relative_to(ROOT) or not remote.startswith('/') or remote == '/' or '..' in Path(remote).parts:
        raise ValueError('fresh output outside repository and explicit absolute remote root required')
    if args.peer.startswith('-') or not args.peer.strip():
        raise ValueError('explicit SSH peer required')
    if ipaddress.ip_address(args.a_host).is_loopback:
        raise ValueError('real LAN A address required')
    out.mkdir(parents=True, exist_ok=False)
    ssh = ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=8', args.peer]
    scp = ['scp', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=8']
    try:
        dump(out / 'source-lock.json', sources())
        environment = "import json,platform,sqlite3,ssl; print(json.dumps({'hostname':platform.node(),'platform':platform.platform(),'python':platform.python_version(),'sqlite':sqlite3.sqlite_version,'openssl':ssl.OPENSSL_VERSION}))"
        command([sys.executable, '-c', environment], out / 'environment-A.log')
        command([*ssh, shlex.join(['python3', '-c', environment])], out / 'environment-B.log')
        command([*ssh, shlex.join(['python3', '-c', 'from pathlib import Path; Path(' + repr(remote) + ').mkdir(parents=True,exist_ok=False)'])], out / 'remote-root.log')
        for name in EXPERIMENTS[:3]:
            command([sys.executable, '-B', '-W', 'error::ResourceWarning', '-m', 'unittest', 'discover',
                     '-s', ROOT / 'experiments' / name / 'tests', '-v'], out / (name + '-local-unit.log'))
        for component, experiment in [('authorization', 'aclt-task-authorization'), ('replay', 'aclt-task-replay')]:
            print('Running physical dual-host ' + component + ' matrix', flush=True)
            command([sys.executable, '-B', ROOT / 'experiments' / experiment / 'dualhost.py',
                     '--peer', args.peer, '--a-host', args.a_host, '--remote-root', remote + '/' + component,
                     '--output', out / component], out / (component + '-matrix.log'))
        # Replay's source-locked remote deployment includes the unchanged binding probe.
        script = remote + '/replay/experiments/aclt-task-commitment/'
        command([*ssh, shlex.join(['python3', '-B', '-W', 'error::ResourceWarning', '-m', 'unittest',
                                  'discover', '-s', script + 'tests', '-v'])], out / 'commitment-remote-unit.log')
        command([sys.executable, '-B', ROOT / 'experiments/aclt-task-commitment/probe.py', '--output', out / 'commitment-A'], out / 'commitment-A.log')
        command([*ssh, shlex.join(['python3', '-B', script + 'probe.py', '--output', remote + '/commitment-B'])], out / 'commitment-B.log')
        code = 'import tarfile; t=tarfile.open(' + repr(remote + '/commitment-B.tar') + ',"w"); t.add(' + repr(remote + '/commitment-B') + ',arcname="commitment-B"); t.close()'
        command([*ssh, shlex.join(['python3', '-c', code])], out / 'commitment-archive.log')
        command([*scp, args.peer + ':' + remote + '/commitment-B.tar', out / 'commitment-B.tar'], out / 'commitment-collect.log')
        with tarfile.open(out / 'commitment-B.tar') as tar:
            tar.extractall(out, filter='data')
        report = json.loads((out / 'replay/report.json').read_text())
        pins = {'public_digest': report['public_digest'], **{c['label']: c['anchor_digest'] for c in report['checkpoints']}}
        dump(out / 'retained-pins.json', pins)
        dump(out / 'public-inventory.json', inventory(out))
        result = verify(out, out / 'retained-pins.json')
        result['execution_action'] = 'fresh two-host run of all three slices, followed by offline verification'
        dump(out / 'suite.json', result)
        print('PASS: 48 binding records; 16 authorization + 12 replay scenarios; 7 tamper controls', flush=True)
    except BaseException as exc:
        if not (out / 'suite.json').exists():
            dump(out / 'suite.json', {'status': 'FAIL', 'error': type(exc).__name__ + ': ' + str(exc)})
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    r = sub.add_parser('run', help='Explicit opt-in real LAN run; new local/remote directories only')
    for name in ['peer', 'a-host', 'remote-root']:
        r.add_argument('--' + name, required=True)
    r.add_argument('--output', type=Path, required=True)
    v = sub.add_parser('verify', help='Only rehash/reduce retained evidence, without SSH or computation')
    v.add_argument('--evidence', type=Path, required=True)
    v.add_argument('--pins', type=Path, required=True, help='caller-retained key/checkpoint pins, independently stored')
    v.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    if a.command == 'run':
        run(a)
        return
    if a.report.exists() or a.report.resolve().is_relative_to(a.evidence.resolve()):
        p.error('new report outside retained evidence required')
    result = verify(a.evidence, a.pins)
    dump(a.report, result)
    print('PASS: retained Work 2 evidence verified without guest/network execution')


if __name__ == '__main__':
    main()
