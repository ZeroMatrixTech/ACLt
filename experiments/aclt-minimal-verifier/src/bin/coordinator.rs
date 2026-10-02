use aclt_minimal_verifier::{chunk_size, expected, fields, input, read, summary, verify};
use std::{collections::VecDeque, env, fs::{self, File}, io::Write, path::PathBuf,
    process::{self, Child, Command, Stdio}, thread, time::{Duration, Instant}};

struct Job { child: Child, id: usize, attempt: usize, start: Instant, expired: bool, output: PathBuf }
impl Drop for Job {
    fn drop(&mut self) { let _ = self.child.kill(); let _ = self.child.wait(); }
}
fn event(log: &mut File, kind: &str, id: usize, attempt: usize, detail: &str) -> Result<(), String> {
    writeln!(log, "{kind}\t{id}\t{attempt}\t{detail}").map_err(|e| e.to_string())?;
    log.flush().map_err(|e| e.to_string())
}
fn retry(queue: &mut VecDeque<usize>, id: usize, attempt: usize, maximum: usize) -> Result<(), String> {
    if attempt >= maximum { return Err(format!("block {id}: attempt budget exhausted ({maximum})")); }
    queue.push_back(id); Ok(())
}
fn run() -> Result<(), String> {
    let args: Vec<_> = env::args().collect();
    if args.len() != 8 { return Err("usage: coordinator INPUT CHUNK WORKER NEW_RUN_DIR SCENARIO TIMEOUT_MS MAX_ATTEMPTS".into()); }
    let values = input(&args[1])?;
    let chunk = chunk_size(&args[2])?;
    let worker = fs::canonicalize(&args[3]).map_err(|e| e.to_string())?;
    let directory = PathBuf::from(&args[4]);
    let scenario = args[5].as_str();
    if !["normal", "slow", "wrong", "crash", "hang", "duplicate", "malformed", "wrong-attempt", "always-wrong"].contains(&scenario) {
        return Err("unknown scenario".into());
    }
    let timeout_ms = chunk_size(&args[6])?;
    if !(50..=10000).contains(&timeout_ms) { return Err("timeout must be 50..10000 ms".into()); }
    let maximum = chunk_size(&args[7])?;
    if maximum > 5 { return Err("max attempts must be 1..5".into()); }
    // Refuse to overwrite or resume a previous run, including a previously successful run.
    fs::create_dir(&directory).map_err(|e| format!("new run directory required: {e}"))?;
    let snapshot = directory.join("input.txt");
    fs::write(&snapshot, values.iter().map(i64::to_string).collect::<Vec<_>>().join(" ")).map_err(|e| e.to_string())?;
    fs::write(directory.join("config.txt"), format!("chunk={chunk}\nworkers=2\ntimeout_ms={timeout_ms}\nmax_attempts={maximum}\nscenario={scenario}\n")).map_err(|e| e.to_string())?;
    let mut log = File::create(directory.join("events.tsv")).map_err(|e| e.to_string())?;
    let count = values.len().div_ceil(chunk);
    let mut queue: VecDeque<_> = (0..count).collect();
    let mut attempts = vec![0; count];
    let mut accepted: Vec<Option<String>> = vec![None; count];
    let mut jobs: Vec<Job> = Vec::new();
    let timeout = Duration::from_millis(timeout_ms as u64);
    while !queue.is_empty() || !jobs.is_empty() {
        // Two OS processes maximum, including expired attempts retained for the late-result test.
        while jobs.len() < 2 && !queue.is_empty() {
            let id = queue.pop_front().unwrap();
            attempts[id] += 1;
            let attempt = attempts[id];
            let mode = if id == 0 && (attempt == 1 || scenario == "always-wrong") {
                if scenario == "always-wrong" { "wrong" } else { scenario }
            } else { "normal" };
            let output = directory.join(format!("block-{id}-attempt-{attempt}.txt"));
            let stdout = File::create(&output).map_err(|e| e.to_string())?;
            let stderr = File::create(directory.join(format!("block-{id}-attempt-{attempt}.stderr"))).map_err(|e| e.to_string())?;
            let child = Command::new(&worker).args([snapshot.to_str().ok_or("non-UTF8 path")?, &chunk.to_string(),
                &id.to_string(), &attempt.to_string(), mode, &(timeout_ms * 2).to_string()])
                .stdin(Stdio::null()).stdout(stdout).stderr(stderr).spawn().map_err(|e| e.to_string())?;
            let job = Job { child, id, attempt, start: Instant::now(), expired: false, output };
            event(&mut log, "START", id, attempt, &format!("pid={} mode={mode}", job.child.id()))?;
            jobs.push(job);
        }
        let mut index = 0;
        while index < jobs.len() {
            let job = &mut jobs[index];
            let status = job.child.try_wait().map_err(|e| e.to_string())?;
            // Deadline is checked before result acceptance, even if exit was observed in this poll.
            if !job.expired && job.start.elapsed() >= timeout {
                job.expired = true;
                event(&mut log, "TIMEOUT", job.id, job.attempt, "attempt invalidated")?;
                retry(&mut queue, job.id, job.attempt, maximum)?;
            }
            if let Some(status) = status {
                if job.expired || job.attempt != attempts[job.id] || accepted[job.id].is_some() {
                    event(&mut log, "STALE", job.id, job.attempt, "ignored")?;
                } else {
                    let content = read(job.output.to_str().ok_or("non-UTF8 path")?, 256);
                    let parsed = content.as_ref().ok().and_then(|s| {
                        if s.lines().count() != 1 { return None; }
                        fields(s).ok()
                    });
                    let correct = status.success() && parsed.as_ref().is_some_and(|f|
                        f.len() == 7 && f[0] == job.attempt as i64 && f[1..] == expected(&values, chunk, job.id));
                    if correct {
                        let row = parsed.unwrap()[1..].iter().map(i64::to_string).collect::<Vec<_>>().join(" ");
                        accepted[job.id] = Some(row);
                        event(&mut log, "ACCEPT_BLOCK", job.id, job.attempt, "verified")?;
                    } else {
                        event(&mut log, "REJECT_BLOCK", job.id, job.attempt, "exit, format, attempt, or statistics invalid")?;
                        retry(&mut queue, job.id, job.attempt, maximum)?;
                    }
                }
                jobs.remove(index);
            } else if job.expired && job.start.elapsed() >= timeout * 3 {
                event(&mut log, "KILL", job.id, job.attempt, "expired process cleanup")?;
                jobs.remove(index); // Drop kills and waits; no process slot is reused before cleanup.
            } else { index += 1; }
        }
        if !jobs.is_empty() { thread::sleep(Duration::from_millis(5)); }
    }
    let rows = accepted.into_iter().collect::<Option<Vec<_>>>().ok_or("incomplete task")?.join("\n") + "\n";
    verify(&values, chunk, &rows)?;
    fs::write(directory.join("results.tmp"), &rows).map_err(|e| e.to_string())?;
    fs::rename(directory.join("results.tmp"), directory.join("results.txt")).map_err(|e| e.to_string())?;
    event(&mut log, "COMPLETE", 0, 0, "all blocks verified")?;
    println!("{}", summary(&values, chunk));
    Ok(())
}
fn main() {
    if let Err(e) = run() { eprintln!("REJECT: {e}"); process::exit(1); }
}
