#!/usr/bin/env python3
"""Single-host fault campaign. All mutations are inside disposable test directories."""
import ctypes, hashlib, json, os, pathlib, random, resource, shutil, signal, subprocess, tempfile, threading, time
ROOT=pathlib.Path(__file__).resolve().parents[1]
COORD=ROOT/'target/debug/coordinator'; WORKER=ROOT/'build/worker'; VERIFY=ROOT/'target/debug/aclt-minimal-verifier'
assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0
records=[]; launched=[]; kill_count=0; random_kills=0

def record(group,name,**details):
    records.append(dict(group=group,case=name,passed=True,**details))

def wait_for(test,label,seconds=8):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if test(): return
        time.sleep(.003)
    raise AssertionError('timeout: '+label)

def spawn(args,pause=None,extra=None):
    env={k:v for k,v in os.environ.items() if not k.startswith('ACLT_TEST_')}
    if pause: env['ACLT_TEST_PAUSE']=pause
    if extra: env.update(extra)
    # EFBIG is observed as an I/O error instead of terminating the process via SIGXFSZ.
    p=subprocess.Popen([str(x) for x in args],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                       preexec_fn=lambda:signal.signal(signal.SIGXFSZ,signal.SIG_IGN))
    launched.append(p);return p

def finish(p,success=True):
    out,err=p.communicate(timeout=25)
    assert (p.returncode==0)==success,(p.args,p.returncode,out,err)
    if not success: assert 'ACCEPT count=' not in out,(out,err)
    return out,err

def checkpoint(p,d,name):
    def ready():
        if p.poll() is not None: raise AssertionError((name,p.communicate()))
        path=d/'checkpoint.txt'
        return path.exists() and path.read_text()==name+'\n'
    wait_for(ready,name)

def release(d,name): (d/'checkpoint.release').write_text(name)

def clear_checkpoint(d): (d/'checkpoint.txt').unlink(missing_ok=True)

def live_workers():
    result=[]
    for path in pathlib.Path('/proc').glob('[0-9]*'):
        try:
            if (path/'cmdline').read_bytes().split(b'\0')[0]==os.fsencode(WORKER):
                if (path/'stat').read_text().split(') ',1)[1][0]!='Z': result.append(int(path.name))
        except (FileNotFoundError,ProcessLookupError,PermissionError): pass
    return result

def reap():
    while True:
        try:
            pid,_=os.waitpid(-1,os.WNOHANG)
            if not pid:return
        except ChildProcessError:return

def stop_process(p):
    global kill_count
    assert p.poll() is None,'coordinator completed before random interruption'
    p.kill();p.communicate(timeout=5);assert p.returncode==-9
    kill_count+=1
    wait_for(lambda:not live_workers(),'workers exit after coordinator');reap()

def state(d):
    raw=(d/'state.txt').read_bytes();head,digest,body=raw.split(b'\n',2)
    assert head==b'ACLT-STATE-2' and hashlib.sha256(body).hexdigest().encode()==digest
    lines=body.decode().splitlines();n=int(lines[4])
    return [row.split(' ',2) for row in lines[5:5+n]]

def log(d):
    p=d/'events.tsv'
    return p.read_text() if p.is_file() else ''

def resume(d,pause=None,extra=None):return spawn([COORD,'resume',d],pause,extra)

def verified(d,chunk=4):
    p=subprocess.run([str(VERIFY),str(d/'input.txt'),str(chunk),str(d/'results.txt')],capture_output=True,text=True,timeout=10)
    assert p.returncode==0,(d.name,p.stderr)
    rows=state(d);assert all(row[2]!='PENDING' for row in rows)
    values=list(map(int,(d/'input.txt').read_text().split()))
    assert f'sum={sum(values)} min={min(values)} max={max(values)}' in p.stdout
    before=(d/'results.txt').read_bytes();beforelog=log(d)
    finish(resume(d));assert (d/'results.txt').read_bytes()==before and log(d)==beforelog
    wait_for(lambda:not live_workers(),'no workers after run');reap()
    return [int(row[1]) for row in rows]

def rewrite_state(d,edit):
    lines=(d/'state.txt').read_text().splitlines()[2:];edit(lines)
    body='\n'.join(lines)+'\n'
    (d/'state.txt').write_text('ACLT-STATE-2\n'+hashlib.sha256(body.encode()).hexdigest()+'\n'+body)

stop=threading.Event();samples=[]
def watch():
    while not stop.is_set(): samples.append(len(live_workers()));time.sleep(.003)
