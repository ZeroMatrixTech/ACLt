#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check retained FM/RIR summaries; optionally verify Git blobs and replay locally.

Default is metadata only. --repository checks all source blobs at recorded merge
revisions. --replay materializes those snapshots in temporary directories and runs
their original drivers; it never creates new two-host evidence or updates summary.
"""
import argparse
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import migration_evidence as e

def run(repository=None,replay=False,output=None):
    if replay and repository is None:raise ValueError('--replay requires --repository')
    if output:
        if output.exists():raise ValueError('output directory exists')
        output.mkdir(parents=True)
    results=[]
    for spec in e.SPECS.values():
        summary=e.load(ROOT/'docs/testing'/(spec['stem']+'.summary.json'));result=e.verify(summary)
        if repository:
            result['source_files_verified']=e.verify_source(summary,e.git_reader(repository));result['source_verification']='PASS'
        if replay:
            with tempfile.TemporaryDirectory(prefix='aclt-retained-replay-') as name:
                tmp=Path(name);snapshot=tmp/'source';snapshot.mkdir()
                data=subprocess.check_output(['git','archive','--format=tar',summary['source_revision']],cwd=repository,stderr=subprocess.PIPE)
                with tarfile.open(fileobj=io.BytesIO(data)) as tf:tf.extractall(snapshot,filter='data')
                e.verify_source(summary,lambda rev,n:(snapshot/n).read_bytes())
                report=tmp/'replay.json';r=subprocess.run([sys.executable,'-B',str(snapshot/summary['driver']),'--report',str(report)],cwd=snapshot,capture_output=True,text=True,timeout=180)
                if output:(output/(spec['stem']+'.log')).write_text(r.stdout+r.stderr)
                e.need(r.returncode==0,'local replay driver failed: '+summary['id'])
                got=e.load(report);e.compare_replay(summary,got);result['local_replay']='PASS'
                if output:(output/(spec['stem']+'.local-replay.json')).write_text(json.dumps(got,indent=2)+'\n')
        results.append(result)
    record=dict(status='PASS',audit_dependency_plan=e.verify_audit_plan(ROOT),verification_scope='metadata + exact Git source' if repository else 'metadata only; no source or execution claim',local_replay=replay,new_dualhost_runs=0,gate_changes=False,summaries=results)
    if output:(output/'result.json').write_text(json.dumps(record,indent=2)+'\n')
    return record

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repository',type=Path);p.add_argument('--replay',action='store_true');p.add_argument('--output',type=Path);a=p.parse_args()
    try:print(json.dumps(run(a.repository,a.replay,a.output),indent=2))
    except (ValueError,KeyError,TypeError,subprocess.SubprocessError) as exc:p.exit(1,'FAIL: '+str(exc)+'\n')
if __name__=='__main__':main()
