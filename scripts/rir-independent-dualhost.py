#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Two physical-host RIR independent core build/byte/signature checks, controlled over SSH.

Only tests encoding and signature adapters. No task TCP protocol, remote compute
admission, fault injection, identity independence or settlement claim is made.
"""

if not __debug__:
    raise SystemExit('assert-based validation requires Python without -O/PYTHONOPTIMIZE')

import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tarfile
ROOT=Path(__file__).resolve().parents[1]
FILES=['experiments/aclt-rir-stats-probe/src/independent_executor.rs', 'experiments/aclt-rir-stats-probe/src/core.rs', 'experiments/aclt-rir-stats-probe/independent.py', 'experiments/aclt-rir-stats-probe/independent-contract.json', 'experiments/aclt-rir-stats-probe/wasm.py', 'experiments/aclt-rir-stats-probe/runtime.py', 'experiments/aclt-rir-stats-probe/cases.py', 'experiments/aclt-rir-stats-probe/tests/fixture.json', 'experiments/aclt-rir-stats-probe/tests/independent-vectors.json', 'tools/verification_profile/__init__.py', 'tools/verification_profile/codec.py', 'tools/verification_profile/rust/main.rs', 'tools/verification_profile/rust/fm.rs', 'tools/verification_profile/rust/fm_policy.rs', 'tools/verification_profile/rust/sha256.rs', 'tools/verification_profile/rust/nfc.rs', 'tools/verification_profile/rust/unicode_data.rs', 'tools/verification_profile/rust/UNICODE-LICENSE.txt', 'scripts/check-rir-independent.py']

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--peer',required=True);p.add_argument('--remote-root',required=True);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_.-]+@[a-zA-Z0-9_.-]+',a.peer) or a.peer.startswith('-'):p.error('explicit user@host required')
    if not re.fullmatch(r'/[a-zA-Z0-9_/.-]+',a.remote_root) or '..' in Path(a.remote_root).parts or a.remote_root in ('/','/tmp','/home'):p.error('new absolute remote directory required')
    if a.output.exists():p.error('output exists')
    a.output.mkdir(parents=True)
    ssh=['ssh','-F','/dev/null','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10',a.peer]
    commands=[]
    def run(argv,log,**kw):
        commands.append(argv)
        (a.output/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
        r=subprocess.run(argv,capture_output=True,timeout=240,**kw)
        (a.output/log).write_bytes(r.stdout+r.stderr)
        if r.returncode:raise RuntimeError(f'{log}: exit {r.returncode}; retained failure output')
        return r.stdout
    source={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in FILES}
    (a.output/'SOURCE-SHA256.json').write_text(json.dumps(source,indent=2)+'\n')
    archive=a.output/'source.tar'
    with tarfile.open(archive,'w') as t:
        for n in FILES:t.add(ROOT/n,arcname=n,recursive=False)
        t.add(a.output/'SOURCE-SHA256.json',arcname='SOURCE-SHA256.json')
    remote=shlex.quote(a.remote_root)
    # Exclusive mkdir: never replace or reuse a previous remote run.
    run(ssh+[f'umask 077; mkdir -- {remote} && tar -xf - -C {remote}'],'remote-deploy.log',input=archive.read_bytes())
    preflight='''import json,hashlib,pathlib,platform,socket,subprocess
r=pathlib.Path('.');pins=json.loads((r/'SOURCE-SHA256.json').read_text())
assert all(hashlib.sha256((r/n).read_bytes()).hexdigest()==h for n,h in pins.items())
print(json.dumps({'hostname':socket.gethostname(),'platform':platform.platform(),'source_sha256':pins,'python':subprocess.check_output(['python3','--version'],text=True).strip(),'rustc':subprocess.check_output(['rustc','--version'],text=True).strip(),'openssl':subprocess.check_output(['openssl','version'],text=True).strip()}))
'''
    info=json.loads(run(ssh+[f'cd {remote} && python3 -c '+shlex.quote(preflight)],'remote-source-and-environment.json'))
    import socket
    if info['hostname']==socket.gethostname():raise RuntimeError('same hostname: separate physical-host assumption not accepted')
    assert info['source_sha256']==source
    run([sys.executable,'-B',str(ROOT/'scripts/check-rir-independent.py'),'--report',str(a.output.resolve()/'A-report.json')],'A-check.log')
    run(ssh+[f'cd {remote} && python3 -B scripts/check-rir-independent.py --report report.json'],'B-check.log')
    remote_read='import pathlib,sys;sys.stdout.write(pathlib.Path("report.json").read_text())'
    b=json.loads(run(ssh+[f'cd {remote} && python3 -c '+shlex.quote(remote_read)],'B-report.json'))
    aa=json.loads((a.output/'A-report.json').read_text())
    for key in ['status','cases','fixed_vectors','source_sha256','support','results_sha256']:assert aa[key]==b[key],key
    assert aa['status']=='PASS' and aa['support']['full_ADR_0006_conformance'] is False
    assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in source.items()),'local source changed during run'
    result={'status':'PASS','scope':'two-host codec build, raw RIR validation/execution, exact result CBOR/digest, negative and host-fault checks; no formal Receipt admission; SSH transfer only, no task protocol validation','physical_hosts':'two distinct physical hosts accepted under DUALHOST-SSH-1; hostname difference is not proof of physical independence','A_hostname':socket.gethostname(),'B_hostname':info['hostname'],'cases_per_host':aa['cases'],'fixed_vectors':aa['fixed_vectors'],'results_sha256':aa['results_sha256'],'source_sha256':source,'remote_run_retained':True,'new_protocol_or_gate_claim':False}
    (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='source_sha256'},indent=2))
if __name__=='__main__':main()
