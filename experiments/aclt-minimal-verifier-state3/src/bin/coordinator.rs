#[path = "support/admission.rs"]
mod admission;
use aclt_minimal_verifier::{chunk_size, expected, fields, input, read, summary, verify};
use std::{collections::VecDeque, env, fs::{self, File, OpenOptions}, io::Write,
    os::unix::{process::CommandExt, fs::OpenOptionsExt}, path::{Path, PathBuf}, process::{self, Child, Command, Stdio},
    thread, time::{Duration, Instant}, sync::atomic::{AtomicU64, Ordering}};

// Linux-only lifecycle protection; no external Rust dependencies.
extern "C" { fn prctl(option: i32, ...) -> i32; fn getppid() -> i32; fn setrlimit(resource: i32, limit: *const RLimit) -> i32; }
#[repr(C)]
struct RLimit { current: u64, maximum: u64 }
#[cfg(feature="test-faults")]
use std::sync::atomic::AtomicUsize;

static STORAGE_CAP: AtomicU64=AtomicU64::new(0);
static STATE_RESERVE: AtomicU64=AtomicU64::new(0);
static LOG_CAP: AtomicU64=AtomicU64::new(1_048_576);

struct Job { child: Child, id: usize, attempt: usize, start: Instant, expired: bool, output: PathBuf }
impl Drop for Job { fn drop(&mut self) { let _ = self.child.kill(); let _ = self.child.wait(); } }
struct State {
    chunk: usize, timeout_ms: usize, maximum: usize, scenario: String, phase: String,
    verify_used: u64, verify_limit: u64, storage_limit: u64, log_limit: u64, task_id: String,
    boot: String, deadline_ms: u64, recoveries: u64, recovery_limit: u64, reason: String,
    worker: PathBuf, worker_hash: String, values: Vec<i64>, attempts: Vec<usize>, accepted: Vec<Option<String>>,
}
fn hex(bytes: &[u8]) -> String { bytes.iter().map(|x| format!("{x:02x}")).collect() }
fn hash(data: &[u8]) -> Result<String,String> {
    let mut child = Command::new("sha256sum").stdin(Stdio::piped()).stdout(Stdio::piped()).spawn().map_err(|e|e.to_string())?;
    let written = child.stdin.take().unwrap().write_all(data);
    let output = child.wait_with_output().map_err(|e|e.to_string())?;
    written.map_err(|e|e.to_string())?;
    if !output.status.success() { return Err("sha256sum failed".into()); }
    let text = String::from_utf8(output.stdout).map_err(|e|e.to_string())?;
    let digest = text.split_whitespace().next().ok_or("missing checksum")?;
    if digest.len()!=64 { return Err("invalid checksum".into()); }
    Ok(digest.into())
}
fn snapshot(values: &[i64]) -> String { values.iter().map(i64::to_string).collect::<Vec<_>>().join(" ") }
fn body(s: &State) -> Result<String,String> {
    let mut text = format!("{} {} {} {} {}\n{}\n{}\n{}\n{}\n",s.chunk,s.timeout_ms,s.maximum,s.scenario,
        &s.phase,hex(s.worker.to_str().ok_or("non-UTF8 path")?.as_bytes()),s.worker_hash,
        snapshot(&s.values),s.attempts.len());
    for id in 0..s.attempts.len() { text.push_str(&format!("{id} {} {}\n",s.attempts[id],s.accepted[id].as_deref().unwrap_or("PENDING"))); }
    text.push_str(&format!("LIMITS {} {} {} {} {} {} {} {} {} {}\nEND\n",s.boot,s.deadline_ms,s.recoveries,s.recovery_limit,s.reason,s.verify_used,s.verify_limit,s.storage_limit,s.log_limit,s.task_id)); Ok(text)
}
// Fault hooks are opt-in and only used by the local failure-injection tests.
#[cfg(not(feature="test-faults"))]
fn io_fault(_name: &str, _stage: &str) -> Result<(),String> { Ok(()) }
#[cfg(feature="test-faults")]
fn io_fault(name: &str, stage: &str) -> Result<(),String> {
    static MATCHES: AtomicUsize=AtomicUsize::new(0);
    if let Ok(spec)=env::var("ACLT_TEST_IO_FAIL") {
        let fields=spec.split(':').collect::<Vec<_>>();
        if fields.len()==3 && fields[0]==name && fields[1]==stage {
            let occurrence=MATCHES.fetch_add(1,Ordering::SeqCst)+1;
            if fields[2].parse::<usize>().ok()==Some(occurrence) {
                let errno=env::var("ACLT_TEST_IO_ERRNO").ok().and_then(|v|v.parse::<i32>().ok()).unwrap_or(5);
                return Err(format!("injected I/O failure {name}:{stage}: {}",std::io::Error::from_raw_os_error(errno)));
            }
        }
    }
    Ok(())
}
fn output_file(path: &Path) -> Result<File,String> {
    // Linux O_NOFOLLOW: stale symbolic links must not redirect output writes.
    OpenOptions::new().write(true).create(true).truncate(true).custom_flags(0x20000)
        .open(path).map_err(|e|format!("{}: {e}",path.display()))
}
fn sync_directory(directory: &Path) -> Result<(),String> {
    File::open(directory).and_then(|f|f.sync_all()).map_err(|e|e.to_string())
}
fn atomic(directory: &Path, name: &str, data: &[u8]) -> Result<(),String> {
    storage_guard(directory,data.len() as u64)?;
    let tmp=directory.join(format!("{name}.writing"));
    io_fault(name,"open")?;
    let mut f=output_file(&tmp)?;
    checkpoint(directory,&format!("io-{name}-created"))?;
    let middle=data.len()/2;
    f.write_all(&data[..middle]).map_err(|e|e.to_string())?;
    checkpoint(directory,&format!("io-{name}-partial"))?;
    io_fault(name,"write")?;
    f.write_all(&data[middle..]).map_err(|e|e.to_string())?;
    io_fault(name,"file_sync")?;f.sync_all().map_err(|e|e.to_string())?;
    checkpoint(directory,&format!("io-{name}-synced"))?;
    io_fault(name,"rename")?;
    fs::rename(tmp,directory.join(name)).map_err(|e|e.to_string())?;
    checkpoint(directory,&format!("io-{name}-renamed"))?;
    io_fault(name,"dir_sync")?;sync_directory(directory)
}
fn save(directory: &Path,s: &State) -> Result<(),String> {
    let body=body(s)?;
    atomic(directory,"state.txt",format!("ACLT-STATE-3\n{}\n{body}",hash(body.as_bytes())?).as_bytes())
}
fn validate_config(chunk: usize,timeout: usize,maximum: usize,scenario: &str) -> Result<(),String> {
    if !(1..=100000).contains(&chunk) || !(50..=10000).contains(&timeout) || !(1..=5).contains(&maximum) { return Err("configuration out of range".into()); }
    if !["normal","slow","wrong","crash","hang","duplicate","malformed","wrong-attempt","always-wrong"].contains(&scenario) { return Err("unknown scenario".into()); }
    Ok(())
}
#[cfg(not(feature="test-faults"))]
fn checkpoint(_directory: &Path, _name: &str) -> Result<(),String> { Ok(()) }
#[cfg(feature="test-faults")]
fn checkpoint(directory: &Path,name: &str) -> Result<(),String> {
    if env::var("ACLT_TEST_PAUSE").ok().as_deref()==Some(name) {
        atomic(directory,"checkpoint.txt",format!("{name}\n").as_bytes())?;
        // Driver can SIGKILL or explicitly release; never wait without a bound.
        let until=Instant::now()+Duration::from_secs(20);
        while Instant::now()<until {
            if fs::read_to_string(directory.join("checkpoint.release")).ok().as_deref()==Some(name) {
                fs::remove_file(directory.join("checkpoint.release")).map_err(|e|e.to_string())?;
                return Ok(());
            }
            thread::sleep(Duration::from_millis(5));
        }
        return Err(format!("test checkpoint {name} was not interrupted"));
    }
    Ok(())
}
fn event(log: &mut File,kind: &str,id: usize,attempt: usize,detail: &str) -> Result<(),String> {
    let row=format!("{kind}\t{id}\t{attempt}\t{detail}\n");
    if log.metadata().map_err(|e|e.to_string())?.len().saturating_add(row.len() as u64)>LOG_CAP.load(Ordering::SeqCst) {return Err("quota:LOG".into());}
    // /proc/self/fd resolves only this already opened diagnostic file.
    let path=fs::read_link(format!("/proc/self/fd/{}",std::os::fd::AsRawFd::as_raw_fd(log))).map_err(|e|e.to_string())?;
    storage_guard(path.parent().ok_or("missing log parent")?,row.len() as u64)?;
    io_fault("events.tsv","write")?;
    writeln!(log,"{kind}\t{id}\t{attempt}\t{detail}").map_err(|e|e.to_string())?;
    log.flush().map_err(|e|e.to_string())
}
fn retry(queue: &mut VecDeque<usize>,id: usize,attempt: usize,maximum: usize) -> Result<(),String> {
    if attempt>=maximum { return Err(format!("block {id}: attempt budget exhausted ({maximum})")); }
    queue.push_back(id); Ok(())
}
// /proc uptime is shared across processes and includes suspend on Linux.
// Bind it to the boot ID: this experiment refuses automatic cross-boot recovery.
fn boot_id() -> Result<String,String> {
    fs::read_to_string("/proc/sys/kernel/random/boot_id").map(|s|s.trim().into()).map_err(|e|e.to_string())
}
fn uptime_ms() -> Result<u64,String> {
    let raw=fs::read_to_string("/proc/uptime").map_err(|e|e.to_string())?;
    let value=raw.split_whitespace().next().ok_or("missing uptime")?;
    let (seconds,fraction)=value.split_once('.').ok_or("invalid uptime")?;
    let seconds=seconds.parse::<u64>().map_err(|_|"invalid uptime")?;
    let milliseconds=format!("{fraction:0<3}");
    seconds.checked_mul(1000).and_then(|v|v.checked_add(milliseconds[..3].parse::<u64>().ok()?)).ok_or("uptime overflow".into())
}
fn terminal(directory: &Path,s: &mut State,phase: &str,reason: &str) -> Result<(),String> {
    s.phase=phase.into(); s.reason=reason.into();
    io_fault("terminal","save")?;
    let reserve=STATE_RESERVE.swap(0,Ordering::SeqCst);
    let saved=save(directory,s); STATE_RESERVE.store(reserve,Ordering::SeqCst); saved?;
    checkpoint(directory,"terminal-saved")?;
    Err(format!("terminal {phase}: {reason} (budget exhausted or deadline reached)"))
}
fn check_deadline(directory: &Path,s: &mut State) -> Result<(),String> {
    if uptime_ms()?>=s.deadline_ms {return terminal(directory,s,"EXPIRED","DEADLINE");}
    Ok(())
}
fn contract(s: &State) -> Result<String,String> {
    Ok(format!("ACLT-LOCAL-CONTRACT-1\nstats-int-v1\n{}\n{} {} {} {}\n{}\n{}\n{}\n{} {} {} {} {} {}\n",s.task_id,
        s.chunk,s.timeout_ms,s.maximum,s.scenario,hex(s.worker.to_str().ok_or("non-UTF8 path")?.as_bytes()),s.worker_hash,
        hash(snapshot(&s.values).as_bytes())?,s.boot,s.deadline_ms,s.recovery_limit,s.verify_limit,s.storage_limit,s.log_limit))
}
fn configure_limits(s: &State) -> Result<(),String> {
    STORAGE_CAP.store(s.storage_limit,Ordering::SeqCst);
    LOG_CAP.store(s.log_limit,Ordering::SeqCst);
    // Enough headroom for every pending row to become a maximal accepted row,
    // plus a terminal snapshot and two bounded worker files. Not filesystem blocks.
    STATE_RESERVE.store((body(s)?.len() as u64+s.attempts.len() as u64*128+1024)*2,Ordering::SeqCst);
    Ok(())
}
fn storage_guard(directory: &Path,extra: u64) -> Result<(),String> {
    let cap=STORAGE_CAP.load(Ordering::SeqCst); if cap==0 {return Ok(());}
    let mut total=extra.saturating_add(STATE_RESERVE.load(Ordering::SeqCst)).saturating_add(1024);
    for entry in fs::read_dir(directory).map_err(|e|e.to_string())? {
        let entry=entry.map_err(|e|e.to_string())?;
        let meta=fs::symlink_metadata(entry.path()).map_err(|e|e.to_string())?;
        if meta.is_file() {total=total.saturating_add(meta.len());}
    }
    if total>cap {Err("quota:STORAGE".into())} else {Ok(())}
}
fn charge_verification(directory: &Path,s: &mut State,units: u64) -> Result<(),String> {
    if units>s.verify_limit-s.verify_used {return Err("quota:VERIFY".into());}
    s.verify_used+=units; io_fault("verification","save")?; save(directory,s)?;
    checkpoint(directory,"verification-reserved")?; Ok(())
}
fn run() -> Result<(),String> {
    let mut args=env::args().collect::<Vec<_>>();
    if args.get(1).map(String::as_str)==Some("resume") {
        return Err("continuation disabled: interrupted qualification is never refunded".into());
    }
    if args.len()==3 && args[1]=="init-registry" {return admission::init(Path::new(&args[2]));}
    if args.len()==4 && args[1]=="audit" {return admission::audit(Path::new(&args[2]),&input(&args[3])?);}
    if ![9,11,14].contains(&args.len()) {return Err("strict usage: coordinator INPUT CHUNK WORKER NEW_RUN_DIR SCENARIO TIMEOUT_MS 1 [TASK_TTL_MS 0 [VERIFY_UNITS STORAGE_BYTES LOG_BYTES]] REGISTRY | init-registry REGISTRY | audit REGISTRY INPUT; legacy execution disabled".into());}
    let registry=PathBuf::from(args.pop().unwrap());
    let directory=PathBuf::from(&args[4]);
    let admission;
    let mut s={
        let values=input(&args[1])?; let chunk=chunk_size(&args[2])?;
        let timeout_ms=chunk_size(&args[6])?; let maximum=chunk_size(&args[7])?;
        if maximum!=1 {return Err("strict policy requires MAX_ATTEMPTS=1".into());}
        validate_config(chunk,timeout_ms,maximum,&args[5])?;
        let worker=fs::canonicalize(&args[3]).map_err(|e|e.to_string())?;
        let count=values.len().div_ceil(chunk);
        let ttl=if args.len()>=10 {args[8].parse::<u64>().map_err(|_|"invalid task TTL")?} else {300_000};
        let recovery_limit=if args.len()>=10 {args[9].parse::<u64>().map_err(|_|"invalid recovery limit")?} else {0};
        if recovery_limit!=0 {return Err("strict policy requires MAX_RECOVERIES=0".into());}
        if !(50..=86_400_000).contains(&ttl) || recovery_limit>100 {return Err("task limits out of range".into());}
        let verify_limit=if args.len()==13 {args[10].parse::<u64>().map_err(|_|"invalid verification budget")?} else {10_000_000};
        let storage_limit=if args.len()==13 {args[11].parse::<u64>().map_err(|_|"invalid storage budget")?} else {67_108_864};
        let log_limit=if args.len()==13 {args[12].parse::<u64>().map_err(|_|"invalid log budget")?} else {1_048_576};
        if verify_limit>100_000_000 || !(4096..=268_435_456).contains(&storage_limit) || log_limit>16_777_216 {return Err("resource limits out of range".into());}
        let state=State {verify_used:0,verify_limit,storage_limit,log_limit,
            task_id:fs::read_to_string("/proc/sys/kernel/random/uuid").map_err(|e|e.to_string())?.trim().into(),chunk,timeout_ms,maximum,scenario:args[5].clone(),phase:"RUN".into(),
            boot:boot_id()?,deadline_ms:uptime_ms()?.checked_add(ttl).ok_or("deadline overflow")?,
            recoveries:0,recovery_limit,reason:"NONE".into(),
            worker_hash:hash(&fs::read(&worker).map_err(|e|e.to_string())?)?,worker,values,attempts:vec![0;count],accepted:vec![None;count]};
        configure_limits(&state)?;
        if directory.try_exists().map_err(|e|e.to_string())? {return Err("new run directory required".into());}
        admission=admission::Admission::reserve(&registry,&state)?;
        fs::create_dir(&directory).map_err(|e|format!("qualification consumed, run creation failed: {e}"))?;
        atomic(&directory,"contract.txt",contract(&state)?.as_bytes())?;
        atomic(&directory,"input.txt",snapshot(&state.values).as_bytes())?;
        save(&directory,&state)?; state
    };
    let lock=OpenOptions::new().read(true).write(true).create_new(true).custom_flags(0x20000).open(directory.join("run.lock")).map_err(|e|e.to_string())?;
    lock.try_lock().map_err(|e|format!("run is locked: {e}"))?;
    checkpoint(&directory,"locked")?;
    configure_limits(&s)?;
    checkpoint(&directory,"saved")?;
    if s.phase=="FAILED" || s.phase=="EXPIRED" {
        return Err(format!("terminal {}: {}",s.phase,s.reason));
    }
    if s.boot!=boot_id()? {return Err("host reboot detected: automatic recovery unsupported".into());}
    let outcome=(|| -> Result<(),String> {
    let mut log=OpenOptions::new().create(true).append(true).custom_flags(0x20000).open(directory.join("events.tsv")).map_err(|e|e.to_string())?;
    // results.txt is valid only if every block is durably accepted and its bytes match.
    if directory.join("results.txt").exists() || s.phase=="DONE" {
        let rows=s.accepted.iter().cloned().collect::<Option<Vec<_>>>().ok_or("published result with incomplete state")?.join("\n")+"\n";
        if read(directory.join("results.txt").to_str().ok_or("non-UTF8 path")?,12_000_000)?!=rows { return Err("published result mismatch".into()); }
        verify(&s.values,s.chunk,&rows)?;
        if s.phase!="DONE" { s.phase="DONE".into(); save(&directory,&s)?; event(&mut log,"COMPLETE_RECOVERED",0,0,"existing publication verified")?; }
        println!("{}",summary(&s.values,s.chunk)); return Ok(());
    }
    check_deadline(&directory,&mut s)?;
    let mut queue=VecDeque::new();
    for id in 0..s.attempts.len() {
        if s.accepted[id].is_none() {
            if s.attempts[id]>=s.maximum { return terminal(&directory,&mut s,"FAILED","ATTEMPTS"); }
            queue.push_back(id);
        }
    }
    let mut jobs:Vec<Job>=Vec::new(); let timeout=Duration::from_millis(s.timeout_ms as u64);
    while !queue.is_empty() || !jobs.is_empty() {
        check_deadline(&directory,&mut s)?;
        while jobs.len()<2 && !queue.is_empty() {
            check_deadline(&directory,&mut s)?;
            let id=queue.pop_front().unwrap(); s.attempts[id]+=1; let attempt=s.attempts[id];
            save(&directory,&s)?;
            if id==0 { checkpoint(&directory,"reserved")?; }
            let mode=if id==0 && (attempt==1 || s.scenario=="always-wrong") { if s.scenario=="always-wrong" {"wrong"} else {&s.scenario} } else {"normal"};
            let output=directory.join(format!("block-{id}-attempt-{attempt}.txt"));
            storage_guard(&directory,1024)?;
            let stdout=output_file(&output)?;
            let stderr=output_file(&directory.join(format!("block-{id}-attempt-{attempt}.stderr")))?;
            let mut command=Command::new(&s.worker);
            command.args([directory.join("input.txt").to_str().ok_or("non-UTF8 path")?,&s.chunk.to_string(),&id.to_string(),&attempt.to_string(),mode,&(s.timeout_ms*2).to_string(),&s.task_id])
                // The same flock open-file description remains alive in every worker until exit.
                .stdin(Stdio::from(lock.try_clone().map_err(|e|e.to_string())?)).stdout(stdout).stderr(stderr);
            let parent=process::id() as i32;
            unsafe { command.pre_exec(move || {
                // Set parent-death SIGKILL and close the fork/prctl race using the expected parent.
                // Linux RLIMIT_FSIZE bounds each direct worker output/error file.
                if setrlimit(1,&RLimit {current:256,maximum:256})!=0 {return Err(std::io::Error::last_os_error());}
                if prctl(1,9,0,0,0)!=0 { return Err(std::io::Error::last_os_error()); }
                if getppid()!=parent { return Err(std::io::Error::other("coordinator already exited")); }
                Ok(())
            }); }
            let child=command.spawn().map_err(|e|e.to_string())?;
            let job=Job {child,id,attempt,start:Instant::now(),expired:false,output};
            event(&mut log,"START",id,attempt,&format!("pid={} mode={mode}",job.child.id()))?;
            jobs.push(job);
        }
        if jobs.len()==2 { checkpoint(&directory,"running")?; }
        let mut index=0;
        while index<jobs.len() {
            let job=&mut jobs[index]; let status=job.child.try_wait().map_err(|e|e.to_string())?;
            if !job.expired && job.start.elapsed()>=timeout {
                job.expired=true;
                // Persisted reservation already makes this attempt invalid after any restart.
                event(&mut log,"TIMEOUT",job.id,job.attempt,"attempt invalidated")?;
                if job.id==0 { checkpoint(&directory,"timeout")?; }
                if retry(&mut queue,job.id,job.attempt,s.maximum).is_err() {
                    return terminal(&directory,&mut s,"FAILED","ATTEMPTS");
                }
            }
            if let Some(status)=status {
                if job.expired || job.attempt!=s.attempts[job.id] || s.accepted[job.id].is_some() {
                    event(&mut log,"STALE",job.id,job.attempt,"ignored")?;
                } else {
                    if job.id==0 { checkpoint(&directory,"output")?; }
                    let units=(s.values.len()-job.id*s.chunk).min(s.chunk) as u64;
                    charge_verification(&directory,&mut s,units)?;
                    let content=read(job.output.to_str().ok_or("non-UTF8 path")?,256);
                    let parsed=content.as_ref().ok().and_then(|text| if text.lines().count()==1 {text.strip_prefix(&format!("{} ",s.task_id)).and_then(|row|fields(row).ok())} else {None});
                    let correct=status.success() && parsed.as_ref().is_some_and(|f| f.len()==7 && f[0]==job.attempt as i64 && f[1..]==expected(&s.values,s.chunk,job.id));
                    if correct {
                        s.accepted[job.id]=Some(parsed.unwrap()[1..].iter().map(i64::to_string).collect::<Vec<_>>().join(" "));
                        save(&directory,&s)?;
                        event(&mut log,"ACCEPT_BLOCK",job.id,job.attempt,"verified")?;
                        if job.id==0 { checkpoint(&directory,"accepted")?; }
                    } else {
                        event(&mut log,"REJECT_BLOCK",job.id,job.attempt,"exit, format, attempt, or statistics invalid")?;
                        if retry(&mut queue,job.id,job.attempt,s.maximum).is_err() {
                    return terminal(&directory,&mut s,"FAILED","ATTEMPTS");
                }
                    }
                }
                jobs.remove(index);
            } else if job.expired && job.start.elapsed()>=timeout*3 {
                event(&mut log,"KILL",job.id,job.attempt,"expired process cleanup")?; jobs.remove(index);
            } else {index+=1;}
        }
        if !jobs.is_empty() {thread::sleep(Duration::from_millis(5));}
    }
    let rows=s.accepted.iter().cloned().collect::<Option<Vec<_>>>().ok_or("incomplete task")?.join("\n")+"\n";
    let units=s.values.len() as u64; charge_verification(&directory,&mut s,units)?;
    verify(&s.values,s.chunk,&rows)?;
    atomic(&directory,"results.tmp",rows.as_bytes())?; checkpoint(&directory,"temp")?;
    // Recheck on-disk inputs/results immediately before publication. This is not
    // protection against an adversary continually rewriting files as this user.
    if read(directory.join("input.txt").to_str().ok_or("non-UTF8 path")?,2_000_000)?!=snapshot(&s.values) {
        return Err("input snapshot changed before publication".into());
    }
    if read(directory.join("results.tmp").to_str().ok_or("non-UTF8 path")?,12_000_000)?!=rows {
        return Err("temporary result changed before publication".into());
    }
    check_deadline(&directory,&mut s)?;
    io_fault("results.txt","publish")?;
    // link is atomic and fails if the destination already exists (no overwrite).
    storage_guard(&directory,rows.len() as u64)?;
    fs::hard_link(directory.join("results.tmp"),directory.join("results.txt")).map_err(|e|format!("publication failed: {e}"))?;
    fs::remove_file(directory.join("results.tmp")).map_err(|e|e.to_string())?;
    io_fault("results.txt","dir_sync")?;sync_directory(&directory)?;
    checkpoint(&directory,"published")?;
    s.phase="DONE".into();save(&directory,&s)?;
    checkpoint(&directory,"terminal-saved")?;
    event(&mut log,"COMPLETE",0,0,"all blocks verified")?;
    admission.accept(&s,&rows)?;
    println!("{}",summary(&s.values,s.chunk)); Ok(())
    })();
    if s.phase=="RUN" {
        if let Err(ref reason)=outcome {
            if let Some(code)=reason.strip_prefix("quota:") {return terminal(&directory,&mut s,"FAILED",code);}
        }
    }
    outcome
}
fn main() { if let Err(e)=run() { eprintln!("REJECT: {e}"); process::exit(1); } }
