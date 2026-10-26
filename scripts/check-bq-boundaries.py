# SPDX-License-Identifier: Apache-2.0
"""Reproduce B/Q slice-1 exact countermodels; no network or calibration fitting."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.bq_boundaries.model import report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report', type=Path, required=True)
    args = p.parse_args()
    if args.report.exists():
        p.error('report exists; choose a new path')
    result = report()
    paths = ['scripts/check-bq-boundaries.py', 'tools/bq_boundaries/__init__.py',
             'tools/bq_boundaries/model.py', 'tests/bq_boundaries/test_boundaries.py',
             'tests/verification_model/recursive_model.py', 'tests/verification_model/closed_form_oracle.py']
    result['source_sha256'] = {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in paths}
    with args.report.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print('PASS: 8 exact boundary witnesses; not empirical B/Q calibration')


if __name__ == '__main__':
    main()
