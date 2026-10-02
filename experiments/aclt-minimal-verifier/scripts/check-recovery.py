#!/usr/bin/env python3
"""Linux SIGKILL recovery tests with explicit checkpoints, not guessed sleep timing."""
import ctypes, fcntl, hashlib, json, os, pathlib, signal, subprocess, tempfile, threading, time
ROOT=pathlib.Path(__file__).resolve().parents[1]
COORD=ROOT/'target/debug/coordinator'; WORKER=ROOT/'build/worker'; VERIFY=ROOT/'target/debug/aclt-minimal-verifier'
# Adopt and reap workers orphaned by intentionally killing their parent.
assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0, 'PR_SET_CHILD_SUBREAPER failed'
records=[]; evidence=[]; killed=0; launched=[]

def wait_for(predicate,description,seconds=6):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        if predicate(): return
        time.sleep(.005)
    raise AssertionError('timed out: '+description)

def events(d):
    p=d/'events.tsv'
    return [s.split('\t') for s in p.read_text().splitlines()] if p.exists() else []

def starts(d): return [e for e in events(d) if e[0]=='START']

def worker_pids():
    answer=[]
    for path in pathlib.Path('/proc').glob('[0-9]*'):
        try:
            if (path/'cmdline').read_bytes().split(b'\0')[0] == os.fsencode(WORKER):
                if (path/'stat').read_text().split(') ',1)[1][0] != 'Z': answer.append(int(path.name))
        except (FileNotFoundError,ProcessLookupError,PermissionError): pass
    return answer

def reap():
    while True:
        try:
            pid,_=os.waitpid(-1,os.WNOHANG)
            if pid==0: return
        except ChildProcessError: return

