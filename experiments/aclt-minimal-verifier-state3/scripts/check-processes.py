#!/usr/bin/env python3
"""End-to-end tests: real Rust coordinator and real C++ child processes."""

if not __debug__:
    raise SystemExit('assert-based validation requires Python without -O/PYTHONOPTIMIZE')

import json, os, pathlib, subprocess, tempfile
ROOT = pathlib.Path(__file__).resolve().parents[1]
COORD = ROOT/'target/debug/coordinator'
WORKER = ROOT/'build/worker'
VERIFY = ROOT/'target/debug/aclt-minimal-verifier'
records = []
def run(args):
    return subprocess.run([str(x) for x in args], capture_output=True, text=True, timeout=20)

def events(directory):
    return [line.split('\t') for line in (directory/'events.tsv').read_text().splitlines()]

with tempfile.TemporaryDirectory() as temp:
    base = pathlib.Path(temp)
    source = base/'source.txt'
    source.write_text('3 -1 8 0 -7 12 5 2 -3 9\n')
    def scenario(name, expected_event=None, maximum=2, success=True):
        directory = base/f'{name}-{maximum}'
        command = [COORD,source,4,WORKER,directory,name,500,maximum]
        proc = run(command)
        assert (proc.returncode == 0) == success, (name,proc.stdout,proc.stderr)
        log = events(directory)
        if expected_event:
            assert any(e[0] == expected_event and e[1] == '0' and e[2] == '1' for e in log), (name,log)
        # Started processes have been reaped at success and at attempt-budget failure.
        for e in log:
            if e[0] == 'START':
                pid = int(e[3].split()[0].split('=')[1])
                assert not pathlib.Path(f'/proc/{pid}').exists(), (name,'process still alive',pid)
        if success:
            accepted = [int(e[1]) for e in log if e[0] == 'ACCEPT_BLOCK']
            assert sorted(accepted) == [0,1,2] and len(accepted) == len(set(accepted))
            assert log[-1][0] == 'COMPLETE'
            # Independent CLI verifies persisted result against persisted input.
            checked = run([VERIFY,directory/'input.txt',4,directory/'results.txt'])
            assert checked.returncode == 0 and 'sum=28 min=-7 max=12' in checked.stdout
            assert not (directory/'results.tmp').exists()
            if name != 'normal':
                assert any(e[:3] == ['START','0','2'] for e in log)
                assert not any(e[:3] == ['ACCEPT_BLOCK','0','1'] for e in log)
            if name == 'normal':
                assert log[0][0] == log[1][0] == 'START'
                assert log[0][3].split()[0] != log[1][3].split()[0]
            if name == 'slow':
                assert any(e[:3] == ['STALE','0','1'] for e in log)
                assert log.index(next(e for e in log if e[:3] == ['ACCEPT_BLOCK','0','2'])) < log.index(next(e for e in log if e[:3] == ['STALE','0','1']))
            old = (directory/'results.txt').read_bytes()
            rerun = run(command)
            assert rerun.returncode != 0 and (directory/'results.txt').read_bytes() == old
        else:
            assert 'budget exhausted' in proc.stderr
            assert not (directory/'results.txt').exists()
            assert not any(e[0] == 'COMPLETE' for e in log)
            assert sum(e[0] == 'START' and e[1] == '0' for e in log) == maximum
        records.append({'scenario':name,'max_attempts':maximum,'expected_success':success,'passed':True})
        return directory
    scenario('normal')
    for name, event in [('slow','TIMEOUT'),('wrong','REJECT_BLOCK'),('crash','REJECT_BLOCK'),
                        ('hang','KILL'),('duplicate','REJECT_BLOCK'),('malformed','REJECT_BLOCK'),
                        ('wrong-attempt','REJECT_BLOCK')]:
        scenario(name,event)
    scenario('always-wrong','REJECT_BLOCK',2,False)
    scenario('hang','TIMEOUT',1,False)
    scenario('crash','REJECT_BLOCK',1,False)
    # A failed launch must not publish final results.
    directory=base/'launch-failure'
    bad_worker=base/'not-executable'; bad_worker.write_text('not executable')
    proc=run([COORD,source,4,bad_worker,directory,'normal',500,2])
    assert proc.returncode != 0 and not (directory/'results.txt').exists()
    records.append({'scenario':'launch-failure','passed':True})
(ROOT/'build/process-tests.json').write_text(json.dumps(records,indent=2)+'\n')
print(f'PASS: {len(records)} multi-process scenarios; retries, late results, attempt limits, cleanup, and overwrite refusal checked')
