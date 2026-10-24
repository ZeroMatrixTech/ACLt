# SPDX-License-Identifier: Apache-2.0
"""Non-production task fixture, shared by local tests and explicit dual-host probes."""
import json
import struct
from common import ROOT,profile
from commitment import freeze

def task(nonce):
    profile()
    from rir_adapter import modules
    wasm,_=modules()
    raw=bytes.fromhex(json.loads((ROOT/'experiments/aclt-rir-stats-probe/tests/fixture.json').read_text())['raw_hex'])
    artifact=wasm.artifact(wasm.normalize(raw)[0]);data=struct.pack('<QQ4q',2,4,3,-1,5,8)
    commitment,identity=freeze(artifact,[data],bytes(32),nonce,{'gas_limit':50000000,'output_limit':4800000,'memory_pages_limit':2,'call_depth_limit':8})
    return commitment,identity,artifact,data
