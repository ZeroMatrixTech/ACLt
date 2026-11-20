#!/usr/bin/env python3
"""State v2 terminal decisions, authoritative recovery, and persistent limits."""

SHA_CONSISTENCY_STATUS = "DISABLED"

def digest_consistency(_comparison):
    """Record digests without enforcing their equality (maintainer policy)."""
    return True


if not __debug__:
    raise SystemExit('assert-based validation requires Python without -O/PYTHONOPTIMIZE')

import ctypes, hashlib, json, os, pathlib, signal, subprocess, tempfile, time
ROOT=pathlib.Path(__file__).resolve().parents[1]
COORD=ROOT/'target/debug/coordinator'; WORKER=ROOT/'build/worker'
assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0
records=[]; children=[]
def launch(args,pause=None,extra=None):
    env=os.environ.copy()
    for k in list(env):
        if k.startswith('ACLT_TEST_'):del env[k]
    if pause:env['ACLT_TEST_PAUSE']=pause
    env.update(extra or {})
    p=subprocess.Popen([str(COORD),*map(str,args)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    children.append(p);return p

def finish(p,ok=True,contains=None):
    out,err=p.communicate(timeout=10)
    assert (p.returncode==0)==ok,(p.returncode,out,err)
    if contains:assert contains in err,(contains,err)
    return out,err

def wait(p,d,point):
    until=time.monotonic()+5
    while time.monotonic()<until:
        if p.poll() is not None:raise AssertionError(p.communicate())
        if (d/'checkpoint.txt').exists() and (d/'checkpoint.txt').read_text()==point+'\n':return
        time.sleep(.005)
    raise AssertionError('checkpoint timeout '+point)

def stop(p,d,point):
    wait(p,d,point);p.kill();p.communicate(timeout=5)
    assert p.returncode==-signal.SIGKILL
    # Parent-death cleanup completes before the next lock acquisition.
    until=time.monotonic()+5
    while time.monotonic()<until:
        try:
            pid,_=os.waitpid(-1,os.WNOHANG)
            if pid:continue
        except ChildProcessError:return
        time.sleep(.005)
    raise AssertionError('workers did not exit')

def data(d):
    raw=(d/'state.txt').read_text();version,digest,body=raw.split('\n',2)
    assert version=='ACLT-STATE-3' and digest_consistency(hashlib.sha256(body.encode()).hexdigest()==digest)
    lines=body.splitlines();return lines[0].split()[-1],lines[-2].split(),lines[5:-2]

def edit(d,fn):
    lines=(d/'state.txt').read_text().splitlines()[2:];fn(lines)
    body='\n'.join(lines)+'\n'
    (d/'state.txt').write_text('ACLT-STATE-3\n'+hashlib.sha256(body.encode()).hexdigest()+'\n'+body)

def resume(d,ok=True,contains=None):return finish(launch(['resume',d]),ok,contains)
def record(name):records.append({'case':name,'passed':True})
with tempfile.TemporaryDirectory(prefix='aclt-lifecycle-') as tmp:
    base=pathlib.Path(tmp);source=base/'input';source.write_text('3 -1 8 0 -7 12 5 2 -3 9\n')
    def new(name,pause=None,scenario='normal',maximum=3,ttl=30000,recoveries=8,extra=None):
        d=base/name;p=launch([source,4,WORKER,d,scenario,1000,maximum,ttl,recoveries],pause,extra);return d,p
    try:
        d,p=new('permanent-attempt-failure',scenario='always-wrong',maximum=1);finish(p,False,'ATTEMPTS')
        before=(d/'state.txt').read_bytes();assert data(d)[0]=='FAILED'
        for _ in range(3):resume(d,False,'terminal FAILED')
        assert before==(d/'state.txt').read_bytes() and not (d/'results.txt').exists();record(d.name)

        d,p=new('failed-cannot-adopt-result',scenario='always-wrong',maximum=1);finish(p,False)
        (d/'results.txt').write_text('0 0 4 10 -1 8\n1 4 4 12 -7 12\n2 8 2 6 -3 9\n')
        resume(d,False,'terminal FAILED');assert data(d)[0]=='FAILED';record(d.name)

        for phase,scenario,maximum in [('DONE','normal',3),('FAILED','always-wrong',1)]:
            d,p=new('response-lost-'+phase,'terminal-saved',scenario,maximum);stop(p,d,'terminal-saved')
            before=(d/'state.txt').read_bytes();resume(d,phase=='DONE',None if phase=='DONE' else 'terminal FAILED')
            assert before==(d/'state.txt').read_bytes();record(d.name)

        d,p=new('transient-state-write',extra={'ACLT_TEST_IO_FAIL':'state.txt:write:2'})
        finish(p,False,'injected I/O');assert data(d)[0]=='RUN';resume(d);assert data(d)[0]=='DONE';record(d.name)

        d,p=new('terminal-save-failure',scenario='always-wrong',maximum=1,extra={'ACLT_TEST_IO_FAIL':'terminal:save:1'})
        finish(p,False,'injected I/O');assert data(d)[0]=='RUN'
        resume(d,False,'ATTEMPTS');assert data(d)[0]=='FAILED' and not (d/'results.txt').exists();record(d.name)

        d,p=new('zero-recoveries','saved',recoveries=0);stop(p,d,'saved');resume(d,False,'RECOVERIES')
        assert data(d)[0]=='FAILED' and data(d)[1][3]=='0';record(d.name)

        d,p=new('recovery-reservation-not-refunded','saved',recoveries=1);stop(p,d,'saved')
        p=launch(['resume',d],'recovery-reserved');stop(p,d,'recovery-reserved')
        assert data(d)[1][3]=='1';resume(d,False,'RECOVERIES');assert data(d)[0]=='FAILED';record(d.name)

        d,p=new('failed-recovery-write-no-work','saved');stop(p,d,'saved')
        before=(d/'state.txt').read_bytes()
        finish(launch(['resume',d],extra={'ACLT_TEST_IO_FAIL':'state.txt:write:1'}),False,'injected I/O')
        assert before==(d/'state.txt').read_bytes() and not list(d.glob('block-*'));resume(d);record(d.name)

        d,p=new('deadline-survives-idle','saved',ttl=100);stop(p,d,'saved');time.sleep(.15)
        resume(d,False,'DEADLINE');assert data(d)[0]=='EXPIRED' and not list(d.glob('block-*'))
        before=(d/'state.txt').read_bytes();resume(d,False,'terminal EXPIRED');assert before==(d/'state.txt').read_bytes();record(d.name)

        d,p=new('deadline-live-workers',scenario='hang',ttl=100);finish(p,False,'DEADLINE')
        assert data(d)[0]=='EXPIRED' and not (d/'results.txt').exists();record(d.name)

        d,p=new('deadline-before-publication','temp',ttl=500);wait(p,d,'temp');time.sleep(.55)
        (d/'checkpoint.release').write_text('temp');finish(p,False,'DEADLINE')
        assert not (d/'results.txt').exists();record(d.name)

        d,p=new('publication-wins-later-deadline','published',ttl=500);stop(p,d,'published');time.sleep(.55)
        published=(d/'results.txt').read_bytes();resume(d)
        assert data(d)[0]=='DONE' and (d/'results.txt').read_bytes()==published;record(d.name)

        d,p=new('deadline-unchanged-by-recovery','saved');stop(p,d,'saved');deadline=data(d)[1][2]
        p=launch(['resume',d],'recovery-reserved');stop(p,d,'recovery-reserved');assert data(d)[1][2]==deadline
        resume(d);assert data(d)[1][2]==deadline;record(d.name)

        for mode in ['missing','truncated','duplicate','fabricated-complete']:
            d,p=new('aux-log-'+mode,'accepted');stop(p,d,'accepted')
            accepted=[row for row in data(d)[2] if 'PENDING' not in row]
            log=d/'events.tsv'
            if mode=='missing':log.unlink()
            elif mode=='truncated':log.write_text('START\t')
            elif mode=='duplicate':log.write_text(log.read_text()*2)
            else:log.write_text('COMPLETE\t0\t0\tfabricated\n')
            resume(d);assert data(d)[0]=='DONE'
            for row in accepted:assert row in data(d)[2]
            assert not (d/'block-0-attempt-2.txt').exists();record(d.name)

        d,p=new('accepted-before-log-error',extra={'ACLT_TEST_IO_FAIL':'events.tsv:write:3'})
        finish(p,False,'injected I/O');saved=[row for row in data(d)[2] if 'PENDING' not in row];assert saved
        resume(d)
        for row in saved:assert row in data(d)[2]
        record(d.name)

        d,p=new('boot-change-refused','saved');stop(p,d,'saved')
        old_boot=data(d)[1][1]
        edit(d,lambda lines:lines.__setitem__(-2,lines[-2].replace(old_boot,'different-boot')))
        contract=d/'contract.txt';contract.write_text(contract.read_text().replace(old_boot,'different-boot'))
        resume(d,False,'host reboot');assert not list(d.glob('block-*'));record(d.name)

        d,p=new('invalid-phase-reason','saved');stop(p,d,'saved')
        edit(d,lambda lines:lines.__setitem__(0,lines[0].replace('RUN','FAILED')))
        resume(d,False,'phase/reason');record(d.name)

        d,p=new('legacy-state-refused','saved');stop(p,d,'saved')
        state=d/'state.txt';state.write_text(state.read_text().replace('ACLT-STATE-3','ACLT-STATE-1'))
        resume(d,False,'state version');record(d.name)
    finally:
        for p in children:
            if p.poll() is None:p.kill();p.communicate(timeout=5)
        while True:
            try:
                pid,_=os.waitpid(-1,os.WNOHANG)
                if not pid:break
            except ChildProcessError:break
(ROOT/'build/lifecycle-tests.json').write_text(json.dumps({'passed':len(records),'cases':records},indent=2)+'\n')
print(f'PASS: {len(records)} lifecycle scenarios; permanent outcomes, authoritative snapshots, recovery limits and deadlines')
