// Local trusted-operator prototype. Not a network identity or Sybil defence.
use super::*;

pub struct Admission { root: PathBuf, unit: String, claim: String, reservation: String, _lock: File }
fn deployment(root: &Path) -> Result<(),String> {
    // Production has one operator-selected namespace, not a caller-selected identity.
    // The feature is only for independently isolated regression fixtures.
    #[cfg(not(feature="admission-test-registry"))]
    if root!=Path::new(option_env!("ACLT_REGISTRY_ROOT").unwrap_or("/var/lib/aclt/local-unit")) {
        return Err("registry differs from the fixed deployment root".into());
    }
    let _=root;
    Ok(())
}
fn regular(path: &Path) -> Result<(), String> {
    if !fs::symlink_metadata(path).map_err(|e|e.to_string())?.is_file() { return Err("registry file is not regular".into()); }
    Ok(())
}
fn root_unit(root: &Path) -> Result<String,String> {
    deployment(root)?;
    if !root.is_absolute() || !fs::symlink_metadata(root).map_err(|e|format!("registry unavailable: {e}"))?.is_dir()
        || fs::canonicalize(root).map_err(|e|e.to_string())? != root { return Err("absolute canonical registry directory required".into()); }
    regular(&root.join("unit.txt"))?;
    let unit=read(root.join("unit.txt").to_str().ok_or("non-UTF8 registry")?,256)?;
    let id=unit.strip_prefix("ACLT-LOCAL-UNIT-1\n").and_then(|s|s.strip_suffix('\n')).ok_or("invalid registry identity")?;
    if id.len()!=36 || !id.bytes().all(|b|b.is_ascii_hexdigit() || b==b'-') { return Err("invalid registry identity".into()); }
    Ok(id.into())
}
fn create(path: &Path) -> Result<File,String> {
    OpenOptions::new().write(true).create_new(true).custom_flags(0x20000).open(path).map_err(|e|e.to_string())
}
pub fn init(root: &Path) -> Result<(),String> {
    deployment(root)?;
    if !root.is_absolute() { return Err("absolute registry path required".into()); }
    fs::create_dir(root).map_err(|e|format!("new registry required; never reset an existing one: {e}"))?;
    let id=fs::read_to_string("/proc/sys/kernel/random/uuid").map_err(|e|e.to_string())?;
    let mut unit=create(&root.join("unit.txt"))?;
    unit.write_all(format!("ACLT-LOCAL-UNIT-1\n{}\n",id.trim()).as_bytes()).map_err(|e|e.to_string())?;
    unit.sync_all().map_err(|e|e.to_string())?;
    create(&root.join("registry.lock"))?.sync_all().map_err(|e|e.to_string())?;
    sync_directory(root)?;sync_directory(root.parent().ok_or("registry parent required")?)?;
    println!("initialized local unit {}",id.trim()); Ok(())
}
fn claim_id(values: &[i64]) -> Result<String,String> {
    // Ordered signed decimal integers, single spaces, no trailing newline.
    // Chunk, run UUID, paths, boot and resource budgets cannot create eligibility.
    hash(format!("ACLT-LOCAL-CLAIM-1\nstats-int-v1\n{}",snapshot(values)).as_bytes())
}
// A separate filesystem can carry test signals, without syncing the data directory.
#[cfg(not(feature="test-faults"))]
fn pause(_root: &Path, _name: &str) -> Result<(),String> { Ok(()) }
#[cfg(feature="test-faults")]
fn pause(root: &Path, name: &str) -> Result<(),String> {
    if env::var("ACLT_TEST_PAUSE").ok().as_deref()!=Some(name) {return Ok(());}
    let signals=env::var("ACLT_TEST_SIGNAL_DIR").map(PathBuf::from).unwrap_or_else(|_|root.to_path_buf());
    checkpoint(&signals,name)
}
impl Admission {
    pub fn reserve(root: &Path,s: &State) -> Result<Self,String> {
        let unit=root_unit(root)?;
        regular(&root.join("registry.lock"))?;
        let lock=OpenOptions::new().read(true).write(true).custom_flags(0x20000).open(root.join("registry.lock")).map_err(|e|e.to_string())?;
        lock.try_lock().map_err(|e|format!("local unit busy: {e}"))?;
        let claim=claim_id(&s.values)?;
        for suffix in ["receipt","receipt.pending"] {
            match fs::symlink_metadata(root.join(format!("{claim}.{suffix}"))) {
                Ok(_) => return Err("claim unavailable: existing acceptance artifact".into()),
                Err(e) if e.kind()==std::io::ErrorKind::NotFound => (),
                Err(e) => return Err(e.to_string()),
            }
        }
        let path=root.join(format!("{claim}.claim"));
        // Any existing object, including a truncated reservation, consumes eligibility.
        let mut f=create(&path).map_err(|e|format!("claim unavailable; duplicate or storage failure: {e}"))?;
        pause(root,"claim-created")?;
        let body=format!("{unit}\n{claim}\n{}\n{}\n{}\n{}\n",s.task_id,s.boot,s.chunk,s.worker_hash);
        let reservation=format!("ACLT-LOCAL-RESERVATION-1\n{}\n{body}",hash(body.as_bytes())?);
        io_fault("claim","write")?;
        let middle=reservation.len()/2;
        f.write_all(&reservation.as_bytes()[..middle]).map_err(|e|e.to_string())?;
        pause(root,"claim-partial")?;
        f.write_all(&reservation.as_bytes()[middle..]).map_err(|e|e.to_string())?;
        io_fault("claim","file_sync")?;f.sync_all().map_err(|e|e.to_string())?;
        pause(root,"claim-synced")?;
        io_fault("claim","dir_sync")?;sync_directory(root)?;
        pause(root,"claim-reserved")?;
        Ok(Self {root:root.into(),unit,claim,reservation,_lock:lock})
    }
    pub fn accept(&self,s: &State,rows: &str) -> Result<(),String> {
        if s.phase!="DONE" {return Err("only a complete verified task may be accepted".into());}
        verify(&s.values,s.chunk,rows)?;
        let body=format!("{}\n{}\n{}\n{}\n{}\n{rows}",self.claim,self.unit,hash(self.reservation.as_bytes())?,s.chunk,hash(rows.as_bytes())?);
        let data=format!("ACLT-LOCAL-RECEIPT-1\n{}\n{body}",hash(body.as_bytes())?);
        let tmp=self.root.join(format!("{}.receipt.pending",self.claim));
        let mut f=create(&tmp)?;
        pause(&self.root,"receipt-created")?;
        io_fault("receipt","write")?;
        let middle=data.len()/2;
        f.write_all(&data.as_bytes()[..middle]).map_err(|e|e.to_string())?;
        pause(&self.root,"receipt-partial")?;
        f.write_all(&data.as_bytes()[middle..]).map_err(|e|e.to_string())?;
        io_fault("receipt","file_sync")?;f.sync_all().map_err(|e|e.to_string())?;
        pause(&self.root,"receipt-synced")?;
        io_fault("receipt","publish")?;
        fs::hard_link(&tmp,self.root.join(format!("{}.receipt",self.claim))).map_err(|e|format!("receipt publication failed: {e}"))?;
        pause(&self.root,"receipt-published")?;
        io_fault("receipt","dir_sync")?;sync_directory(&self.root)?;
        // Pending is retained as an immutable provenance copy; never overwrite it.
        pause(&self.root,"receipt-committed")?;
        Ok(())
    }
}
pub fn audit(root: &Path,values: &[i64]) -> Result<(),String> {
    let unit=root_unit(root)?;
    regular(&root.join("registry.lock"))?;
    let lock=OpenOptions::new().read(true).custom_flags(0x20000).open(root.join("registry.lock")).map_err(|e|e.to_string())?;
    lock.try_lock_shared().map_err(|e|format!("local unit busy: {e}"))?;
    let claim=claim_id(values)?;
    let path=root.join(format!("{claim}.receipt"));regular(&path)?;
    let raw=read(path.to_str().ok_or("non-UTF8 registry")?,32_000_000)?;
    let mut parts=raw.splitn(3,'\n');
    if parts.next()!=Some("ACLT-LOCAL-RECEIPT-1") {return Err("receipt version invalid".into());}
    let digest=parts.next().ok_or("receipt truncated")?;let body=parts.next().ok_or("receipt truncated")?;
    if hash(body.as_bytes())?!=digest {return Err("receipt checksum mismatch".into());}
    let mut fields=body.splitn(6,'\n');
    if fields.next()!=Some(&claim) || fields.next()!=Some(&unit) {return Err("receipt identity mismatch".into());}
    let reservation_hash=fields.next().ok_or("receipt truncated")?;
    let record=self::read_record(root,&claim)?;
    if hash(record.as_bytes())?!=reservation_hash {return Err("receipt reservation mismatch".into());}
    let mut rp=record.splitn(3,'\n');
    if rp.next()!=Some("ACLT-LOCAL-RESERVATION-1") {return Err("reservation version invalid".into());}
    let rd=rp.next().ok_or("reservation truncated")?;let rb=rp.next().ok_or("reservation truncated")?;
    if hash(rb.as_bytes())?!=rd {return Err("reservation checksum mismatch".into());}
    let rfields=rb.lines().collect::<Vec<_>>();
    if rfields.len()!=6 || rfields[0]!=unit || rfields[1]!=claim {return Err("reservation identity mismatch".into());}
    let chunk=chunk_size(fields.next().ok_or("receipt truncated")?)?;
    if chunk.to_string()!=rfields[4] {return Err("receipt chunk mismatch".into());}
    let result_hash=fields.next().ok_or("receipt truncated")?;let rows=fields.next().ok_or("receipt truncated")?;
    if hash(rows.as_bytes())?!=result_hash {return Err("receipt result mismatch".into());}
    // Read-only mathematical audit; no worker spawn, qualification or vote increment.
    verify(values,chunk,rows)?;
    println!("ACCEPTED {claim} local_contributions=1 result_sha256={result_hash}");Ok(())
}
fn read_record(root: &Path,claim: &str) -> Result<String,String> {
    let path=root.join(format!("{claim}.claim"));regular(&path)?;
    read(path.to_str().ok_or("non-UTF8 registry")?,4096)
}
