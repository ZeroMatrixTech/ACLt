# SPDX-License-Identifier: Apache-2.0
"""Reuse the unchanged slice-3 reference in a dedicated probe process."""
from pathlib import Path
import importlib
import sys
from cbor_codec import Rejected,need

STATS=Path(__file__).resolve().parent.parent/'aclt-rir-stats-probe'

def modules():
    # Fail closed if another experiment's generic module names already occupy
    # this process; never silently mix two different Wasm/runtime implementations.
    for name in ['wasm','runtime']:
        if name in sys.modules:
            need(Path(sys.modules[name].__file__).resolve()==STATS/(name+'.py'),'conflicting RIR probe module: '+name)
    if str(STATS) not in sys.path:sys.path.insert(0,str(STATS))
    return importlib.import_module('wasm'),importlib.import_module('runtime')

def parse_artifact(raw):
    wasm,_=modules()
    try:return wasm.decode_artifact(raw)
    except wasm.Reject as exc:raise Rejected('candidate RIR rejected: '+str(exc)) from exc

def execute(artifact,inputs,limits):
    wasm,runtime=modules()
    try:return runtime.load_candidate(artifact,inputs,**limits).run()
    except wasm.Reject as exc:raise Rejected('candidate execution rejected: '+str(exc)) from exc
    # HostFault intentionally propagates as a host failure, never a Task outcome.
