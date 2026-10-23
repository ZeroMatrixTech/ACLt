# SPDX-License-Identifier: Apache-2.0
"""Freeze or execute an experimental commitment; no production authorization."""
import argparse
import json
from pathlib import Path
from commitment import freeze,load,view,execute_probe,Rejected

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    create=sub.add_parser('freeze');run=sub.add_parser('execute-probe')
    for c in [create,run]:
        c.add_argument('--artifact',type=Path,required=True);c.add_argument('--input',type=Path,action='append',required=True)
    create.add_argument('--requester-ref',required=True);create.add_argument('--nonce',required=True)
    for flag in ['gas-limit','output-limit','memory-pages-limit','call-depth-limit']:create.add_argument('--'+flag,type=int,required=True)
    create.add_argument('--output',type=Path,required=True)
    run.add_argument('--commitment',type=Path,required=True);run.add_argument('--task-id',required=True);run.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    # Refuse existing destinations before reading any inputs or doing execution.
    target=a.output if a.command=='freeze' else a.report
    if target.exists():p.error('destination exists; preserve frozen objects and evidence')
    try:
        artifact=a.artifact.read_bytes();inputs=[path.read_bytes() for path in a.input]
        if a.command=='freeze':
            try:requester=bytes.fromhex(a.requester_ref);nonce=bytes.fromhex(a.nonce)
            except ValueError as exc:raise Rejected('invalid requester/nonce hex') from exc
            limits={k:getattr(a,k) for k in ['gas_limit','output_limit','memory_pages_limit','call_depth_limit']}
            raw,identity=freeze(artifact,inputs,requester,nonce,limits)
            target.mkdir(parents=True,exist_ok=False)
            (target/'commitment.cbor').write_bytes(raw)
            (target/'view.json').write_text(json.dumps(view(load(raw)),indent=2)+'\n')
            (target/'identity.json').write_text(json.dumps({'experimental_task_id':identity,'object_kind':'ExperimentalTaskCommitment','authorization':'NOT_IMPLEMENTED'},indent=2)+'\n')
            print(identity);return 0
        result={'status':'TASK_OUTCOME',**execute_probe(a.commitment.read_bytes(),a.task_id,artifact,inputs)};code=0
    except Rejected as exc:
        result={'status':'REJECTED','reason':str(exc)};code=2
    except OSError as exc:
        result={'status':'HOST_FAULT','reason':type(exc).__name__};code=3
    except Exception as exc:
        # Unexpected interpreter failures must never become a Task trap.
        result={'status':'HOST_FAULT','reason':type(exc).__name__};code=3
    if a.command=='execute-probe':
        with target.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result));return code

if __name__=='__main__':raise SystemExit(main())
