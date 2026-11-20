# SPDX-License-Identifier: Apache-2.0
"""Funding-gated once-only reference execution, and immutable outcome retransmission."""
import argparse
from context import *
from durability import durable_new, state_directory


def execute_once(cfg, public, directory, binding, expected_task, transport=None, test_hook=None):
    frozen = decode(binding); p = validate_policy(decode(frozen['policy'])); pid = policy_id(frozen['policy'])
    task, inputs = bind(frozen['commitment'], expected_task, frozen['artifact'], [frozen['input']])
    need(p['task'].hex() == expected_task and p['requester'] == task['requester_ref'], 'local funding task binding')
    need(cfg['role'] in ['A', 'B'] and cfg['environment'] == environment(), 'local funded environment')
    directory = state_directory(directory)
    durable_new(directory/'intent.cbor', encode({'authority': cfg['authority_id'], 'policy_id': pid, 'role': cfg['role']}))
    packet = request(cfg, 'START', {'policy_id': pid, 'role': cfg['role']})
    reply = transport(packet) if transport else exchange(cfg, packet, public)
    need(reply['status'] == 'STARTED', 'funded execution not authorized')
    permit = reply['result']['permit']
    expected = permit_body(cfg['authority_id'], pid, p, binding, cfg['role'], {'actor': cfg['requester'], 'environment': cfg['environment']})
    need(recorded_fields_match(verify(permit, public, cfg['public_digest']), expected, {'binding_digest'}), 'funded permit/local binding')
    durable_new(directory/'binding.cbor', binding); durable_new(directory/'permit.cbor', permit)
    if test_hook: test_hook('after_permit')
    durable_new(directory/'invoke.cbor', encode({'permit_digest': sha(permit)}))
    from rir_adapter import execute
    result = execute(frozen['artifact'], inputs, task['execution_limits'])
    digest = bytes.fromhex(result.pop('outcome_digest'))
    if 'output_hex' in result: result['output'] = bytes.fromhex(result.pop('output_hex'))
    raw = encode({'schema_id': 'aclt.exp.compared-outcome@1', 'permit_digest': sha(permit),
                  'task': p['task'], 'role': cfg['role'], 'environment': cfg['environment'],
                  'result': result, 'outcome_digest': digest})
    validate_report(raw, permit, public, cfg['public_digest'], binding, expected)
    durable_new(directory/'outcome.cbor', raw)
    if test_hook: test_hook('after_outcome')
    return pid, raw


def submit_saved(cfg, public, directory, pid, transport=None):
    raw = regular(Path(directory)/'outcome.cbor'); binding = regular(Path(directory)/'binding.cbor')
    permit = regular(Path(directory)/'permit.cbor'); frozen = decode(binding); p = validate_policy(decode(frozen['policy']))
    need(policy_id(frozen['policy']) == pid, 'saved policy binding')
    body = verify(permit, public, cfg['public_digest'])
    expected = permit_body(cfg['authority_id'], pid, p, binding, cfg['role'], {'actor': cfg['requester'], 'environment': body['environment']})
    validate_report(raw, permit, public, cfg['public_digest'], binding, expected)
    packet = request(cfg, 'SUBMIT', {'policy_id': pid, 'role': cfg['role'], 'report': raw})
    return transport(packet) if transport else exchange(cfg, packet, public)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('mode', choices=['execute', 'submit', 'environment'])
    for n in ['config', 'public', 'state', 'binding', 'report']: p.add_argument('--'+n, type=Path)
    p.add_argument('--task-id'); p.add_argument('--policy-id'); a = p.parse_args()
    if a.mode == 'environment': print(environment().hex()); raise SystemExit(0)
    need(a.report is not None and not a.report.exists(), 'new report required')
    cfg = config(a.config)
    if a.mode == 'execute':
        pid, raw = execute_once(cfg, a.public, a.state, regular(a.binding), a.task_id)
        result = {'status': 'OUTCOME_SAVED', 'policy_id': pid.hex(), 'outcome_digest': decode(raw)['outcome_digest'].hex()}
    else:
        result = submit_saved(cfg, a.public, a.state, bytes.fromhex(a.policy_id))
        result = {'status': result['status']}
    with a.report.open('x') as f: json.dump(result, f, indent=2); f.write('\n')
    print(json.dumps(result))
