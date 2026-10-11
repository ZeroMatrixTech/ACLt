import os,pathlib,json,runpy,sys
args=dict(x.split('=',1) for x in pathlib.Path('/proc/cmdline').read_text().split() if '=' in x)
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
path=pathlib.Path('/evidence')/('boot-'+boot+'.json');path.write_text(json.dumps({'boot':boot,'role':args['role'],'initialize':args.get('initialize')=='1'}))
with path.open('rb') as f:os.fsync(f.fileno())
os.setgid(1000);os.setuid(1000);sys.path.insert(0,'/experiment')
if args['role']=='receiver':
 if args.get('initialize')=='1':
  sys.argv=['receiver.py','--initialize'];runpy.run_path('/experiment/receiver.py',run_name='__main__')
 sys.argv=['receiver.py'];runpy.run_path('/experiment/receiver.py',run_name='__main__')
else:runpy.run_path('/experiment/node.py',run_name='__main__')
