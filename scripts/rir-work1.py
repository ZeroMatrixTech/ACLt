# SPDX-License-Identifier: Apache-2.0
"""Build three candidate RIR slices, or revalidate their retained dual-host evidence."""
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ['aclt-rir-build-probe', 'aclt-rir-io-probe', 'aclt-rir-stats-probe']
REQUIRED = [
    {'build.py', 'normalize.py', 'toolchain-lock.json', 'src/program.rs', 'src/entry.rs'},
    {'build.py', 'wasm.py', 'runtime.py', 'cases.py', 'toolchain-lock.json', 'src/sdk.rs', 'src/program.rs', 'src/entry.rs'},
    {'build.py', 'wasm.py', 'runtime.py', 'cases.py', 'toolchain-lock.json', 'src/sdk.rs', 'src/program.rs', 'src/entry.rs', 'src/executor.rs', 'src/reference.cpp', 'tests/fixture.json'},
]

def sha(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('expected regular evidence/source file: ' + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_check(experiment, report, required):
    sources = report['source_hashes']
    if set(sources) != required:
        raise ValueError('unexpected or missing source pins: ' + experiment.name)
    for name, expected in sources.items():
        if sha(experiment / name) != expected:
            raise ValueError('current source differs from tested source: ' + experiment.name + '/' + name)
    if report['toolchain_lock_sha256'] != sha(experiment / 'toolchain-lock.json'):
        raise ValueError('toolchain report/source mismatch')


def verify(pairs):
    if len(pairs) != 3:
        raise ValueError('all three slice pairs are required')
    results = []
    for index, (name, pair) in enumerate(zip(EXPERIMENTS, pairs)):
        experiment = ROOT / 'experiments' / name
        left, right = [Path(p).resolve() for p in pair]
        if left == right:
            raise ValueError('distinct retained run directories required')
        reports = [json.loads((p / 'report.json').read_text()) for p in [left, right]]
        for report in reports:
            source_check(experiment, report, REQUIRED[index])
        # Reuse the maintained per-slice checker: it rehashes the four retained
        # Wasm/envelope/corpus files and checks the candidate domain digest.
        spec = importlib.util.spec_from_file_location('rir_work1_compare_' + str(index), experiment / 'compare.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.compare(left, right)
        result.pop('hosts', None)  # public summary contains no machine identifiers
        records = 0
        for root, report in zip([left, right], reports):
            for build in report['builds']:
                directory = root / build['name']
                for file, key in [('executor', 'native_executor_sha256'), ('worker', 'cpp_worker_sha256')]:
                    if key in build and sha(directory / file) != build[key]:
                        raise ValueError('retained native binary changed: ' + file)
                if index:
                    execution = json.loads((directory / 'execution.json').read_text())
                    expected = 55 if index == 1 else 69
                    if execution['count'] != expected or len(execution['cases']) != expected or build['execution_cases'] != expected:
                        raise ValueError('incomplete execution corpus')
                    records += expected
        results.append({'slice': index + 1, 'comparison': result, 'execution_records': records,
                        'source_hashes': reports[0]['source_hashes'],
                        'run_report_sha256': [sha(p / 'report.json') for p in [left, right]]})
    # Continuity, not cross-program identity: all three programs have different
    # artifacts, but retain the same toolchain/export boundary and SDK contract.
    locks = [sha(ROOT / 'experiments' / n / 'toolchain-lock.json') for n in EXPERIMENTS]
    entries = [sha(ROOT / 'experiments' / n / 'src/entry.rs') for n in EXPERIMENTS]
    sdks = [sha(ROOT / 'experiments' / n / 'src/sdk.rs') for n in EXPERIMENTS[1:]]
    if len(set(locks)) != 1 or len(set(entries)) != 1 or len(set(sdks)) != 1:
        raise ValueError('cross-slice toolchain/export/SDK drift')
    stats = ROOT / 'experiments/aclt-rir-stats-probe/src/reference.cpp'
    original = ROOT / 'experiments/aclt-minimal-verifier-state3/cpp/worker.cpp'
    if sha(stats) != sha(original):
        raise ValueError('C++ baseline snapshot drift')
    return {'status': 'PASS', 'work_item': 'RIR-WORK1',
            'completed_scope': 'candidate Rust-to-RIR execution and exact stats comparison',
            'evidence_action': 'rehash retained dual-host runs; no new compilation or remote execution',
            'retained_builds': 12, 'retained_execution_records': sum(r['execution_records'] for r in results),
            'continuity': {'toolchain_lock_sha256': locks[0], 'entry_sha256': entries[0], 'sdk_sha256': sdks[0],
                           'cpp_baseline_sha256': sha(stats)}, 'slices': results,
            'ADR_status': 'PROPOSED', 'gate_change': False,
            'limitations': ['three progressively extended programs, not one identical artifact',
                            'physical independence remains the accepted DUALHOST-SSH-1 assumption',
                            'hash consistency is not authenticated provenance or statistical independence',
                            'not complete RIR/RPR conformance, formal Receipt, verification verdict or settlement']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    build = sub.add_parser('build', help='Run on each physical host in a new directory; no automatic SSH/install')
    build.add_argument('--toolchain', type=Path, required=True)
    build.add_argument('--output', type=Path, required=True)
    check = sub.add_parser('verify', help='Rehash retained runs against current pinned source files')
    for i in range(1, 4):
        check.add_argument('--slice' + str(i), type=Path, nargs=2, required=True, metavar=('A', 'B'))
    check.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'build':
        if not str(args.toolchain).strip() or not (args.toolchain / 'bin/rustc').is_file():
            parser.error('explicit installed toolchain required')
        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=False)
        results = []
        try:
            for i, name in enumerate(EXPERIMENTS, 1):
                argv = [sys.executable, '-B', str(ROOT / 'experiments' / name / 'build.py'),
                        '--toolchain', str(args.toolchain.resolve()), '--output', str(output / ('slice' + str(i)))]
                with (output / ('slice' + str(i) + '.log')).open('x') as log:
                    result = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT)
                results.append({'slice': i, 'exit_code': result.returncode})
                if result.returncode:
                    raise RuntimeError('slice build failed; preserve output and logs: ' + str(i))
        finally:
            (output / 'suite.json').write_text(json.dumps({'status': 'PASS' if len(results) == 3 and all(r['exit_code'] == 0 for r in results) else 'FAIL', 'runs': results}, indent=2) + '\n')
        print('PASS: three candidate slices; compare with independent physical-host evidence next')
        return
    pairs = [args.slice1, args.slice2, args.slice3]
    target = args.report.resolve()
    if target.exists() or any(target.is_relative_to(p.resolve()) for pair in pairs for p in pair):
        parser.error('report must be new and outside retained run directories')
    result = verify(pairs)
    with target.open('x') as out:
        json.dump(result, out, indent=2)
        out.write('\n')
    print(json.dumps({'status': result['status'], 'retained_builds': 12, 'retained_execution_records': result['retained_execution_records']}))


if __name__ == '__main__':
    main()
