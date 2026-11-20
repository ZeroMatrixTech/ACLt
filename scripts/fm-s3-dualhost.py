#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the candidate FM-S3 LAN closeout with an A authority and a B executor.

A hosts the authority, the auditor and the closure observer key; B hosts the
executor. --terminals combines verified RPR entries, observer-signed execution
closure and the funding boundary in two isolated ledgers. --historical-gaps
runs the Work 2/3 fault and recovery cases in two more isolated ledgers.
"""
import argparse
import hashlib
from itertools import count
import json
from pathlib import Path
import re
import runpy
import shlex
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.formal_migration import foundation, policy, s2, s2_evidence, s2_fixture, s2_worker, s3_authority, s3_closure
from tools.verification_profile import codec as c

BASE = runpy.run_path(str(ROOT/'scripts/fm-s2-dualhost.py'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('peer', 'a-host', 'remote-root'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--task-trap', action='store_true', help='run the pinned divide-by-zero artifact')
    parser.add_argument('--execution-closure', action='store_true', help='run the pinned observer closure matrix')
    parser.add_argument('--terminals', action='store_true',
                        help='run verified-entry, FAILED, FUNDING_EXHAUSTED and start-state scenarios')
    parser.add_argument('--historical-gaps', action='store_true',
                        help='run Work 2/3 candidate migration fault and recovery regressions')
    parser.add_argument('--group', choices=('primary','secondary'), help=argparse.SUPPRESS)
    args = parser.parse_args()
    grouped = args.terminals or args.historical_gaps
    if args.group and not grouped:
        parser.error('--group requires --terminals or --historical-gaps')
    if sum((args.task_trap, args.execution_closure, args.terminals, args.historical_gaps)) > 1:
        parser.error('choose one specialized matrix')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+', args.peer):
        parser.error('explicit user@host required')
    if not re.fullmatch(r'/tmp/fm-s3-[A-Za-z0-9_.-]+', args.remote_root):
        parser.error('new dedicated /tmp/fm-s3-* directory required')
    output = args.output.resolve()
    output.mkdir(mode=0o700)
    if grouped and args.group is None:
        # Bound each state and deployment input to at most three full Receipts.
        mode = '--terminals' if args.terminals else '--historical-gaps'
        failed = []
        for group in ('primary','secondary'):
            with (output/f'{group}.log').open('wb') as log:
                result = subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),mode,
                    '--group',group,'--peer',args.peer,'--a-host',args.a_host,
                    '--remote-root',f'{args.remote_root}-{group}','--output',str(output/group)],
                    cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            if result.returncode:
                failed.append(f'{group} (exit {result.returncode})')
        if failed:
            raise RuntimeError('failed groups: '+', '.join(failed)+f'; logs: {output}')
        summary = {group:json.loads((output/group/'summary.json').read_text())
                   for group in ('primary','secondary')}
        (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        print(json.dumps(summary,indent=2))
        return
    secondary = args.group == 'secondary'
    ssh = ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o',
           'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10', args.peer]
    remote_root = shlex.quote(args.remote_root)
    counter = count(1)

    def run(command, label, *, remote=False, data=None, expected=0):
        seq = next(counter)
        argv = ssh + [f'cd {remote_root} && {shlex.join(command)}'] if remote else command
        result = subprocess.run(argv, cwd=ROOT, input=data, capture_output=True, timeout=120)
        (output/f'{seq:03}-{label}.log').write_bytes(result.stdout + result.stderr)
        if result.returncode != expected:
            raise RuntimeError(f'{label}: exit {result.returncode}, expected {expected}; {result.stderr[-500:]!r}')
        return result.stdout

    def put(entries):
        run(['tar', '-xf', '-'], 'upload', remote=True, data=BASE['tar_bytes'](entries))

    def need(value, message):
        if not value:
            raise RuntimeError(message)

    names = BASE['source_files']() + ['scripts/fm-s3-dualhost.py', 'scripts/check-fm-s2-evidence.py']
    sources = {name: (ROOT/name).read_bytes() for name in sorted(set(names))}
    pins = {name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()}
    (output/'source-sha256.json').write_text(json.dumps(pins, indent=2)+'\n')
    subprocess.run(ssh + [f'umask 077; mkdir -- {remote_root}'], check=True, timeout=15)
    put(dict(sources, **{'source-sha256.json': json.dumps(pins).encode()}))
    verify_sources = """from pathlib import Path
