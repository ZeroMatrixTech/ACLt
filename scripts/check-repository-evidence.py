#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Metadata by default; explicit Git source checks never fetch or execute history."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.git_sources import read_blob
from tools.repository_checks import source_baseline,check_documents
from tools.migration_evidence import verify as verify_summary
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repository',type=Path);a=p.parse_args()
    def blob(revision,name):
        return read_blob(a.repository,revision,name)
    try:
        baseline=source_baseline(ROOT,blob if a.repository else None);reports=[]
        for name in ('FM-S1A-20261028','FM-S1B-20261028','RIR-INDEPENDENT-CORE-20261028'):
            v=json.loads((ROOT/('docs/testing/'+name+'.summary.json')).read_text());verify_summary(v)
            if a.repository:
                for n,want in v['source_files_sha256'].items():
                    import hashlib
                    if hashlib.sha256(blob(v['source_revision'],n)).hexdigest()!=want:raise ValueError('source mismatch '+n)
            reports.append(dict(id=v['id'],pins=len(v['source_files_sha256']),source_verification='PASS' if a.repository else 'NOT_RUN'))
        print(json.dumps(dict(status='PASS',baseline=baseline,retained_summaries=reports,documents=check_documents(ROOT),new_protocol_acceptance=False),indent=2))
    except (ValueError,KeyError,OSError) as exc:p.exit(1,'FAIL: '+str(exc)+'\n')
