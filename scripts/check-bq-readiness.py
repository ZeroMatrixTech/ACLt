# SPDX-License-Identifier: Apache-2.0
"""Replay non-authoritative B/Q evidence review; never enable capability."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.bq_boundaries.readiness import matrix_report, strict_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    base=ROOT/'tests/bq_readiness/fixtures'
    p.add_argument('--inventory',type=Path,default=base/'project-gaps.json')
    p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():p.error('new report path required')
    raw=a.inventory.read_bytes();inventory=strict_json(raw)
    hypothetical=strict_json((base/'hypothetical-complete.json').read_bytes())
    result=matrix_report(hypothetical,inventory)
    index=strict_json((base/'project-evidence-index.json').read_bytes())
    artifacts={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in index.values()}
    if inventory['data_kind']=='project-gap-inventory':
        rows={x['requirement_id']:x for x in inventory['records']}
        for rid,name in index.items():
            if rid not in rows or rows[rid]['evidence_digest']!=artifacts[name]:
                raise ValueError('project experimental artifact changed: '+rid)
    result['project_experimental_artifacts_sha256']=artifacts
    result['inventory_sha256']=hashlib.sha256(raw).hexdigest()
    names=['scripts/check-bq-readiness.py','tools/bq_boundaries/readiness.py',
           'tools/bq_boundaries/calibration.py','tools/bq_boundaries/model.py','tools/bq_boundaries/__init__.py',
           'tests/verification_model/recursive_model.py','tests/verification_model/closed_form_oracle.py',
           'tests/bq_readiness/test_readiness.py','tests/bq_readiness/fixtures/hypothetical-complete.json',
           'tests/bq_readiness/fixtures/project-gaps.json','tests/bq_readiness/fixtures/project-evidence-index.json']
    result['source_sha256']={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    with a.report.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print('PASS: research review/projections reproduced; actual capability unchanged')


if __name__=='__main__':main()