import hashlib,json,platform,socket
pins=json.loads(Path('source-sha256.json').read_text())
# SHA consistency DISABLED; source manifest remains record data.
print(json.dumps({'hostname':socket.gethostname(),'platform':platform.platform()}))
"""
    peer = json.loads(run(['python3', '-B', '-c', verify_sources], 'B-preflight', remote=True))
    need(peer['hostname'] != socket.gethostname(), 'distinct physical peer hostname required')
    compiler = ['rustc','--edition=2021','-D','warnings','-C','overflow-checks=yes','-O',
                'experiments/aclt-rir-stats-probe/src/independent_executor.rs','-o']
    binary = output/'executor'
    run(compiler+[str(binary)], 'A-build')
    run(compiler+['executor'], 'B-build', remote=True)
    digest = hashlib.sha256(binary.read_bytes()).digest()
    run(['sha256sum','executor'], 'B-binary', remote=True)  # Record only; SHA consistency DISABLED.

    private = output/'private'
    artifact = None
    if args.task_trap:
        vectors = json.loads((ROOT/'experiments/aclt-rir-stats-probe/tests/independent-vectors.json').read_text())
        vector = next(v for v in vectors['vectors'] if v['id'] == 'divzero')
        artifact = bytes.fromhex(vector['artifact_hex'])
    receipt_count = 2 if (args.terminals and secondary) or (args.historical_gaps and not secondary) else 3
    # One held Receipt leaves 5 of 22 units in the funding boundary group.
    balance = 22 if args.terminals and secondary else 68
    cfg, templates = s2_fixture.build(ROOT, private, digest, count=receipt_count, artifact=artifact,
                                      balance=balance)
    if args.historical_gaps and secondary:
        # Three interrupted executor assignments stay open until the common deadline.
        cfg['caps']['provider'] = dict(concurrency=3,value=21,attempts=3)
    observer = private/'closure-observer.pem'
    observer_der = s2_fixture.keypair(observer) if args.execution_closure or (args.terminals and not secondary) else None
    bundles = [s3_authority.bind_bundle(bundle, task_traps=args.task_trap or args.terminals,
                                        closure_observer_der=observer_der, rpr_entry=args.terminals or args.historical_gaps,
                                        funding_boundary=args.terminals) for bundle in templates]
    receipts = [policy.bundle(bundle) for bundle in bundles]
    cfg['allowed_receipts'] = receipts
    for name, value in [('config.cbor',cfg),('bundles.cbor',bundles)]:
        (private/name).write_bytes(c.encode(value))
    put({name:(private/name).read_bytes() for name in ('config.cbor','bundles.cbor','executor.pem')})
    db, clock, fault = (private/name for name in ('state.db','clock','fault'))
    clock.write_text('3000')
    now = 3000
    s3_authority.Ledger(db,cfg,private/'issuer.pem',clock=lambda:now,create=True)
    proc = None
    log = None
    generation = 0
    port = None

    def stop():
        if proc is not None and proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=15)
        if log is not None:
            log.close()

    def start():
        nonlocal proc, log, generation, port
        generation += 1
        ready = output/f'ready-{generation}.json'
        log = (output/f'service-{generation}.log').open('wb')
        proc = subprocess.Popen([sys.executable,'-B','scripts/fm-s2-service.py','--s3b',
            '--host',args.a_host,'--config',str(private/'config.cbor'),'--private',str(private/'issuer.pem'),
            '--database',str(db),'--ready',str(ready),'--clock-file',str(clock),'--fault-file',str(fault)],
            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        for _ in range(200):
            if ready.exists():
                try:
                    port = json.loads(ready.read_text())['port']
                    return
                except json.JSONDecodeError:
                    pass
            need(proc.poll() is None, 'authority startup failed')
            time.sleep(0.05)
        raise RuntimeError('authority startup timeout')

    call_number = count(1)
    def call(op, index, role='REQUESTER', *, expect=0, rejection=None, **extra):
        index_of_call = next(call_number)
        remote = role == 'EXECUTOR'
        base = Path('.') if remote else private
        out = Path(f'call-{index_of_call}') if remote else output/f'call-{index_of_call}'
        command = ['python3','-B','scripts/fm-s2-client.py','--op',op,'--index',str(index),
                   '--role',role,'--host',args.a_host,'--port',str(port),'--now',str(now),
                   '--config',str(base/'config.cbor'),'--bundles',str(base/'bundles.cbor'),
                   '--private',str(base/(role.lower()+'.pem')),'--output',str(out)]
        for flag, value in extra.items():
            command += ['--'+flag.replace('_','-')]
            if value is not True:
                command += [str(value)]
        stdout = run(command, f'{role}-{op}', remote=remote, expected=expect)
        if expect:
            if rejection is not None:
                # The diagnostic is unsigned. Checkpoint equality is checked separately.
                path = out/'response.cbor'
                raw = run(['cat',str(path)], 'B-rejection-diagnostic', remote=True) if remote else path.read_bytes()
                need(c.decode(raw)==dict(error=rejection), f'{op}: unexpected rejection diagnostic')
            return json.loads(stdout) if stdout.strip() else None
        if op == 'WORK':
            if not (args.terminals or args.historical_gaps):
                return None
            raw = run(['cat',str(out/'result.cbor')], 'B-work-result', remote=True) if remote else (out/'result.cbor').read_bytes()
            return c.decode(raw)
        raw = run(['cat',str(out/'result.cbor')], 'B-response', remote=True) if remote else (out/'result.cbor').read_bytes()
        return c.decode(raw)

    def setup(index):
        call('CREATE',index)
        for role in ('EXECUTOR','AUDITOR'):
            call('ACTIVATE',index,role)
            directory = f'work-{index}' if role == 'EXECUTOR' else output/f'audit-{index}'
            call('WORK',index,role,runtime='executor' if role == 'EXECUTOR' else binary,
                 directory=directory,s3b=True)
        run(['python3','-B','-c',
             'from pathlib import Path; from tools.formal_migration.s2_worker import s3_result_body; '
             'from tools.verification_profile import codec as c; import sys; '
             'Path(sys.argv[2]).write_bytes(c.encode(s3_result_body(sys.argv[1])))',
             f'work-{index}',f'result-{index}.cbor'], 'B-runtime-result',remote=True)

    def submit(index, role='EXECUTOR', expect=0):
        path = f'result-{index}.cbor'
        if role == 'AUDITOR':
            path = output/f'auditor-result-{index}.cbor'
            path.write_bytes(c.encode(s2_worker.s3_result_body(output/f'audit-{index}')))
        return call('S3_RESULT',index,role,expect=expect,body_file=path)

    def finish(cases, final, terminals=None):
        ledger = s3_authority.Ledger(db,cfg,private/'issuer.pem',clock=lambda:now)
        snapshot = s2_evidence.export(ledger)
        anchor = final['checkpoint']
        state = ledger.state()
        paid = sum(task['settlement']['paid'] for task in state['tasks'].values())
        need(state['held']==0 and state['free']+paid==cfg['balance'],'final funding conservation')
        for name, obj in [('snapshot.cbor',snapshot),('anchor.cbor',anchor),('config.cbor',cfg)]:
            (output/name).write_bytes(c.encode(obj))
        put({'snapshot.cbor':c.encode(snapshot),'anchor.cbor':c.encode(anchor)})
        result = run(['python3','-B','scripts/check-fm-s2-evidence.py','--s3b','--config','config.cbor',
                      '--snapshot','snapshot.cbor','--expected-genesis',s2.h(cfg).hex(),
                      '--anchor','anchor.cbor'],'B-public-replay',remote=True)
        replay = s3_authority.verify_snapshot(cfg,snapshot,anchor)
        need(json.loads(result)==replay,'A/B public replay mismatch')
        cases.append('cross_host_public_replay')
        outcome_kind = ('HOST_RESOURCE_EXHAUSTED' if args.execution_closure
                        else 'OK_AND_HOST_RESOURCE_EXHAUSTED' if args.terminals
                        else 'TRAP_INTEGER_DIVIDE_BY_ZERO' if args.task_trap else 'OK')
        summary = dict(sha_consistency='DISABLED',status='PASS', scenarios=cases, task_outcome=outcome_kind,
                       runtime_sha256=digest.hex(), replay=replay,
                       genesis=s2.h(cfg).hex(), total=cfg['balance'], available=state['free'], paid=paid,
                       holdings=state['held'], source_manifest_sha256=hashlib.sha256(
                           (output/'source-sha256.json').read_bytes()).hexdigest())
        if args.historical_gaps:
            summary.update(mode='HISTORICAL_GAPS', group=args.group,
                           topology=dict(A='authority and auditor', B='executor and signed request sender'))
        if terminals is not None:
            roles_on_a = 'authority and auditor' if secondary else 'authority, auditor and closure observer key'
            summary.update(mode='TERMINALS', group=args.group, terminals=terminals,
                           topology=dict(A=roles_on_a, B='executor'))
        (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        print(json.dumps(summary,indent=2))

    def body_on_b(index, kind, reason='RESOURCE'):
        name = f'{kind}-{index}.cbor'
        builder = ('s3_result_body(sys.argv[1])' if kind == 'result'
                   else 's3_hostfault_body(sys.argv[1], sys.argv[3])')
        run(['python3','-B','-c',
             'from pathlib import Path; from tools.formal_migration.s2_worker import s3_result_body, s3_hostfault_body; '
             'from tools.verification_profile import codec as c; import sys; '
             f'Path(sys.argv[2]).write_bytes(c.encode({builder}))',
             f'work-{index}', name, reason], f'B-{kind}-body', remote=True)
        return name

    def work(index, role, crash=None, **extra):
        directory = f'work-{index}' if role == 'EXECUTOR' else output/f'audit-{index}'
        extra.update(runtime='executor' if role == 'EXECUTOR' else binary, directory=directory, s3b=True)
        if crash:
            extra['crash_hook'] = crash
        return call('WORK', index, role, expect=73 if crash else 0, **extra)

    def states(index):
        return call('QUERY', index)['result']['start_states']

    def closure_request(index, signer):
        binding = c.decode(run(['cat', f'work-{index}/s3-start'], 'B-entry-binding', remote=True))
        binding.pop('entry')
        start_ref = binding.pop('start')
        statement = s3_closure.observation(cfg, binding, start_ref)
        signature = s2.sign(signer, s3_closure.SIGNATURE_DOMAIN, statement) if signer else b'\0'*256
        path = output/f'closure-{index}.cbor'
        path.write_bytes(c.encode(dict(receipt=receipts[index], observation=statement,
                                       observer_signature=signature)))
        return path

    def terminals_flow():
        nonlocal now
        found = []
        decisions = {}
        call('CREATE',0)
        for role in ('EXECUTOR','AUDITOR'):
            call('ACTIVATE',0,role)
            work(0,role)
        call('S3_RESULT',0,'EXECUTOR',body_file=body_on_b(0,'result'))
        submit(0,'AUDITOR')
        need(states(0)==dict(EXECUTOR='EXECUTION_STARTED',AUDITOR='EXECUTION_STARTED'),'verified entry states')
        decisions[0] = call('S3_FINALIZE',0)['result']
        need((decisions[0]['condition'],decisions[0]['terminal'],decisions[0]['method_observation'])
             ==('EVIDENCE_EXHAUSTED','UNRESOLVED','CONCORDANT'),'verified entry pair decision')
        found.append('cross_host_verified_entry_pair')

        call('CREATE',1)
        call('ACTIVATE',1,'EXECUTOR')
        observed = work(1,'EXECUTOR',closure_fault=True)
        need(observed['returncode']==3 and c.decode(observed['core'])==dict(status='HOST_FAULT',code=s3_closure.FAULT),
             'unexpected RPR fault record')
        need(work(1,'EXECUTOR')==observed,'B restart re-executed the faulted entry')
        need(states(1)==dict(EXECUTOR='EXECUTION_STARTED',AUDITOR='NOT_CONSUMED'),'faulted entry state')
        call('S3_HOST_FAULT',1,'EXECUTOR',body_file=body_on_b(1,'hostfault','RESOURCE'))
        call('S3_FINALIZE',1,expect=2)
        call('S3_CLOSE_EXECUTION',1,expect=2,body_file=closure_request(1,None))
        call('S3_CLOSE_EXECUTION',1,expect=2,body_file=closure_request(1,private/'executor.pem'))
        path = closure_request(1,observer)
        exhausted = call('S3_CLOSE_EXECUTION',1,body_file=path)['result']
        need((exhausted['attempts_observed'],exhausted['valid_submission_count'])==(1,0),'closure counts')
        need(call('S3_CLOSE_EXECUTION',1,body_file=path)['result']==exhausted,'closure retry changed')
        call('ACTIVATE',1,'AUDITOR',expect=2)
        decisions[1] = call('S3_FINALIZE',1)['result']
        need((decisions[1]['condition'],decisions[1]['terminal'])==('EXECUTION_FAILED','FAILED'),
             'observer closure decision')
        found += ['physical_rpr_fault_through_verified_entry', 'self_report_does_not_close',
                  'forged_observer_rejected', 'observer_closure_failed']

        call('CREATE',2)
        call('ACTIVATE',2,'EXECUTOR')
        work(2,'EXECUTOR',crash='AFTER_CONSUME')
        need(work(2,'EXECUTOR')==dict(status='UNKNOWN_NO_REEXECUTION',stage='AUTHORIZATION_CONSUMED'),
             'B consume-only stage')
        run(['test','!','-e','work-2/invocation'], 'B-consumed-without-invocation', remote=True)
        need(states(2)['EXECUTOR']=='AUTHORIZATION_CONSUMED','authorization consumed state')
        call('ACTIVATE',2,'AUDITOR')
        work(2,'AUDITOR')
        submit(2,'AUDITOR')
        found.append('executor_killed_after_permit_consume')

        now = bundles[2]['receipt']['execution']['deadline']
        clock.write_text(str(now))
        decisions[2] = call('S3_FINALIZE',2)['result']
        need((decisions[2]['condition'],decisions[2]['terminal'],decisions[2]['start_states']['EXECUTOR'])
             ==('VERIFICATION_INVALIDATING','UNRESOLVED','START_UNKNOWN'),'start unknown decision')
        found.append('start_unknown_invalidating')

        before = call('S3_SETTLEMENT_STATUS',1)['checkpoint']
        for marker, code, status in [('BEFORE_COMMIT',71,'READY'),('AFTER_COMMIT',72,'COMMITTED')]:
            fault.write_text(marker)
            lost = call('S3_SETTLE',1,expect=2)
            need(lost['reason']=='incomplete S2 frame','fault did not interrupt the FAILED settlement reply')
            need(proc.wait(timeout=10)==code,'wrong fault boundary')
            stop()
            start()
            response = call('S3_SETTLEMENT_STATUS',1)
            recovered = response['result']
            need(recovered['status']==status,'FAILED settlement recovery status mismatch')
            checkpoint = response['checkpoint']
            if status == 'READY':
                need(checkpoint == before,'rolled-back settlement changed checkpoint')
            else:
                need(checkpoint['seq'] == before['seq']+1 and
                     c.decode(response['events'][-1])['prev'] == before['head'],
                     'committed settlement did not extend checkpoint exactly once')
        failed = call('S3_SETTLE',1)['result']
        need(failed==recovered['settlement'] and (failed['paid'],failed['refund'])==(0,17),
             'FAILED settlement changed after recovery')
        found += ['failed_settlement_before_commit_restart', 'failed_settlement_after_commit_restart']
        for index, paid in [(0,12),(2,5)]:
            last = call('S3_SETTLE',index)
            need((last['result']['paid'],last['result']['refund'])==(paid,17-paid),
                 'terminal settlement amount')
        found.append('terminal_settlements')
        return found, last, {str(k): v['terminal'] for k, v in sorted(decisions.items())}

    def terminal_boundary_flow():
        nonlocal now
        found = []
        decisions = {}
        call('CREATE',0)
        call('ACTIVATE',0,'EXECUTOR')
        work(0,'EXECUTOR',crash='BEFORE_GUEST')
        need(work(0,'EXECUTOR')==dict(status='UNKNOWN_NO_REEXECUTION',stage='INVOCATION_RECORDED'),
             'B restart re-executed or lost the entry stage')
        run(['test','!','-e','work-0/observation'],'B-no-guest-output',remote=True)
        need(states(0)==dict(EXECUTOR='EXECUTION_STARTED',AUDITOR='NOT_CONSUMED'),'interrupted entry state')
        call('S3_HOST_FAULT',0,'EXECUTOR',body_file=body_on_b(0,'hostfault','INTERRUPTED'))
        found.append('executor_interrupted_after_entry_before_guest')

        call('CREATE',1)
        boundary = call('ACTIVATE',1,'EXECUTOR')['result']
        need(boundary==dict(funding_exhausted=True,receipt=receipts[1],role='EXECUTOR',required=17,available=5),
             'funding boundary record')
        call('ACTIVATE',1,'AUDITOR',expect=2,rejection='S3 funding boundary recorded')
        decisions[1] = call('S3_FINALIZE',1)['result']
        need((decisions[1]['condition'],decisions[1]['terminal'])==('BUDGET_EXHAUSTED','FUNDING_EXHAUSTED'),
             'funding boundary decision')
        found.append('underfunded_activation_boundary')

        now = bundles[0]['receipt']['execution']['deadline']
        clock.write_text(str(now))
        decisions[0] = call('S3_FINALIZE',0)['result']
        need((decisions[0]['condition'],decisions[0]['terminal'],'execution_observation' in decisions[0])
             ==('DEADLINE_REACHED','EXPIRED',False),'self-reported interruption must not close execution')
        expired = call('S3_SETTLE',0)['result']
        need((expired['paid'],expired['refund'])==(0,17),'interrupted task refund')
        final = call('S3_SETTLE',1)
        need(final['result']['entitlements']==[] and final['result']['terminal']=='FUNDING_EXHAUSTED',
             'funding boundary settlement')
        found += ['deadline_after_unclosed_interruption', 'terminal_boundary_settlements']
        return found, final, {str(k): v['terminal'] for k, v in sorted(decisions.items())}

    def signed_request(op, index, *, role='REQUESTER', body=None):
        record = cfg['requester'] if role == 'REQUESTER' else cfg['providers'][role]
        return s2.request(cfg, private/(role.lower()+'.pem'), foundation.principal_digest(record),
                          op, dict(receipt=receipts[index]) if body is None else body, now)

    def from_b(label, *requests, failure=None):
        # B owns the client connections. The requester signing key stays on A.
        names = [f'{label}-{i}.request.cbor' for i in range(len(requests))]
        put({name:c.encode(req) for name,req in zip(names,requests)})
        remote_client = """import json, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from tools.formal_migration.s2_transport import rpc
