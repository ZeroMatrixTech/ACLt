# SPDX-License-Identifier: Apache-2.0
"""Real LAN test-ledger client; settlement is internal, never external payment."""
import argparse
from wire import *


def view(value):
    if type(value) is bytes: return value.hex()
    if type(value) is dict: return {k: view(v) for k, v in value.items()}
    if type(value) is list: return [view(v) for v in value]
    return value


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation', choices=['freeze', 'reserve', 'status', 'balance', 'settle'])
    for n in ['config', 'public', 'report']: p.add_argument('--'+n, type=Path, required=True)
    p.add_argument('--policy-id')
    for n in ['policy', 'commitment', 'artifact', 'input']: p.add_argument('--'+n, type=Path)
    a = p.parse_args(); need(not a.report.exists(), 'new report required')
    if a.operation == 'freeze':
        need(all(getattr(a, n) is not None for n in ['policy', 'commitment', 'artifact', 'input']), 'freeze files required')
        data = {n: regular(getattr(a, n)) for n in ['policy', 'commitment', 'artifact', 'input']}
    elif a.operation in ['reserve', 'status', 'settle']:
        need(a.policy_id is not None, 'policy ID required'); data = {'policy_id': bytes.fromhex(a.policy_id)}
    else: data = {}
    cfg = config(a.config); packet = request(cfg, a.operation.upper(), data)
    result, raw = exchange(cfg, packet, a.public, keep_raw=True)
    with a.report.open('x') as f: json.dump({'request': packet.hex(), 'signed_response': raw.hex(), 'response': view(result)}, f, indent=2); f.write('\n')
    print(json.dumps({'status': result['status']}))