monitor=threading.Thread(target=watch,daemon=True);monitor.start()
with tempfile.TemporaryDirectory(prefix='aclt-batch-') as temp:
    base=pathlib.Path(temp);source=base/'source.txt';source.write_text('3 -1 8 0 -7 12 5 2 -3 9\n')
    def start(name,pause=None,extra=None,source_file=source,worker=WORKER):
        d=base/name
        p=spawn([COORD,source_file,4,worker,d,'normal',2000,5],pause,extra)
        return d,p
    def saved(name):
        d,p=start(name,'saved');checkpoint(p,d,'saved');stop_process(p);clear_checkpoint(d);return d
    try:
        # Regression tests for three actual pre-fix publication failures.
        for kind in ('temporary-result-changed','existing-final-result','snapshot-changed'):
            d,p=start(kind,'temp');checkpoint(p,d,'temp')
            original_input=(d/'input.txt').read_bytes()
            if kind=='temporary-result-changed':(d/'results.tmp').write_text('broken\n')
            elif kind=='existing-final-result':(d/'results.txt').write_text('preserve me\n')
            else:(d/'input.txt').write_text('3 -1 8 0 -7 13 5 2 -3 9')
            release(d,'temp');_,err=finish(p,False)
            if kind=='existing-final-result':
                assert (d/'results.txt').read_text()=='preserve me\n';(d/'results.txt').unlink()
            else:assert not (d/'results.txt').exists()
            (d/'input.txt').write_bytes(original_input);finish(resume(d));verified(d)
            record('publication-regression',kind,rejection=err.strip())

        # EIO injection at each atomic-save boundary: first reservation and final result staging.
        for filename,occurrence in [('state.txt',2),('results.tmp',1)]:
            for stage in ('open','write','file_sync','rename','dir_sync'):
                name=f'io-{filename}-{stage}'
                d,p=start(name,extra={'ACLT_TEST_IO_FAIL':f'{filename}:{stage}:{occurrence}'})
                _,err=finish(p,False);assert 'injected I/O failure' in err
                assert not (d/'results.txt').exists()
                before=state(d);finish(resume(d));after=verified(d)
                assert all(a>=int(b[1]) for a,b in zip(after,before))
                record('injected-storage-error',name,rejection=err.strip())
        for filename,stage,occurrence in [('results.txt','publish',1),('results.txt','dir_sync',1),('state.txt','file_sync',8),('events.tsv','write',3)]:
            name=f'io-final-{filename}-{stage}'
            d,p=start(name,extra={'ACLT_TEST_IO_FAIL':f'{filename}:{stage}:{occurrence}'})
            _,err=finish(p,False);assert 'injected I/O failure' in err
            if (d/'results.txt').exists():
                q=subprocess.run([str(VERIFY),str(d/'input.txt'),'4',str(d/'results.txt')],capture_output=True,timeout=5);assert q.returncode==0
            finish(resume(d));verified(d);record('injected-storage-error',name,rejection=err.strip())
        d,p=start('injected-enospc',extra={'ACLT_TEST_IO_FAIL':'state.txt:write:2','ACLT_TEST_IO_ERRNO':'28'})
        _,err=finish(p,False);assert 'No space left' in err
        finish(resume(d));verified(d)
        record('injected-storage-error','ENOSPC',method='injected errno 28; host disk was not filled')

        # Real kernel errors: EFBIG, permission denial, directories in place of files.
        d,p=start('kernel-efbig','saved');checkpoint(p,d,'saved')
        old=(d/'state.txt').read_bytes()
        resource.prlimit(p.pid,resource.RLIMIT_FSIZE,(len(old)-1,len(old)-1))
        release(d,'saved');_,err=finish(p,False);assert 'File too large' in err
        assert (d/'state.txt').read_bytes()==old and not (d/'results.txt').exists()
        finish(resume(d));verified(d);record('kernel-storage-error','EFBIG',method='kernel per-process file size limit')
        assert os.geteuid()!=0,'permission-denied checks require non-root user'
        for target,mode in [('state.txt.writing','file'),('events.tsv','file'),('directory','directory')]:
            d,p=start('permission-'+target,'saved');checkpoint(p,d,'saved')
            path=d if mode=='directory' else d/target
            if mode=='file':path.touch()
            original=path.stat().st_mode & 0o777;path.chmod(0o500 if mode=='directory' else 0o400)
            try:
                release(d,'saved') if mode=='file' else None
                if mode=='directory':
                    # Release file must be created before dropping directory write permission.
                    path.chmod(original);release(d,'saved');path.chmod(0o500)
                _,err=finish(p,False);assert 'Permission denied' in err
            finally:path.chmod(original)
            finish(resume(d));verified(d);record('kernel-storage-error','permission-'+target)
        for target in ('state.txt.writing','block-0-attempt-1.txt','block-0-attempt-1.stderr','results.tmp.writing'):
            d,p=start('directory-conflict-'+target,'saved');checkpoint(p,d,'saved')
            (d/target).mkdir();release(d,'saved');_,err=finish(p,False)
            assert not (d/'results.txt').exists();(d/target).rmdir()
            finish(resume(d));verified(d);record('kernel-storage-error','directory-conflict-'+target)
        for target in ('state.txt.writing','block-0-attempt-1.txt','events.tsv'):
            d,p=start('symlink-'+target,'saved');checkpoint(p,d,'saved')
            sentinel=base/('sentinel-'+target);sentinel.write_text('DO NOT CHANGE')
            (d/target).symlink_to(sentinel);release(d,'saved');finish(p,False)
            assert sentinel.read_text()=='DO NOT CHANGE';(d/target).unlink()
            finish(resume(d));verified(d);record('kernel-storage-error','symlink-'+target)

        # Kills inside save, including a truly partial .writing file.
        for step in ('created','partial','synced','renamed'):
            d=saved('atomic-kill-'+step);old=state(d)
            point='io-state.txt-'+step;p=resume(d,pause=point);checkpoint(p,d,point);stop_process(p)
            current=state(d)
            assert current==old  # First recovery write consumes recovery quota, not a worker attempt.
            limits=(d/'state.txt').read_text().splitlines()[-2].split()
            assert int(limits[3])==int(step=='renamed')
            finish(resume(d));verified(d);record('atomic-write-interruption',step)

        # Strict loading of damaged records and final outputs; no silent reset/recompute.
        template=saved('corruption-template')
        finish(resume(template));verified(template)
        pristine=(template/'state.txt').read_bytes();input_bytes=(template/'input.txt').read_bytes()
        result_bytes=(template/'results.txt').read_bytes()
        semantic={
            'bad-count':lambda x:x.__setitem__(4,'4'),
            'bad-phase':lambda x:x.__setitem__(0,x[0].replace('DONE','UNKNOWN')),
            'bad-chunk-zero':lambda x:x.__setitem__(0,'0 '+x[0].split(' ',1)[1]),
            'bad-timeout':lambda x:x.__setitem__(0,x[0].replace('2000','1')),
            'bad-max-attempts':lambda x:x.__setitem__(0,x[0].replace(' 5 ',' 6 ')),
            'bad-worker-path-hex':lambda x:x.__setitem__(1,'zz'),
            'negative-attempt':lambda x:x.__setitem__(5,'0 -1 '+x[5].split(' ',2)[2]),
            'too-many-attempts':lambda x:x.__setitem__(5,'0 6 '+x[5].split(' ',2)[2]),
            'accepted-with-zero-attempt':lambda x:x.__setitem__(5,'0 0 '+x[5].split(' ',2)[2]),
            'wrong-saved-sum':lambda x:x.__setitem__(5,x[5].replace(' 10 ',' 11 ')),
            'duplicate-block':lambda x:x.__setitem__(6,x[5]),
            'done-with-pending':lambda x:x.__setitem__(5,'0 1 PENDING'),
            'extra-record':lambda x:x.insert(-1,'unexpected'),
            'wrong-footer':lambda x:x.__setitem__(-1,'BROKEN'),
            'noncanonical-number':lambda x:x.__setitem__(5,'0 01 '+x[5].split(' ',2)[2]),
        }
        for name,edit in semantic.items():
            d=base/name;shutil.copytree(template,d);rewrite_state(d,edit)
            before=log(d);finish(resume(d),False);assert log(d)==before
            assert (d/'results.txt').read_bytes()==result_bytes
            record('damaged-record',name)
        for name in ('truncated-state','bad-checksum','missing-state','oversized-state','missing-input','changed-input',
                     'missing-result','changed-result','oversized-result','result-symlink','input-fifo','stale-writing-file'):
            d=base/name;shutil.copytree(template,d)
            if name=='truncated-state':(d/'state.txt').write_bytes(pristine[:-4])
            elif name=='bad-checksum':(d/'state.txt').write_bytes(pristine.replace(b'normal',b'normxl'))
            elif name=='missing-state':(d/'state.txt').unlink()
            elif name=='oversized-state':(d/'state.txt').write_bytes(b'x'*16000001)
            elif name=='missing-input':(d/'input.txt').unlink()
            elif name=='changed-input':(d/'input.txt').write_bytes(input_bytes.replace(b'12',b'13'))
            elif name=='missing-result':(d/'results.txt').unlink()
            elif name=='changed-result':(d/'results.txt').write_text('broken')
            elif name=='oversized-result':(d/'results.txt').write_bytes(b'x'*12000001)
            elif name=='result-symlink':
                (d/'results.txt').unlink();(d/'results.txt').symlink_to(template/'results.txt')
            elif name=='input-fifo':
                (d/'input.txt').unlink();os.mkfifo(d/'input.txt')
            else:(d/'state.txt.writing').write_text('broken unfinished write')
            before=log(d);finish(resume(d),name=='stale-writing-file');assert log(d)==before
            record('damaged-record',name,expected='ignore stale temporary file' if name=='stale-writing-file' else 'reject')
        for name in ('worker-changed','worker-missing'):
            copy=base/(name+'-binary');shutil.copy2(WORKER,copy)
            d,p=start(name,'saved',worker=copy);checkpoint(p,d,'saved');stop_process(p)
            if name=='worker-changed':copy.write_bytes(copy.read_bytes()+b'changed')
            else:copy.unlink()
            before=log(d);finish(resume(d),False);assert log(d)==before and not (d/'results.txt').exists()
            record('damaged-record',name)

        # Four eight-way recovery races. One winner waits while all seven losers exit.
        for trial in range(4):
            d=saved(f'concurrent-{trial}');clear_checkpoint(d)
            contenders=[resume(d,pause='locked') for _ in range(8)]
            wait_for(lambda:sum(p.poll() is not None for p in contenders)==7,'seven lock losers')
            winner=next(p for p in contenders if p.poll() is None);checkpoint(winner,d,'locked')
            for p in contenders:
                if p is not winner:
                    _,err=finish(p,False);assert 'locked' in err
            release(d,'locked');finish(winner);verified(d)
            record('concurrent-recovery',f'eight-way-{trial}',contenders=8,winners=1)

        # Timed SIGKILL after releasing saved-state checkpoint: interruption point varies by scheduling.
        rng=random.Random(20261002)
        for trial in range(24):
            values=[rng.randint(-1000000,1000000) for _ in range(240)]
            inp=base/f'random-input-{trial}.txt';inp.write_text(' '.join(map(str,values)))
            d,p=start(f'random-{trial}','saved',source_file=inp)
            delays=[];previous=None
            for interruption in range(3):
                checkpoint(p,d,'saved');before=state(d)
                release(d,'saved');delay=rng.uniform(.001,.025);delays.append(round(delay*1000,3));time.sleep(delay)
                stop_process(p);random_kills+=1;after=state(d)
                assert all(int(a[1])>=int(b[1]) and (b[2]=='PENDING' or a[2]==b[2]) for a,b in zip(after,before))
                if previous:assert all(int(a[1])>=int(b[1]) for a,b in zip(after,previous))
                previous=after;clear_checkpoint(d)
                if interruption<2:p=resume(d,pause='saved')
            finish(resume(d));attempts=verified(d)
            assert max(attempts)<=5
            record('random-interruption',f'random-{trial}',seed=20261002,delay_ms=delays,sigkills=3,max_attempts=max(attempts),blocks=60)
    finally:
        stop.set();monitor.join(timeout=2)
        for p in launched:
            if p.poll() is None:p.kill();p.communicate(timeout=5)
        for pid in live_workers():
            try:os.kill(pid,signal.SIGKILL)
            except ProcessLookupError:pass
        reap()
        (ROOT/'build/batch-partial.json').write_text(json.dumps(records,indent=2)+'\n')
assert samples and max(samples)<=2,max(samples)
groups={group:sum(r['group']==group for r in records) for group in sorted({r['group'] for r in records})}
report={'passed':len(records),'groups':groups,'actual_sigkills':kill_count,'random_sigkills':random_kills,
        'maximum_live_workers_observed':max(samples),'cases':records,
        'scope':'single-host process and file faults; EIO/ENOSPC injected, EFBIG/EACCES real kernel errors; no disk filling or power cut'}
(ROOT/'build/batch-tests.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'PASS: {len(records)} batch cases; {random_kills} randomized SIGKILLs; groups={groups}')
