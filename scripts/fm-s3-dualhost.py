#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the candidate FM-S3 LAN closeout with an A authority and a B executor."""
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
from tools.formal_migration import policy, s2, s2_evidence, s2_fixture, s2_worker, s3_authority
from tools.verification_profile import codec as c

BASE = runpy.run_path(str(ROOT/'scripts/fm-s2-dualhost.py'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('peer', 'a-host', 'remote-root'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+', args.peer):
        parser.error('explicit user@host required')
    if not re.fullmatch(r'/tmp/fm-s3-[A-Za-z0-9_.-]+', args.remote_root):
        parser.error('new dedicated /tmp/fm-s3-* directory required')
    output = args.output.resolve()
    output.mkdir(mode=0o700)
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
if any(hashlib.sha256(Path(k).read_bytes()).hexdigest()!=v for k,v in pins.items()):
    raise SystemExit('B source hash mismatch')
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
    need(run(['sha256sum','executor'], 'B-binary', remote=True).split()[0].decode() == digest.hex(),
         'runtime pins differ')

    private = output/'private'
    cfg, templates = s2_fixture.build(ROOT, private, digest, count=3)
    bundles = [s3_authority.bind_bundle(bundle) for bundle in templates]
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
    def call(op, index, role='REQUESTER', *, expect=0, **extra):
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
            return json.loads(stdout)
        if op == 'WORK':
            return None
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

    cases = []
    try:
        start()
        setup(0)
        original = submit(0)['result']
        need(submit(0)['result'] == original, 'B result retry changed allocation')
        body = c.decode(run(['cat','result-0.cbor'],'B-original',remote=True))
        outcome = c.decode(body['outcome'])
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
        summary = dict(status='PASS', scenarios=cases, runtime_sha256=digest.hex(), replay=replay,
                       genesis=s2.h(cfg).hex(), total=cfg['balance'], available=state['free'], paid=paid,
                       holdings=state['held'], source_manifest_sha256=hashlib.sha256(
                           (output/'source-sha256.json').read_bytes()).hexdigest())
        (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        print(json.dumps(summary,indent=2))
    finally:
        stop()


if __name__ == '__main__':
    main()
