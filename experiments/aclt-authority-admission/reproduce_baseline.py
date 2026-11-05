# SPDX-License-Identifier: Apache-2.0
"""Retain authenticated old-version rollback/clone counterexamples; no worker executed."""

if not __debug__:
    raise SystemExit('assert-based validation requires Python without -O/PYTHONOPTIMIZE')

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

p = argparse.ArgumentParser()
p.add_argument('--source', type=Path, required=True)
p.add_argument('--report', type=Path, required=True)
args = p.parse_args()
sys.path.insert(0, str(args.source/'experiments/aclt-multinode-admission'))
from receiver import Receiver
from protocol import envelope, check, rows
manifest = {'keys': {'a': {'unit': 'A', 'secret': 'test-only'}},
            'tasks': {'t': {'values': [3,-1,8,0], 'chunk': 2, 'units': ['A']}}}
boot = '00000000-0000-0000-0000-000000000000'

def contribute(receiver):
    def send(op, **extra):
        return check(receiver.handle(envelope(op, 'a', 't', boot, 'test-only', **extra)), 'test-only')['reply']
    q = send('reserve')
    assert q['status'] == 'reserved'
    result = send('submit', ticket=q['ticket'], rows=rows([3,-1,8,0], 2))
    assert result['status'] == 'accepted'
    return {'reservation': q, 'acceptance': result}

with tempfile.TemporaryDirectory() as td:
    root = Path(td);db = root/'ledger';snapshot = root/'snapshot'
    r = Receiver(manifest, str(db), True);shutil.copy2(db, snapshot)
    first = contribute(r);del r
    shutil.copy2(snapshot, db);second = contribute(Receiver(manifest, str(db)))
    left, right = root/'left', root/'right'
    shutil.copy2(snapshot, left);shutil.copy2(snapshot, right)
    a, b = contribute(Receiver(manifest, str(left))), contribute(Receiver(manifest, str(right)))
    report = {'counterexamples_reproduced': True, 'worker_executions': 0,
              'scope': 'authenticated Receiver.handle path, not VM execution',
              'rollback': [first, second], 'clones': [a, b]}
    assert first['acceptance']['receipt'] != second['acceptance']['receipt']
    assert a['acceptance']['receipt'] != b['acceptance']['receipt']
    args.report.write_text(json.dumps(report, indent=2)+'\n')
print('Two baseline counterexamples reproduced')
