# SPDX-License-Identifier: Apache-2.0
"""Run exact synthetic B/Q calibration/sensitivity research, never approval."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.bq_boundaries.calibration import research_report


def strict_json(raw):
    def pairs(items):
        d={}
        for k,v in items:
            if k in d: raise ValueError('duplicate JSON field')
            d[k]=v
        return d
    def reject(value): raise ValueError('non-rational JSON number: '+value)
    if len(raw)>1_000_000: raise ValueError('research dataset too large')
    return json.loads(raw,object_pairs_hook=pairs,parse_float=reject,parse_constant=reject)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,default=ROOT/'tests/bq_calibration/fixtures/synthetic-v1.json')
    p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    if a.report.exists(): p.error('new report path required')
    raw=a.dataset.read_bytes();result=research_report(strict_json(raw))
    result['dataset_sha256']=hashlib.sha256(raw).hexdigest()
    names=['scripts/check-bq-calibration.py','tools/bq_boundaries/calibration.py',
           'tools/bq_boundaries/model.py','tools/bq_boundaries/__init__.py',
           'tests/verification_model/recursive_model.py','tests/verification_model/closed_form_oracle.py',
           'tests/bq_calibration/test_calibration.py','tests/bq_calibration/fixtures/synthetic-v1.json']
    result['source_sha256']={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    with a.report.open('x') as f:
        json.dump(result,f,indent=2);f.write('\n')
    print('PASS: conditional calibration and sensitivity research; no empirical B/Q certification')


if __name__=='__main__': main()
