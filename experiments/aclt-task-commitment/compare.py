# SPDX-License-Identifier: Apache-2.0
"""Rehash independent-host task-commitment probe evidence against current sources."""
import argparse
import hashlib
import json
from pathlib import Path
from commitment import ROOT,HERE,load,task_id,bind,profile

def compare(left,right):
    reports=[json.loads((root/'report.json').read_text()) for root in [left,right]]
    if any(r['status']!='PASS' for r in reports) or reports[0]['hostname']==reports[1]['hostname']:
        raise ValueError('two passing runs with distinct hostnames required; physical independence is assumed')
    if reports[0]['source_hashes']!=reports[1]['source_hashes']:raise ValueError('cross-host source drift')
    required={p.relative_to(ROOT).as_posix() for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    required.update(profile()[0]['implementation_pins'])
    required.add('experiments/aclt-rir-stats-probe/tests/fixture.json')
    if set(reports[0]['source_hashes'])!=required:raise ValueError('missing or unexpected source pins')
    for name,digest in reports[0]['source_hashes'].items():
        path=Path(name)
        if path.is_absolute() or '..' in path.parts:raise ValueError('invalid source path')
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=digest:raise ValueError('current source drift: '+name)
    expected={'commitment.cbor','artifact.cbor','input.bin','view.json','identity.json','cases.json'}
    if any(set(r['artifacts'])!=expected for r in reports):raise ValueError('artifact inventory drift')
    for root,report in zip([left,right],reports):
        for name,digest in report['artifacts'].items():
            if Path(name).name!=name:raise ValueError('invalid artifact name')
            if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:raise ValueError('retained artifact mismatch: '+name)
        raw=(root/'commitment.cbor').read_bytes()
        if task_id(raw)!=report['experimental_task_id']:raise ValueError('task identity mismatch')
        obj,_=bind(raw,report['experimental_task_id'],(root/'artifact.cbor').read_bytes(),[(root/'input.bin').read_bytes()])
        for key in ['rir_digest','execution_profile_digest']:
            if obj[key].hex()!=report[key]:raise ValueError('report metadata mismatch: '+key)
        data=json.loads((root/'cases.json').read_text())
        if report['cases']!=24 or data['count']!=report['cases'] or len(data['cases'])!=report['cases']:raise ValueError('incomplete case records')
    if reports[0]['artifacts']!=reports[1]['artifacts']:raise ValueError('cross-host bytes differ')
    return {'status':'PASS','scope':'same implementation on two physical hosts; not independent codec validation or authorized execution',
            'physical_independence':'user-accepted DUALHOST-SSH-1 assumption; hostname difference alone is insufficient',
            'cases_per_host':reports[0]['cases'],'records':sum(r['cases'] for r in reports),
            'experimental_task_id':reports[0]['experimental_task_id'],'rir_digest':reports[0]['rir_digest'],
            'execution_profile_digest':reports[0]['execution_profile_digest'],'artifacts':reports[0]['artifacts'],
            'source_hashes':reports[0]['source_hashes'],'run_report_sha256':[hashlib.sha256((r/'report.json').read_bytes()).hexdigest() for r in [left,right]]}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('left',type=Path);p.add_argument('right',type=Path);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists() or any(a.report.resolve().is_relative_to(r.resolve()) for r in [a.left,a.right]):p.error('report must be new and outside retained runs')
    result=compare(a.left,a.right)
    with a.report.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:result[k] for k in ['status','records','experimental_task_id']}))
