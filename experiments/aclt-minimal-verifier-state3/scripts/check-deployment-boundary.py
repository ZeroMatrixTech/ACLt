#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Deploy/debug builds must not contain fault environment hooks."""
from pathlib import Path
import os
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
def require(ok,message):
    if not ok:raise ValueError(message)
for name in ('coordinator-deployment','cargo-deployment/debug/coordinator'):
    raw=(ROOT/'build'/name).read_bytes()
    require(not any(x in raw for x in (b'ACLT_TEST_PAUSE',b'ACLT_TEST_IO_FAIL',b'ACLT_TEST_IO_ERRNO',b'ACLT_TEST_SIGNAL_DIR')),'fault hooks compiled in '+name)
require(b'ACLT_TEST_PAUSE' in (ROOT/'build/cargo-test-registry/debug/coordinator').read_bytes(),'fault test variant missing')
require(b'ACLT_TEST_WORKER_GATE' not in (ROOT/'build/worker').read_bytes(),'deploy worker gate compiled in')
require(b'ACLT_TEST_WORKER_GATE' in (ROOT/'build/worker-test').read_bytes(),'test worker gate missing')
with tempfile.TemporaryDirectory() as td:
    env=dict(os.environ,ACLT_TEST_WORKER_GATE=str(Path(td)/'absent'))
    r=subprocess.run([str(ROOT/'build/worker'),str(ROOT/'examples/input.txt'),'4'],capture_output=True,timeout=3,env=env)
    require(r.returncode==0,'deploy worker obeyed test gate')
print('PASS: deployment debug binaries exclude faults; explicit test variants retain them')
