# SPDX-License-Identifier: Apache-2.0
"""Run one candidate statistics artifact; statuses distinguish rejection, outcome and host fault."""
import argparse
import hashlib
import json
from pathlib import Path
from wasm import Reject
from runtime import load_candidate,HostFault


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--artifact',type=Path,required=True)
    p.add_argument('--input',type=Path,action='append',default=[])
    p.add_argument('--gas-limit',type=int,default=50000000)
    p.add_argument('--output-limit',type=int,default=4800000)
    p.add_argument('--memory-pages-limit',type=int,default=2)
    p.add_argument('--call-depth-limit',type=int,default=8)
    p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():p.error('report already exists; preserve previous evidence')
    inputs=[path.read_bytes() for path in a.input]
    raw=a.artifact.read_bytes()
    result={'scope':'restricted Python candidate statistics reference, not a production RPR',
            'artifact_sha256':hashlib.sha256(raw).hexdigest(),'input_sha256':[hashlib.sha256(x).hexdigest() for x in inputs]}
    try:
        runner=load_candidate(raw,inputs,gas_limit=a.gas_limit,output_limit=a.output_limit,
                              memory_pages_limit=a.memory_pages_limit,call_depth_limit=a.call_depth_limit)
        result.update(status='TASK_OUTCOME',result=runner.run(),host_trace=runner.host.trace);code=0
    except Reject as exc:result.update(status='REJECTED',reason=str(exc));code=2
    except HostFault as exc:result.update(status='HOST_FAULT',reason=str(exc));code=3
    with a.report.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result));return code


if __name__=='__main__':raise SystemExit(main())
