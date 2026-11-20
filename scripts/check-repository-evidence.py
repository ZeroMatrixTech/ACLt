#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check document links and historical metadata; SHA verification is disabled."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.repository_checks import source_baseline,check_documents
from tools.migration_evidence import verify as verify_summary
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repository',type=Path);a=p.parse_args()
    try:
        baseline=source_baseline(ROOT);reports=[]
        for name in ('FM-S1A-20261028','FM-S1B-20261028','RIR-INDEPENDENT-CORE-20261028'):
            v=json.loads((ROOT/('docs/testing/'+name+'.summary.json')).read_text());verify_summary(v)
            reports.append(dict(id=v['id'],pins=len(v['source_files_sha256']),source_verification='DISABLED'))
        print(json.dumps(dict(status='PASS',sha_consistency='DISABLED',baseline=baseline,retained_summaries=reports,documents=check_documents(ROOT),new_protocol_acceptance=False),indent=2))
    except (ValueError,KeyError,OSError) as exc:p.exit(1,'FAIL: '+str(exc)+'\n')
