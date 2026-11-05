#!/usr/bin/env python3
"""Reproducible exact arithmetic, input mutation, sanitizers and narrow reducers."""

if not __debug__:
    raise SystemExit('assert-based validation requires Python without -O/PYTHONOPTIMIZE')

import itertools,json,os,pathlib,random,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1];WORKER=ROOT/'build/worker';SAN=ROOT/'build/worker-sanitized';VERIFY=ROOT/'target/debug/aclt-minimal-verifier'
records=[];seed=20261003;rng=random.Random(seed)
def call(args):return subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=15,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'})
def oracle(values,chunk):
 rows=[]
 for start in range(0,len(values),chunk):
  part=values[start:start+chunk];rows.append(f'{start//chunk} {start} {len(part)} {sum(part)} {min(part)} {max(part)}')
 return '\n'.join(rows)+'\n'
with tempfile.TemporaryDirectory(prefix='aclt-differential-') as tmp:
 d=pathlib.Path(tmp);source=d/'input';result=d/'result'
 datasets=[[0],[10**9]*100000,[-10**9]*100000,[-10**9,10**9]*50000]
 datasets += [[rng.randint(-10**9,10**9) for _ in range(rng.randint(1,250))] for _ in range(200)]
 for i,values in enumerate(datasets):
  chunk=[1,99999,100000,100000][i] if i<4 else rng.randint(1,len(values)+10)
  source.write_text((' \t\r\n'.join(map(str,values)))+'\n');expected=oracle(values,chunk)
  out=call([WORKER,source,chunk]);assert out.returncode==0 and out.stdout==expected,(i,out.stderr)
  result.write_text(out.stdout);v=call([VERIFY,source,chunk,result]);assert v.returncode==0,(i,v.stderr)
  # Independent memory/undefined-behavior instrumentation on boundaries and 16 seeds.
  if i<20:
   out=call([SAN,source,chunk]);assert out.returncode==0 and out.stdout==expected and not out.stderr,(i,out.stderr)
  # Every generated valid result also gets a changed sum and a missing row.
  rows=expected.splitlines();fields=rows[0].split();fields[3]=str(int(fields[3])+1)
  for bad in [' '.join(fields)+'\n'+'\n'.join(rows[1:])+('\n' if len(rows)>1 else ''),'\n'.join(rows[1:])]:
   result.write_text(bad);assert call([VERIFY,source,chunk,result]).returncode!=0,i
 records.append({'group':'seeded exact differential and mutated results','datasets':len(datasets),'mutations':len(datasets)*2,'sanitized_runs':20,'passed':True})
 for bad in ['','-0','+1','01','1.0','1000000001','-1000000001','١','１','1\u00a02','9223372036854775808','1\x002']:
  source.write_text(bad);result.write_text('')
  assert call([WORKER,source,1]).returncode!=0
  assert call([VERIFY,source,1,result]).returncode!=0
 records.append({'group':'invalid canonical input','cases':12,'passed':True})
 codes=['WINDOW_EXPIRED','OUT_OF_SCOPE','REVOKED'];count=0
 for n in range(4):
  for values in itertools.permutations(codes,n):
   expected=next((c for c in reversed(codes) if c in values),'VALID')+'\n'
   for exe in [ROOT/'build/cause-reducer-cpp',ROOT/'target/debug/cause-reducer']:
    out=call([exe,*values]);assert out.returncode==0 and out.stdout==expected,(values,out)
   count+=1
 for values in [[c,c] for c in codes]+[['UNKNOWN'],[''],['REVOKED','unknown']]:
  for exe in [ROOT/'build/cause-reducer-cpp',ROOT/'target/debug/cause-reducer']:assert call([exe,*values]).returncode!=0
 records.append({'group':'Rust/C++ narrow cause reducer','valid_permutations':count,'invalid_inputs':6,'passed':True})
(ROOT/'build/differential-tests.json').write_text(json.dumps({'seed':seed,'groups':records},indent=2)+'\n')
print('PASS: 204 exact datasets, 408 mutated results, 20 sanitizer runs, 12 malformed inputs, 22 Rust/C++ reducer vectors')
