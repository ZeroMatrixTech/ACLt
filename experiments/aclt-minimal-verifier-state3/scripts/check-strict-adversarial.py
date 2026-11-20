"""DeepSeek proposed adversarial cases; coordinator repaired fixtures and formats.

Original worker drafts are preserved in the round's DeepSeek responses. They
were not executable/valid evidence and are not claimed as accepted worker code.
"""

if not __debug__:
    raise SystemExit('assert-based validation requires Python without -O/PYTHONOPTIMIZE')

import hashlib,json,os,pathlib,subprocess,tempfile,traceback
C=os.environ['ACLT_COORDINATOR'];W=os.environ['ACLT_WORKER'];REPORT=pathlib.Path(os.environ['ACLT_STRICT_ADVERSARIAL_REPORT'])
TEXT='3 -1 8 0 -7 12 5 2 -3 9';KEY=hashlib.sha256(('ACLT-LOCAL-CLAIM-1\nstats-int-v1\n'+TEXT).encode()).hexdigest()
cases=[]
def run(*args):return subprocess.run(list(map(str,[C,*args])),capture_output=True,text=True,timeout=30)
def sha(data):return hashlib.sha256(data).hexdigest()
def fixture(base,name):
 d=base/name;d.mkdir();reg=d/'registry';inp=d/'input';inp.write_text(TEXT+'\n')
 p=run('init-registry',reg);assert p.returncode==0,p.stderr
 return reg,inp,d/'run'
def execute(reg,inp,d):return run(inp,4,W,d,'normal',1000,1,reg)
def check(name,condition,detail=''):
 cases.append({'name':name,'passed':bool(condition),'detail':detail});assert condition,(name,detail)
def rewrite(path,body):
 magic=path.read_bytes().split(b'\n',1)[0]
 path.write_bytes(magic+b'\n'+sha(body).encode()+b'\n'+body)
try:
 with tempfile.TemporaryDirectory(prefix='strict-adversarial-') as tmp:
  base=pathlib.Path(tmp)
  reg,inp,d=fixture(base,'dangling');claim=reg/(KEY+'.claim');claim.symlink_to(base/'missing')
  p=execute(reg,inp,d)
  check('dangling-claim-reject-before-worker',p.returncode!=0 and not d.exists() and claim.is_symlink(),p.stderr)
  for suffix in ['receipt','receipt.pending']:
   reg,inp,d=fixture(base,suffix);path=reg/(KEY+'.'+suffix);path.write_bytes(b'PREEXISTING-CORRUPT');before=path.read_bytes()
   p=execute(reg,inp,d)
   check('never-overwrite-'+suffix,p.returncode!=0 and path.read_bytes()==before and not d.exists(),p.stderr)
   if suffix=='receipt':check('corrupt-preexisting-not-accepted',run('audit',reg,inp).returncode!=0)
   else:check('pending-not-accepted',not (reg/(KEY+'.receipt')).exists())
  reg,inp,d=fixture(base,'math');p=execute(reg,inp,d);check('mutation-fixture-valid',p.returncode==0,p.stderr)
  rp=reg/(KEY+'.receipt');original=rp.read_bytes();body=original.split(b'\n',2)[2];fields=body.split(b'\n',5)
  assert fields[5].startswith(b'0 0 4 10 -1 8\n')
  fields[5]=fields[5].replace(b'0 0 4 10 -1 8\n',b'0 0 4 11 -1 8\n',1)
  fields[4]=sha(fields[5]).encode();rewrite(rp,b'\n'.join(fields));before=rp.read_bytes();p=run('audit',reg,inp)
  check('math-reject-with-correct-checksums',p.returncode!=0 and 'checksum' not in p.stderr.lower() and rp.read_bytes()==before,p.stderr)
  rp.write_bytes(original)
  # Copy a valid receipt and reservation to a new unit: checksums all remain valid.
  reg2,inp2,d2=fixture(base,'cross-unit');(reg2/(KEY+'.receipt')).write_bytes(original);(reg2/(KEY+'.claim')).write_bytes((reg/(KEY+'.claim')).read_bytes())
  p=run('audit',reg2,inp2);check('cross-unit-valid-bytes-rejected',p.returncode!=0 and 'identity' in p.stderr,p.stderr)
  # Re-checksum a false chunk binding; no checksum-only rejection is sufficient.
  fields=body.split(b'\n',5);fields[3]=b'2';rewrite(rp,b'\n'.join(fields));p=run('audit',reg,inp)
  check('rechecksummed-chunk-binding-rejected',p.returncode!=0 and 'chunk mismatch' in p.stderr,p.stderr)
  rp.write_bytes(original)
  # Re-checksum a reservation, but keep the original receipt binding.
  cp=reg/(KEY+'.claim');old=cp.read_bytes();cb=old.split(b'\n',2)[2].splitlines();cb[2]=b'00000000-0000-0000-0000-000000000000';rewrite(cp,b'\n'.join(cb)+b'\n');p=run('audit',reg,inp)
  check('reservation-sha-binding-DISABLED',p.returncode==0 and 'SHA_CONSISTENCY=DISABLED' in p.stdout,p.stderr)
 result={'passed':True,'cases':cases,'provenance':'DeepSeek case proposals and draft; coordinator repaired actual CLI, fixtures, receipt format and assertions'}
except BaseException:
 result={'passed':False,'cases':cases,'error':traceback.format_exc()}
 raise
finally:
 REPORT.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'passed':True,'cases':len(cases)}))
