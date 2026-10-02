use aclt_minimal_verifier::{chunk_size, expected, fields, input, read, summary, verify};
use std::{collections::VecDeque, env, fs::{self, File, OpenOptions}, io::Write,
    os::unix::{process::CommandExt, fs::OpenOptionsExt}, path::{Path, PathBuf}, process::{self, Child, Command, Stdio},
    thread, time::{Duration, Instant}, sync::atomic::{AtomicUsize, Ordering}};

// Linux-only lifecycle protection; no external Rust dependencies.
extern "C" { fn prctl(option: i32, ...) -> i32; fn getppid() -> i32; }
struct Job { child: Child, id: usize, attempt: usize, start: Instant, expired: bool, output: PathBuf }
impl Drop for Job { fn drop(&mut self) { let _ = self.child.kill(); let _ = self.child.wait(); } }
struct State {
    chunk: usize, timeout_ms: usize, maximum: usize, scenario: String, done: bool,
    worker: PathBuf, worker_hash: String, values: Vec<i64>, attempts: Vec<usize>, accepted: Vec<Option<String>>,
}
fn hex(bytes: &[u8]) -> String { bytes.iter().map(|x| format!("{x:02x}")).collect() }
fn unhex(s: &str) -> Result<String,String> {
    if s.len() % 2 != 0 || !s.is_ascii() { return Err("invalid path encoding".into()); }
    let bytes = (0..s.len()).step_by(2).map(|i| u8::from_str_radix(&s[i..i+2],16).map_err(|e|e.to_string())).collect::<Result<Vec<_>,_>>()?;
    String::from_utf8(bytes).map_err(|e|e.to_string())
}
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
        if s.done {"DONE"} else {"RUN"},hex(s.worker.to_str().ok_or("non-UTF8 path")?.as_bytes()),s.worker_hash,
        snapshot(&s.values),s.attempts.len());
    for id in 0..s.attempts.len() { text.push_str(&format!("{id} {} {}\n",s.attempts[id],s.accepted[id].as_deref().unwrap_or("PENDING"))); }
    text.push_str("END\n"); Ok(text)
}
// Fault hooks are opt-in and only used by the local failure-injection tests.
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
    atomic(directory,"state.txt",format!("ACLT-STATE-1\n{}\n{body}",hash(body.as_bytes())?).as_bytes())
}
fn validate_config(chunk: usize,timeout: usize,maximum: usize,scenario: &str) -> Result<(),String> {
    if !(1..=100000).contains(&chunk) || !(50..=10000).contains(&timeout) || !(1..=5).contains(&maximum) { return Err("configuration out of range".into()); }
    if !["normal","slow","wrong","crash","hang","duplicate","malformed","wrong-attempt","always-wrong"].contains(&scenario) { return Err("unknown scenario".into()); }
    Ok(())
}
fn load(directory: &Path) -> Result<State,String> {
    let raw=read(directory.join("state.txt").to_str().ok_or("non-UTF8 path")?,16_000_000)?;
    let mut parts=raw.splitn(3,'\n');
    if parts.next()!=Some("ACLT-STATE-1") { return Err("state version invalid".into()); }
    let digest=parts.next().ok_or("state truncated")?;
    let text=parts.next().ok_or("state truncated")?;
    if hash(text.as_bytes())?!=digest { return Err("state checksum mismatch".into()); }
    let lines=text.lines().collect::<Vec<_>>();
    if lines.len()<6 { return Err("state truncated".into()); }
    let config=lines[0].split(' ').collect::<Vec<_>>();
    if config.len()!=5 { return Err("state configuration invalid".into()); }
    let chunk=chunk_size(config[0])?; let timeout_ms=chunk_size(config[1])?; let maximum=chunk_size(config[2])?;
    validate_config(chunk,timeout_ms,maximum,config[3])?;
    if !["RUN","DONE"].contains(&config[4]) { return Err("state phase invalid".into()); }
    let worker=PathBuf::from(unhex(lines[1])?);
    let values=input(directory.join("input.txt").to_str().ok_or("non-UTF8 path")?)?;
    if read(directory.join("input.txt").to_str().unwrap(),2_000_000)?!=lines[3] || snapshot(&values)!=lines[3] { return Err("input snapshot mismatch".into()); }
    let count=values.len().div_ceil(chunk);
    if lines[4]!=count.to_string() || lines.len()!=count+6 || lines.last()!=Some(&"END") { return Err("state block count invalid".into()); }
    let mut attempts=Vec::new(); let mut accepted=Vec::new();
    for id in 0..count {
        let row=lines[5+id].splitn(3,' ').collect::<Vec<_>>();
        if row.len()!=3 || row[0]!=id.to_string() { return Err("state block order invalid".into()); }
        let attempt=aclt_minimal_verifier::number(row[1])?;
        if attempt<0 || attempt as usize>maximum { return Err("state attempts invalid".into()); }
        attempts.push(attempt as usize);
        if row[2]=="PENDING" { accepted.push(None); }
        else {
            if attempt==0 || fields(row[2])?!=expected(&values,chunk,id) { return Err("saved result invalid".into()); }
            accepted.push(Some(row[2].to_string()));
        }
    }
    let s=State {chunk,timeout_ms,maximum,scenario:config[3].into(),done:config[4]=="DONE",worker,worker_hash:lines[2].into(),values,attempts,accepted};
    if body(&s)?!=text { return Err("noncanonical state".into()); }
    if s.done && s.accepted.iter().any(Option::is_none) { return Err("incomplete DONE state".into()); }
    if hash(&fs::read(&s.worker).map_err(|e|e.to_string())?)?!=s.worker_hash { return Err("worker binary mismatch".into()); }
    Ok(s)
}
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
    io_fault("events.tsv","write")?;
    writeln!(log,"{kind}\t{id}\t{attempt}\t{detail}").map_err(|e|e.to_string())?;
    log.flush().map_err(|e|e.to_string())
}
fn retry(queue: &mut VecDeque<usize>,id: usize,attempt: usize,maximum: usize) -> Result<(),String> {
    if attempt>=maximum { return Err(format!("block {id}: attempt budget exhausted ({maximum})")); }
    queue.push_back(id); Ok(())
}
fn run() -> Result<(),String> {
    let args=env::args().collect::<Vec<_>>();
    let resume=args.len()==3 && args[1]=="resume";
    if !resume && args.len()!=8 { return Err("usage: coordinator INPUT CHUNK WORKER NEW_RUN_DIR SCENARIO TIMEOUT_MS MAX_ATTEMPTS | coordinator resume RUN_DIR".into()); }
    let directory=PathBuf::from(if resume {&args[2]} else {&args[4]});
    if !resume { fs::create_dir(&directory).map_err(|e|format!("new run directory required: {e}"))?; }
    let lock=OpenOptions::new().read(true).write(true).create(true).truncate(false).custom_flags(0x20000).open(directory.join("run.lock")).map_err(|e|e.to_string())?;
    lock.try_lock().map_err(|e|format!("run is locked by a coordinator or retiring workers: {e}"))?;
    checkpoint(&directory,"locked")?;
    let mut s=if resume { load(&directory)? } else {
        let values=input(&args[1])?; let chunk=chunk_size(&args[2])?;
        let timeout_ms=chunk_size(&args[6])?; let maximum=chunk_size(&args[7])?;
        validate_config(chunk,timeout_ms,maximum,&args[5])?;
        let worker=fs::canonicalize(&args[3]).map_err(|e|e.to_string())?;
        let count=values.len().div_ceil(chunk);
        let state=State {chunk,timeout_ms,maximum,scenario:args[5].clone(),done:false,
            worker_hash:hash(&fs::read(&worker).map_err(|e|e.to_string())?)?,worker,values,attempts:vec![0;count],accepted:vec![None;count]};
        atomic(&directory,"input.txt",snapshot(&state.values).as_bytes())?;
        save(&directory,&state)?; state
    };
    checkpoint(&directory,"saved")?;
    let mut log=OpenOptions::new().create(true).append(true).custom_flags(0x20000).open(directory.join("events.tsv")).map_err(|e|e.to_string())?;
    // results.txt is valid only if every block is durably accepted and its bytes match.
    if directory.join("results.txt").exists() || s.done {
        let rows=s.accepted.iter().cloned().collect::<Option<Vec<_>>>().ok_or("published result with incomplete state")?.join("\n")+"\n";
        if read(directory.join("results.txt").to_str().ok_or("non-UTF8 path")?,12_000_000)?!=rows { return Err("published result mismatch".into()); }
        verify(&s.values,s.chunk,&rows)?;
        if !s.done { s.done=true; save(&directory,&s)?; event(&mut log,"COMPLETE_RECOVERED",0,0,"existing publication verified")?; }
        println!("{}",summary(&s.values,s.chunk)); return Ok(());
    }
    if resume { event(&mut log,"RESUME",0,0,"unfinished old attempts invalidated; counts retained")?; }
    let mut queue=VecDeque::new();
    for id in 0..s.attempts.len() {
        if s.accepted[id].is_none() {
            if s.attempts[id]>=s.maximum { return Err(format!("block {id}: attempt budget exhausted ({})",s.maximum)); }
            queue.push_back(id);
        }
    }
    let mut jobs:Vec<Job>=Vec::new(); let timeout=Duration::from_millis(s.timeout_ms as u64);
    while !queue.is_empty() || !jobs.is_empty() {
        while jobs.len()<2 && !queue.is_empty() {
            let id=queue.pop_front().unwrap(); s.attempts[id]+=1; let attempt=s.attempts[id];
            save(&directory,&s)?;
            if id==0 { checkpoint(&directory,"reserved")?; }
            let mode=if id==0 && (attempt==1 || s.scenario=="always-wrong") { if s.scenario=="always-wrong" {"wrong"} else {&s.scenario} } else {"normal"};
            let output=directory.join(format!("block-{id}-attempt-{attempt}.txt"));
            let stdout=output_file(&output)?;
            let stderr=output_file(&directory.join(format!("block-{id}-attempt-{attempt}.stderr")))?;
            let mut command=Command::new(&s.worker);
            command.args([directory.join("input.txt").to_str().ok_or("non-UTF8 path")?,&s.chunk.to_string(),&id.to_string(),&attempt.to_string(),mode,&(s.timeout_ms*2).to_string()])
                // The same flock open-file description remains alive in every worker until exit.
                .stdin(Stdio::from(lock.try_clone().map_err(|e|e.to_string())?)).stdout(stdout).stderr(stderr);
            let parent=process::id() as i32;
            unsafe { command.pre_exec(move || {
                // Set parent-death SIGKILL and close the fork/prctl race using the expected parent.
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
                retry(&mut queue,job.id,job.attempt,s.maximum)?;
            }
            if let Some(status)=status {
                if job.expired || job.attempt!=s.attempts[job.id] || s.accepted[job.id].is_some() {
                    event(&mut log,"STALE",job.id,job.attempt,"ignored")?;
                } else {
                    if job.id==0 { checkpoint(&directory,"output")?; }
                    let content=read(job.output.to_str().ok_or("non-UTF8 path")?,256);
                    let parsed=content.as_ref().ok().and_then(|text| if text.lines().count()==1 {fields(text).ok()} else {None});
                    let correct=status.success() && parsed.as_ref().is_some_and(|f| f.len()==7 && f[0]==job.attempt as i64 && f[1..]==expected(&s.values,s.chunk,job.id));
                    if correct {
                        s.accepted[job.id]=Some(parsed.unwrap()[1..].iter().map(i64::to_string).collect::<Vec<_>>().join(" "));
                        save(&directory,&s)?;
                        event(&mut log,"ACCEPT_BLOCK",job.id,job.attempt,"verified")?;
                        if job.id==0 { checkpoint(&directory,"accepted")?; }
                    } else {
                        event(&mut log,"REJECT_BLOCK",job.id,job.attempt,"exit, format, attempt, or statistics invalid")?;
                        retry(&mut queue,job.id,job.attempt,s.maximum)?;
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
    io_fault("results.txt","publish")?;
    // link is atomic and fails if the destination already exists (no overwrite).
    fs::hard_link(directory.join("results.tmp"),directory.join("results.txt")).map_err(|e|format!("publication failed: {e}"))?;
    fs::remove_file(directory.join("results.tmp")).map_err(|e|e.to_string())?;
    io_fault("results.txt","dir_sync")?;sync_directory(&directory)?;
    checkpoint(&directory,"published")?;
    s.done=true;save(&directory,&s)?;
    event(&mut log,"COMPLETE",0,0,"all blocks verified")?;
    println!("{}",summary(&s.values,s.chunk)); Ok(())
}
fn main() { if let Err(e)=run() { eprintln!("REJECT: {e}"); process::exit(1); } }
