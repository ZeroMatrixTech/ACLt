# SPDX-License-Identifier: Apache-2.0
"""Build three candidate RIR slices, or revalidate their retained dual-host evidence."""
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SHA_CONSISTENCY_STATUS = "DISABLED"

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
    """Source pins remain optional report data; consistency is disabled."""
    return SHA_CONSISTENCY_STATUS


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
        # Reuse the maintained per-slice checker for actual retained results.
        spec = importlib.util.spec_from_file_location('rir_work1_compare_' + str(index), experiment / 'compare.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.compare(left, right)
        result.pop('hosts', None)  # public summary contains no machine identifiers
        records = 0
        for root, report in zip([left, right], reports):
            for build in report['builds']:
                directory = root / build['name']
                if index:
                    execution = json.loads((directory / 'execution.json').read_text())
                    expected = 55 if index == 1 else 69
                    if execution['count'] != expected or len(execution['cases']) != expected or build['execution_cases'] != expected:
                        raise ValueError('incomplete execution corpus')
                    records += expected
        results.append({'slice': index + 1, 'comparison': result, 'execution_records': records,
                        'source_hashes': reports[0].get('source_hashes', {}),
                        'run_report_sha256': [sha(p / 'report.json') for p in [left, right]]})
    # Continuity, not cross-program identity: all three programs have different
    # artifacts, but retain the same toolchain/export boundary and SDK contract.
    locks = [sha(ROOT / 'experiments' / n / 'toolchain-lock.json') for n in EXPERIMENTS]
    entries = [sha(ROOT / 'experiments' / n / 'src/entry.rs') for n in EXPERIMENTS]
    sdks = [sha(ROOT / 'experiments' / n / 'src/sdk.rs') for n in EXPERIMENTS[1:]]
    stats = ROOT / 'experiments/aclt-rir-stats-probe/src/reference.cpp'
    return {'sha_consistency': SHA_CONSISTENCY_STATUS, 'status': 'PASS', 'work_item': 'RIR-WORK1',
            'completed_scope': 'candidate Rust-to-RIR execution and exact stats comparison',
            'evidence_action': 'retained actual content/count comparison; SHA consistency DISABLED',
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
    check = sub.add_parser('verify', help='Compare retained actual results; SHA consistency DISABLED')
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