host, port, *names = sys.argv[1:]
requests = [Path(name).read_bytes() for name in names]
ready = Barrier(len(requests), timeout=15)
def call(request):
    ready.wait()
    try:
        return {'response': rpc(host, int(port), request).hex()}
    except ConnectionRefusedError:
        return {'connection_refused': True}
    except OSError as exc:
        return {'transport_error': str(exc)}
with ThreadPoolExecutor(max_workers=len(requests)) as pool:
    print(json.dumps(list(pool.map(call, requests))))
"""
        replies = json.loads(run(['python3','-B','-c',remote_client,args.a_host,str(port),*names],
                                 label,remote=True))
        if failure == 'offline':
            need(replies==[dict(connection_refused=True)], f'{label}: expected refused connection')
            return
        if failure == 'drop':
            need(replies==[dict(transport_error='incomplete S2 frame')] and not fault.exists(),
                 f'{label}: reply was not dropped')
            return
        return [s2.check_response(cfg,req,bytes.fromhex(reply['response']))
                for req,reply in zip(requests,replies,strict=True)]

    def same_checkpoint(response, before, label):
        need(response['checkpoint']==before['checkpoint'], f'{label}: changed checkpoint')

    def one_event(response, before, request, label):
        event = c.decode(response['events'][-1])
        need(response['checkpoint']['seq']==before['checkpoint']['seq']+1 and
             event['prev']==before['checkpoint']['head'] and
             (request is None or event['request']==request), f'{label}: expected exactly one event')
        return event

    def historical_flow():
        call('CREATE',0)
        call('ACTIVATE',0,'EXECUTOR')
        work(0,'EXECUTOR',crash='AFTER_OBSERVATION')
        saved = run(['cat','work-0/observation'],'B-saved-observation',remote=True)
        held = call('QUERY',0)['result']
        need(held['task']['funding_held']==17 and not held['audit']['slots'],
             'persisted but unsent outcome affected authority')
        waiting = call('S3_SETTLEMENT_STATUS',0)
        need(waiting['result']==dict(status='AWAITING_TERMINAL'),'unsent outcome unlocked settlement')
        call('S3_SETTLE',0,expect=2)
        call('WORK',0,'EXECUTOR',runtime='executor',directory='clone-0',s3b=True,expect=1)
        stop()
        need(work(0,'EXECUTOR')==c.decode(saved),'offline worker changed its saved outcome')
        start()
        path = body_on_b(0,'result')
        body = c.decode(run(['cat',path],'B-sealed-result',remote=True))
        # Valid signature over a malformed outcome must not consume the result slot.
        before = call('S3_SETTLEMENT_STATUS',0)
        put({'invalid-0.cbor':c.encode(dict(body,outcome=b''))})
        call('S3_RESULT',0,'EXECUTOR',expect=2,rejection='task outcome byte bound',body_file='invalid-0.cbor')
        same_checkpoint(call('S3_SETTLEMENT_STATUS',0),before,'invalid first result')
        request = signed_request('S3_RESULT',0,role='EXECUTOR',body=body)
        accepted, = from_b('saved-outcome-submit',request)
        one_event(accepted,before,request,'saved outcome acceptance')
        need(accepted['result']['outcome']==body['outcome'],'saved outcome changed on submission')
        duplicates = from_b('result-concurrent-exact-replay',request,request)
        for duplicate in duplicates:
            same_checkpoint(duplicate,accepted,'concurrent result replay')
            need(duplicate['result']==accepted['result'],'exact replay changed original acceptance')
        stop()
        start()
        replayed, = from_b('result-restart-exact-replay',request)
        same_checkpoint(replayed,accepted,'result restart replay')
        need(replayed['result']==accepted['result'],'restart changed original acceptance')
        call('ACTIVATE',0,'AUDITOR')
        work(0,'AUDITOR')
        submit(0,'AUDITOR')
        decision = call('S3_FINALIZE',0)
        call('S3_SETTLE',0,'EXECUTOR',expect=2,rejection='S3b requester role')
        before = call('S3_SETTLEMENT_STATUS',0)
        same_checkpoint(before,decision,'non-requester settlement')
        need(before['result']==dict(status='READY'),'first settlement was already committed')
        first, second = [signed_request('S3_SETTLE',0) for _ in range(2)]
        settled = from_b('first-settlement-B-barrier',first,second)
        for response in settled:
            event = one_event(response,before,None,'first settlement race')
            need(event['request'] in (first,second),'race event has a different request')
        need(settled[0]['result']==settled[1]['result'] and
             settled[0]['checkpoint']==settled[1]['checkpoint'] and
             (settled[0]['result']['paid'],settled[0]['result']['refund'])==(12,5),
             'first settlement race changed allocation')

        call('CREATE',1)
        call('ACTIVATE',1,'EXECUTOR')
        work(1,'EXECUTOR')
        body_on_b(1,'result')
        before = call('S3_SETTLEMENT_STATUS',1)
        fault.write_text('DROP_REPLY')
        lost = submit(1,expect=2)
        need(lost['reason']=='incomplete S2 frame' and not fault.exists(),'result reply was not dropped')
        recovered = submit(1)
        event = one_event(recovered,before,None,'result recovery after missing reply')
        need(event['request']['op']=='S3_RESULT',
             'original result not recovered')
        only_one = call('QUERY',1)['result']
        need(only_one['task']['funding_held']==17 and set(only_one['audit']['slots'])=={'EXECUTOR'},
             'single role released reservation')
        call('S3_FINALIZE',1,expect=2)
        need(call('S3_SETTLEMENT_STATUS',1)['result']==dict(status='AWAITING_TERMINAL'),
             'missing role unlocked settlement')
        call('ACTIVATE',1,'AUDITOR')
        work(1,'AUDITOR')
        submit(1,'AUDITOR')
        call('S3_FINALIZE',1)

        final = drop_settlement(1,12,5)
        return [
            'saved_outcome_process_exit_holds_funds', 'saved_outcome_resubmitted_without_guest',
            'invalid_first_result_then_valid', 'concurrent_exact_result_replay', 'restart_exact_result_replay',
            'non_requester_settlement_rejected', 'first_settlement_two_B_clients_barrier',
            'result_commit_reply_loss_and_recovery', 'single_role_holds_full_reservation',
            'payment_commit_reply_loss_and_recovery',
        ], final

    def drop_settlement(index, paid, refund):
        before = call('S3_SETTLEMENT_STATUS',index)
        request = signed_request('S3_SETTLE',index)
        fault.write_text('DROP_REPLY')
        from_b(f'settlement-{index}-drop',request,failure='drop')
        query = signed_request('S3_SETTLEMENT_STATUS',index)
        recovery, = from_b(f'settlement-{index}-recovery',query)
        allocation = recovery['result'].get('settlement',{})
        event = one_event(recovery,before,request,'settlement after missing reply')
        need(recovery['result']['status']=='COMMITTED' and
             (allocation.get('paid'),allocation.get('refund'))==(paid,refund),'query did not recover the original allocation')
        retry, fresh = from_b(f'settlement-{index}-retry',request,signed_request('S3_SETTLE',index))
        for response in (retry,fresh):
            same_checkpoint(response,recovery,'settlement retry')
            need(response['result']==allocation,'settlement retry changed allocation')
        return recovery

    def historical_interruptions_flow():
        nonlocal now
        call('CREATE',0)
        call('WORK',0,'EXECUTOR',runtime='executor',directory='unfunded',s3b=True,expect=1)
        run(['test','!','-e','unfunded/intent'],'B-unfunded-no-intent',remote=True)
        call('CREATE',1)
        call('ACTIVATE',1,'EXECUTOR')
        call('WORK',1,'EXECUTOR',runtime='executor',directory='unfunded',s3b=True,expect=1)
        run(['test','!','-e','unfunded/invocation'],'B-foreign-receipt-no-invocation',remote=True)
        call('ACTIVATE',0,'EXECUTOR')
        call('CREATE',2)
        call('ACTIVATE',2,'EXECUTOR')
        for index, hook, stage in [(0,'BEFORE_GUEST','INVOCATION_RECORDED'),
                                    (1,'AFTER_INTENT','INTENT_ONLY'),
                                    (2,'AFTER_GUEST','INVOCATION_RECORDED')]:
            work(index,'EXECUTOR',crash=hook)
            need(work(index,'EXECUTOR')==dict(status='UNKNOWN_NO_REEXECUTION',stage=stage),
                 f'{hook}: worker resumed a partial attempt')
            run(['test','!','-e',f'work-{index}/observation'],'B-no-complete-outcome',remote=True)
            run(['python3','-B','-c',
                 'from tools.formal_migration.s2_worker import s3_result_body; import sys; s3_result_body(sys.argv[1])',
                 f'work-{index}'],'B-partial-outcome-not-submittable',remote=True,expected=1)
            held = call('QUERY',index)['result']
            need(held['task']['funding_held']==17 and not held['audit']['slots'],
                 f'{hook}: incomplete execution released funding or submitted a result')
        before = call('S3_SETTLEMENT_STATUS',0)
        stop()
        query = signed_request('S3_SETTLEMENT_STATUS',0)
        from_b('settlement-offline-recovery',query,failure='offline')
        start()
        recovered, = from_b('settlement-restart-incomplete',query)
        same_checkpoint(recovered,before,'offline recovery')
        need(recovered['result']==dict(status='AWAITING_TERMINAL') and
             call('QUERY',0)['result']['task']['funding_held']==17,
             'incomplete execution released funds after restart')

        now = bundles[0]['receipt']['execution']['deadline']
        clock.write_text(str(now))
        for index in (0,1,2):
            decision = call('S3_FINALIZE',index)['result']
            need(decision['terminal']=='EXPIRED','incomplete task failed to expire')
        final = drop_settlement(0,0,17)
        for index in (1,2):
            final = call('S3_SETTLE',index)
            need((final['result']['paid'],final['result']['refund'])==(0,17),'incomplete task allocation')

        return [
            'unfunded_start_no_guest', 'foreign_receipt_no_guest',
            'worker_exit_before_guest_holds_funds', 'worker_exit_after_intent_no_reexecution',
            'worker_exit_after_guest_before_persistence_no_reexecution',
            'offline_settlement_query_no_inference', 'restart_incomplete_holds_full_reservation',
            'full_refund_commit_reply_loss_and_recovery',
        ], final

    cases = []
    try:
        start()
        if args.historical_gaps:
            found, final = historical_interruptions_flow() if secondary else historical_flow()
            finish(found, final)
            return
        if args.terminals:
            found, final, terminals = terminal_boundary_flow() if secondary else terminals_flow()
            finish(found, final, terminals)
            return
        if args.execution_closure:
            call('CREATE', 0)
            call('ACTIVATE', 0, 'EXECUTOR')
            call('WORK', 0, 'EXECUTOR', runtime='executor', directory='closure-work',
                 s3b=True, closure_fault=True)
            raw = run(['cat', 'closure-work/observation'], 'B-closure-observation', remote=True)
            observed = c.decode(raw)
            core = c.decode(observed['core'])
            need(observed['returncode'] == 3 and
                 core == dict(status='HOST_FAULT', code=s3_closure.FAULT), 'unexpected RPR fault record')
            raw = run(['cat', 'closure-work/s3-start'], 'B-closure-entry', remote=True)
            binding = c.decode(raw)
            start_ref = binding.pop('start')
            need(observed['intent'] == binding['intent'], 'closure runtime intent mismatch')
            put({'host-fault.cbor':c.encode(dict(binding,start=start_ref,reason='RESOURCE'))})
            call('S3_HOST_FAULT', 0, 'EXECUTOR', body_file='host-fault.cbor')
            call('S3_FINALIZE', 0, expect=2)
            statement = s3_closure.observation(cfg, binding, start_ref)
            body = dict(receipt=receipts[0], observation=statement, observer_signature=b'\0'*256)
            path = output/'closure.cbor'
            path.write_bytes(c.encode(body))
            call('S3_CLOSE_EXECUTION', 0, expect=2, body_file=path)
            body['observer_signature'] = s2.sign(observer, s3_closure.SIGNATURE_DOMAIN, statement)
            path.write_bytes(c.encode(body))
            exhausted = call('S3_CLOSE_EXECUTION', 0, body_file=path)['result']
            need(exhausted['valid_submission_count']==0 and exhausted['attempts_observed']==1,
                 'incorrect closure counts')
            need(call('S3_CLOSE_EXECUTION', 0, body_file=path)['result']==exhausted, 'closure retry changed')
            call('ACTIVATE', 0, 'AUDITOR', expect=2)
            decision = call('S3_FINALIZE', 0)['result']
            need(decision['terminal']=='FAILED' and decision['condition']=='EXECUTION_FAILED',
                 'verified exhaustion did not produce FAILED')
            final = call('S3_SETTLE', 0)
            need(final['result']['paid']==0 and final['result']['refund']==bundles[0]['funding']['total_limit'],
                 'FAILED settlement did not refund')
            cases += ['physical_rpr_host_fault', 'self_report_does_not_close',
                      'forged_observer_rejected', 'closure_retry_and_fence',
                      'failed_terminal_and_refund']
            finish(cases, final)
            return
        setup(0)
        original = submit(0)['result']
        need(submit(0)['result'] == original, 'B result retry changed allocation')
        body = c.decode(run(['cat','result-0.cbor'],'B-original',remote=True))
        outcome = c.decode(body['outcome'])
        if args.task_trap:
            need(outcome['outcome'] == 'TRAP_INTEGER_DIVIDE_BY_ZERO', 'unexpected real trap outcome')
            outcome['outcome'] = 'TRAP_UNREACHABLE'
        else:
            outcome['output'] += b'conflict'
        body['outcome'] = c.encode(outcome)
        put({'conflict.cbor':c.encode(body)})
        conflict = call('S3_RESULT',0,'EXECUTOR',body_file='conflict.cbor')['result']
        need(conflict == dict(conflict=True,accepted=original['identity']), 'first result lost')
        submit(0,'AUDITOR')
        decision = call('S3_FINALIZE',0)['result']
        need(decision['method_observation']=='CONCORDANT' and decision['terminal']=='UNRESOLVED',
             'real cross-host result mismatch')
        with ThreadPoolExecutor(max_workers=2) as pool:
            allocations = list(pool.map(lambda _:call('S3_SETTLE',0)['result'],range(2)))
        need(allocations[0]==allocations[1] and allocations[0]['paid']>0, 'concurrent settlement mismatch')
        cases += ['cross_host_rpr_and_result', 'duplicate_and_conflict', 'concurrent_settlement']

        setup(1)
        fault.write_text('DROP_REPLY')
        lost = submit(1,expect=2)
        need(lost['reason']=='incomplete S2 frame', 'result failure was not TCP reply loss')
        need(submit(1)['result']['kind']=='S3_RESULT', 'cross-host result lost after TCP reply drop')
        submit(1,'AUDITOR')
        call('S3_FINALIZE',1)
        for marker, code, status in [('BEFORE_COMMIT',71,'READY'),('AFTER_COMMIT',72,'COMMITTED')]:
            fault.write_text(marker)
            lost = call('S3_SETTLE',1,expect=2)
            need(lost['reason']=='incomplete S2 frame','fault did not interrupt the reply')
            need(proc.wait(timeout=10)==code,'wrong fault boundary')
            stop()
            start()
            recovered = call('S3_SETTLEMENT_STATUS',1)['result']
            need(recovered['status']==status,'recovery status mismatch')
        need(call('S3_SETTLE',1)['result']==recovered['settlement'],'lost settlement reply changed rights')
        cases += ['cross_host_result_reply_loss', 'settlement_before_commit_restart',
                  'settlement_after_commit_restart']

        setup(2)
        submit(2,'AUDITOR')
        now = bundles[2]['receipt']['execution']['deadline']
        clock.write_text(str(now))
        with ThreadPoolExecutor(max_workers=2) as pool:
            late = pool.submit(submit,2,expect=2)
            expiry = pool.submit(call,'S3_FINALIZE',2)
            need(late.result()['reason'] in ("{'error': 'S3b deadline'}",
                 "{'error': 'S3b terminal already committed'}", 'S2 fields'), 'unexpected late result response')
            need(expiry.result()['result']['terminal']=='EXPIRED', 'deadline terminal mismatch')
        final = call('S3_SETTLE',2)
        need(final['result']['fulfillment']['executor']=='MISSING','late result affected fulfillment')
        cases.append('cross_host_deadline_rejection')

        finish(cases, final)
    finally:
        stop()


if __name__ == '__main__':
    main()