def launch(args,pause=None,gate=None):
    env=os.environ.copy()
    env.pop('ACLT_TEST_PAUSE',None);env.pop('ACLT_TEST_WORKER_GATE',None)
    if pause: env['ACLT_TEST_PAUSE']=pause
    if gate: env['ACLT_TEST_WORKER_GATE']=str(gate)
    child=subprocess.Popen([str(x) for x in args],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    launched.append(child)
    return child

def checkpoint(p,d,name):
    def ready():
        if p.poll() is not None:
            out,err=p.communicate();raise AssertionError((name,p.returncode,out,err))
        return (d/'checkpoint.txt').exists() and (d/'checkpoint.txt').read_text()==name+'\n'
    wait_for(ready,name)

def kill_at(p,d,name):
    global killed
    checkpoint(p,d,name)
    p.send_signal(signal.SIGKILL);p.communicate(timeout=5)
    assert p.returncode == -signal.SIGKILL
    killed+=1
    wait_for(lambda: not worker_pids(),'parent-death cleanup')
    reap()
    evidence.append({'directory':d.name,'checkpoint':name,'termination':'SIGKILL','events':events(d)})

def resume(d,success=True,pause=None):
    p=launch([COORD,'resume',d],pause=pause)
    if pause: return p
    out,err=p.communicate(timeout=15)
    assert (p.returncode==0)==success,(d.name,p.returncode,out,err)
    return out,err

def state(d):
    lines=(d/'state.txt').read_text().splitlines()
    assert lines[1]==hashlib.sha256(('\n'.join(lines[2:])+'\n').encode()).hexdigest()
    count=int(lines[6]); rows=[line.split(' ',2) for line in lines[7:7+count]]
    return rows

def completed(d):
    p=subprocess.run([str(VERIFY),str(d/'input.txt'),'4',str(d/'results.txt')],capture_output=True,text=True,timeout=5)
    assert p.returncode==0 and 'sum=28 min=-7 max=12' in p.stdout
    rows=state(d)
    assert all(row[2]!='PENDING' for row in rows)
    accepted=[e[1] for e in events(d) if e[0]=='ACCEPT_BLOCK']
    assert len(accepted)==len(set(accepted))==3
    before=(d/'results.txt').read_bytes();oldstarts=starts(d)
    resume(d);resume(d)
    assert (d/'results.txt').read_bytes()==before and starts(d)==oldstarts
    wait_for(lambda:not worker_pids(),'no surviving workers')
    reap()

def record(name,detail): records.append({'case':name,'passed':True,'checks':detail})

stop=threading.Event();observed=[]
def monitor():
    while not stop.is_set():
        observed.append(len(worker_pids()));time.sleep(.002)
watch=threading.Thread(target=monitor,daemon=True);watch.start()
with tempfile.TemporaryDirectory(prefix='aclt-recovery-') as temp:
    base=pathlib.Path(temp);source=base/'source.txt';source.write_text('3 -1 8 0 -7 12 5 2 -3 9\n')
    def new(name,pause,scenario='normal',maximum=3,gate=None):
        d=base/name
        p=launch([COORD,source,4,WORKER,d,scenario,1000,maximum],pause,gate)
        return d,p
    try:
        for case,pause in [('R01','saved'),('R02','reserved')]:
            d,p=new(case,pause);kill_at(p,d,pause)
            before=state(d);resume(d);completed(d)
            if case=='R02': assert before[0][1]=='1' and state(d)[0][1]=='2' and not any(e[1:3]==['0','1'] for e in starts(d))
            record(case,'resume from durable input or consumed reservation; no refunded attempt')

        gate=base/'allow-workers'
        d,p=new('R03','running',gate=gate);checkpoint(p,d,'running')
        wait_for(lambda:len(worker_pids())==2,'two live gated C++ processes')
        oldpids=worker_pids();kill_at(p,d,'running')
        assert not any(pathlib.Path(f'/proc/{pid}').exists() for pid in oldpids)
        resume(d);completed(d)
        assert state(d)[0][1]==state(d)[1][1]=='2'
        record('R03','two live workers die with coordinator; new workers start only after cleanup')

        for case,pause in [('R04','output'),('R05','accepted'),('R06','timeout'),('R07','temp'),('R08','published')]:
            d,p=new(case,pause,scenario='slow' if case=='R06' else 'normal')
            kill_at(p,d,pause);oldstarts=starts(d)
            published=(d/'results.txt').read_bytes() if (d/'results.txt').exists() else None
            resume(d);completed(d)
            if case in ('R04','R06'): assert state(d)[0][1]=='2'
            if case=='R05': assert sum(e[1]=='0' for e in starts(d))==1
            if case in ('R07','R08'): assert starts(d)==oldstarts
            if case=='R08': assert (d/'results.txt').read_bytes()==published and any(e[0]=='COMPLETE_RECOVERED' for e in events(d))
            record(case,'correct recovery at '+pause+'; exact-once counting and final verification')

        d,p=new('R09','saved');kill_at(p,d,'saved')
        owner=resume(d,pause='locked');checkpoint(owner,d,'locked')
        out,err=resume(d,False);assert 'locked' in err and not starts(d)
        (d/'checkpoint.release').write_text('locked');out,err=owner.communicate(timeout=15)
        assert owner.returncode==0,(out,err);completed(d)
        # A separate holder of the same kernel lock also prevents recovery.
        with (d/'run.lock').open('r+') as lease:
            fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
            _,err=resume(d,False);assert 'locked' in err
        record('R09','concurrent recovery excluded by OS lock; completed resume is idempotent')

        d,p=new('R10','reserved',maximum=2);kill_at(p,d,'reserved')
        (d/'checkpoint.txt').unlink()
        p=resume(d,pause='reserved');kill_at(p,d,'reserved')
        out,err=resume(d,False);assert 'budget exhausted' in err
        assert state(d)[0][1]=='2' and not (d/'results.txt').exists() and not starts(d)
        record('R10','two interrupted reservations consume both attempts; restart cannot reset budget')

        d,p=new('R11','saved');kill_at(p,d,'saved')
        original=(d/'state.txt').read_bytes();original_input=(d/'input.txt').read_bytes()
        corruptions=[('truncated',original[:-7]),('checksum',original.replace(b'normal',b'normxl'))]
        for label,bad in corruptions:
            (d/'state.txt').write_bytes(bad);_,err=resume(d,False)
            assert 'checksum' in err and not starts(d)
        (d/'state.txt').write_bytes(original)
        (d/'input.txt').write_bytes(original_input.replace(b'12',b'13'))
        _,err=resume(d,False);assert 'snapshot mismatch' in err and not starts(d)
        (d/'input.txt').write_bytes(original_input)
        # Even a self-consistent checksum must not bypass semantic validation.
        lines=original.decode().splitlines();lines[7]='0 4 PENDING'
        body='\n'.join(lines[2:])+'\n';lines[1]=hashlib.sha256(body.encode()).hexdigest()
        (d/'state.txt').write_text('\n'.join(lines)+'\n')
        _,err=resume(d,False);assert 'attempts invalid' in err and not starts(d)
        (d/'state.txt').write_bytes(original);resume(d);completed(d)
        record('R11','truncation, checksum corruption, snapshot mismatch, invalid count all fail closed')

        d,p=new('R12','output');kill_at(p,d,'output')
        old=(d/'block-0-attempt-1.txt').read_bytes()
        (d/'checkpoint.txt').unlink()
        p=resume(d,pause='reserved');checkpoint(p,d,'reserved')
        assert state(d)[0][1]=='2'
        # Inject an old valid result after restart; old worker itself is already dead.
        (d/'block-0-attempt-1.txt').write_bytes(old)
        (d/'checkpoint.release').write_text('reserved');out,err=p.communicate(timeout=15)
        assert p.returncode==0,(out,err);completed(d)
        assert any(e[:3]==['ACCEPT_BLOCK','0','2'] for e in events(d))
        assert not any(e[:3]==['ACCEPT_BLOCK','0','1'] for e in events(d))
        record('R12','delayed old-file replay after restart ignored; only attempt 2 accepted')
    finally:
        stop.set();watch.join(timeout=2)
        # Any assertion failure still cleans up this test's live children.
        for child in launched:
            if child.poll() is None:
                child.kill();child.communicate(timeout=5)
        for pid in worker_pids():
            try: os.kill(pid,signal.SIGKILL)
            except ProcessLookupError: pass
        reap()
assert observed and max(observed)<=2, observed
report={'cases':records,'passed':len(records),'sigkill_count':killed,'maximum_live_workers_observed':max(observed),
        'scope':'SIGKILL of coordinator; OS remains alive; R12 replays old file, not a surviving old worker'}
(ROOT/'build/recovery-tests.json').write_text(json.dumps(report,indent=2)+'\n')
(ROOT/'build/recovery-events.json').write_text(json.dumps(evidence,indent=2)+'\n')
print(f'PASS: {len(records)} recovery scenarios; {killed} actual coordinator SIGKILLs; maximum observed live workers={max(observed)}')
