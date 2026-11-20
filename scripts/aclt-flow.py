#!/usr/bin/env python3
"""Local evidence-driven workflow. Python stdlib, Linux; no implicit protocol closure."""
import argparse, datetime, fcntl, glob, hashlib, json, os, pathlib, platform, re, signal, subprocess, sys, time, uuid

def stamp(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def atomic(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 temp=path.with_suffix(path.suffix+'.writing')
 with temp.open('w') as f:
  f.write(data);f.flush();os.fsync(f.fileno())
 os.replace(temp,path)
def dump(path,value):atomic(path,json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def read(path,default):return json.loads(path.read_text()) if path.exists() else default

def within(root,name):
 p=root/name
 if p.is_absolute() and p.resolve().is_relative_to(root):return p
 raise ValueError('path outside repository: '+str(name))
def expand(root,patterns):
 paths={}
 for pattern in patterns:
  if pathlib.Path(pattern).is_absolute() or '..' in pathlib.Path(pattern).parts:raise ValueError('unsafe glob')
  for name in glob.glob(str(root/pattern),recursive=True):
   p=pathlib.Path(name)
   if p.is_file() and '__pycache__' not in p.parts:
    within(root,str(p.relative_to(root)))
    paths[str(p.relative_to(root))]=hashlib.sha256(p.read_bytes()).hexdigest()
 return dict(sorted(paths.items()))
def environment(root):
 result={'platform':platform.platform(),'python':sys.version,'PATH':os.environ.get('PATH','')}
 selected={k:os.environ.get(k,'') for k in ['RUSTC','RUSTFLAGS','CARGO_ENCODED_RUSTFLAGS','CARGO_TARGET_DIR','LD_LIBRARY_PATH','LD_PRELOAD','PYTHONPATH','PYTHONHASHSEED','LANG','LC_ALL','TZ']}
 result['build_environment_sha256']=hashlib.sha256(json.dumps(selected,sort_keys=True).encode()).hexdigest()
 tools={'g++':['g++','--version'],'rustc':['rustc','--version'],'cargo':['cargo','--version']}
 local=root/'experiments/aclt-minimal-verifier-state3/.toolchain/usr'
 env=os.environ.copy()
 if local.exists():
  env['LD_LIBRARY_PATH']=str(local/'lib/x86_64-linux-gnu')+':'+env.get('LD_LIBRARY_PATH','')
  tools.update({name:[str(local/'lib/rust-1.93/bin'/name),'--version'] for name in ('rustc','cargo')})
 for name,cmd in tools.items():
  try:
   p=subprocess.run(cmd,cwd=root,env=env,text=True,capture_output=True,timeout=5)
   result[name]=(p.stdout+p.stderr).strip() if p.returncode==0 else 'UNAVAILABLE'
  except (OSError,subprocess.TimeoutExpired):result[name]='UNAVAILABLE'
 return result

def fingerprint(root,job,config,env):
 files=expand(root,job['inputs'])
 bound=[d for d in read(config,{}).get('decisions',[]) if d['id'] in job.get('requires_decisions',[])]
 payload={'decisions':bound,'files':files,'job':job,'workflow_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'environment':env}
 digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
 return digest,files

def coverage(root,config):
 declared=read(within(root,config['coverage']),{})
 source=within(root,config['rules'])
 if source.suffix=='.md' and source.exists():
  rules=[{'rule':m[0],'kind':m[1]} for m in re.findall(r'^\| (SV-[^ |]+) \|.*\| (?:\*\*)?([AB])(?:\*\*)? \|$',source.read_text(),re.M)]
 else:rules=read(source,{}).get('rules',[])
 implemented={i for rows in declared.get('implemented',{}).values() for i in rows}
 partial={i for rows in declared.get('partial',{}).values() for i in rows}
 return [{'id':r['rule'],'kind':r['kind'],'implementation':'DECLARED_IMPLEMENTED' if r['rule'] in implemented else 'PARTIAL' if r['rule'] in partial else 'NOT_IMPLEMENTED'} for r in rules]

def render(root,config,states):
 rules=coverage(root,config)
 a=[r for r in rules if r['kind']=='A']
 lines=['# ACLt 自动进度看板','',f'更新：{stamp()}','', '测试状态根据代码指纹、运行退出码和预期摘要自动更新。协议关闭仍需独立审阅。','', '| 工作 | 状态 | 证据 |','|---|---|---|']
 for job in config['jobs']:
  state=states.get(job['id'],{})
  path=state.get('log','')
  link=f'[运行日志]({path})' if path else '尚无运行'
  lines.append(f"| {job['title']} | {state.get('status','NOT_RUN')} | {link} |")
 lines += ['','## 自动采集的运行摘要','']
 for job in config['jobs']:
  for summary in states.get(job['id'],{}).get('summaries',[]):lines.append(f"- {job['title']}：{summary}")
 lines += ['','## 自动待办','']
 for job in config['jobs']:
  status=states.get(job['id'],{}).get('status','NOT_RUN')
  if status!='PASS':lines.append(f"- {job['title']}：{status}；运行 `python3 scripts/aclt-flow.py run`。")
 for item in config.get('decisions',[]):
  if item['status']!='DECIDED':lines.append(f"- 需要决定：{item['title']}（负责人：{item['owner']}；依据：{item['basis']}）。")
 if a:
  lines += ['',f"规范 Type A：{len(a)} 项；声明已实现 {sum(r['implementation']=='DECLARED_IMPLEMENTED' for r in a)}，部分实现 {sum(r['implementation']=='PARTIAL' for r in a)}，未实现 {sum(r['implementation']=='NOT_IMPLEMENTED' for r in a)}。",'','测试通过不会自动把任何规则改成完整实现，亦不会关闭 Gate。']
 else:lines += ['','覆盖登记缺失：不能据此推断协议实现进度。']
 lines += ['','## 决策登记','', '| 问题 | 状态 | 已选规则 |','|---|---|---|']
 for d in config.get('decisions',[]):lines.append(f"| {d['title']} | {d['status']} | {d['decision'] or '待决定'} |")
 atomic(root/'ACLT-PROGRESS.md','\n'.join(lines)+'\n')
 dump(root/'.aclt-flow/rules-status.json',rules)

def execute(root,job,run_dir,lock_fd):
 log=run_dir/'output.log';started=time.monotonic();code=None;status='ERROR'
 env={k:v for k,v in os.environ.items() if not k.startswith('ACLT_TEST_')}
 with log.open('wb') as output:
  try:
   p=subprocess.Popen(job['command'],cwd=root,env=env,stdout=output,stderr=subprocess.STDOUT,start_new_session=True,pass_fds=(lock_fd,))
   try:code=p.wait(timeout=job['timeout_seconds']);status='PASS' if code==0 else 'FAIL'
   except (subprocess.TimeoutExpired,KeyboardInterrupt) as e:
    os.killpg(p.pid,signal.SIGKILL);p.wait();status='TIMEOUT' if isinstance(e,subprocess.TimeoutExpired) else 'INTERRUPTED'
  except OSError as e:output.write(str(e).encode())
 text=log.read_text(errors='replace')
 missing=[s for s in job.get('required_output',[]) if not (re.search(s[3:],text,re.M) if s.startswith('re:') else s in text)]
 if status=='PASS' and missing:status='INCOMPLETE_OUTPUT'
 return {'status':status,'exit_code':code,'seconds':round(time.monotonic()-started,3),'missing_output':missing,'summaries':re.findall(r'^(?:PASS: .*|Ran [0-9]+ tests.*)$',text,re.M),'log':str(log.relative_to(root))}

def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('action',choices=['status','run']);parser.add_argument('--root',type=pathlib.Path,default=pathlib.Path.cwd());parser.add_argument('--force',action='store_true')
 args=parser.parse_args(argv);root=args.root.resolve();home=root/'.aclt-flow';home.mkdir(parents=True,exist_ok=True)
 with (home/'lock').open('a+') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:print('另一个流程正在更新，请稍后查看。',file=sys.stderr);return 2
  path=home/'template.json';config=read(path,{})
  if config.get('version')!=1:raise ValueError('unknown or missing workflow template')
  ids=[j['id'] for j in config['jobs']]
  if len(ids)!=len(set(ids)) or any(not re.fullmatch(r'[a-z0-9_-]+',i) for i in ids):raise ValueError('invalid job identifiers')
  earlier=set()
  for j in config['jobs']:
   if not set(j.get('needs',[]))<=earlier:raise ValueError('dependencies must precede the job')
   earlier.add(j['id'])
   if not isinstance(j['command'],list) or not j['command'] or not all(isinstance(s,str) for s in j['command']) or not 0<j['timeout_seconds']<=86400:raise ValueError('invalid command or timeout')
  decision_ids=[d['id'] for d in config.get('decisions',[])]
  if len(decision_ids)!=len(set(decision_ids)):raise ValueError('duplicate decision ID')
  for d in config.get('decisions',[]):
   if d['status'] not in ['OPEN','DECIDED'] or (d['status']=='DECIDED' and not d['decision'].strip()):raise ValueError('decision requires a written rule')
  env=environment(root);states=read(home/'state.json',{})
  for job in config['jobs']:
   key=job['id'];digest,files=fingerprint(root,job,path,env);old=states.get(key,{})
   if old.get('status')=='RUNNING':old['status']='INTERRUPTED'
   # Fingerprints and log digests are records; jobs are re-executed.
   if old.get('status')=='PASS':
    log=within(root,old['log'])
    paths=[log]+[log.parent/'artifacts'/name for name in old.get('artifacts',{})]
    if any(not path.is_file() for path in paths):old['status']='EVIDENCE_MISSING'
   decisions={d['id']:d['status'] for d in config.get('decisions',[])}
   if any(decisions.get(d)!='DECIDED' for d in job.get('requires_decisions',[])):old['status']='BLOCKED_DECISION'
   elif any(states.get(d,{}).get('status')!='PASS' for d in job.get('needs',[])):old['status']='BLOCKED_DEPENDENCY'
   states[key]=old
  dump(home/'state.json',states);render(root,config,states)
  if args.action=='status':print(root/'ACLT-PROGRESS.md');return 0
  bad=False
  for job in config['jobs']:
   key=job['id'];digest,files=fingerprint(root,job,path,env)
   if any(decisions.get(d)!='DECIDED' for d in job.get('requires_decisions',[])) or any(states.get(d,{}).get('status')!='PASS' for d in job.get('needs',[])):
    print(f"等待前置条件：{job['title']}",flush=True);bad=True;continue
   run_dir=home/'runs'/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]+'-'+key);run_dir.mkdir(parents=True)
   try:git=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,stderr=subprocess.DEVNULL,text=True).strip()
   except (OSError,subprocess.CalledProcessError):git=None
   record={'job':key,'started':stamp(),'fingerprint':digest,'source_files':files,'environment':env,'git_commit':git,'command':job['command'],'status':'RUNNING','sha_consistency':'DISABLED','log':str((run_dir/'output.log').relative_to(root))}
   states[key]=record;dump(run_dir/'record.json',record);dump(home/'state.json',states);render(root,config,states)
   print(f"开始：{job['title']}；日志：{record['log']}",flush=True)
   record.update(execute(root,job,run_dir,lock.fileno()));record['finished']=stamp()
   after,_=fingerprint(root,job,path,environment(root))
   latest=read(path,{})
   latest_job=next((j for j in latest.get('jobs',[]) if j['id']==key),None)
   if latest.get('version')!=config['version'] or latest_job!=job:record['status']='SOURCE_CHANGED'
   artifacts={}
   for name,hash_value in expand(root,job.get('evidence',[])).items():
    target=run_dir/'artifacts'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((root/name).read_bytes());artifacts[name]=hash_value
   record['artifacts']=artifacts
   record['log_sha256']=hashlib.sha256((run_dir/'output.log').read_bytes()).hexdigest()
   dump(run_dir/'record.json',record);dump(home/'state.json',states);render(root,config,states)
   print(f"完成：{job['title']} → {record['status']}",flush=True)
   bad|=record['status']!='PASS'
  return 1 if bad else 0
if __name__=='__main__':
 try:sys.exit(main())
 except (ValueError,KeyError,OSError,TypeError) as e:print('流程配置或文件错误：'+str(e),file=sys.stderr);sys.exit(2)
