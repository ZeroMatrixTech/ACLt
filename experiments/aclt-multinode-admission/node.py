import http.server,json,os,pathlib,subprocess,threading,time

import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/"tools"))
import test_control

from protocol import canonical,claim,digest,envelope,request,sign
D=None;BOOT='';CONF=None;LOCK=threading.Lock()
WORKER='/repo/experiments/aclt-minimal-verifier-state3/build/worker'
def durable(path,data,new=True):
 with path.open('xb' if new else 'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
 fd=os.open(path.parent,os.O_RDONLY);os.fsync(fd);os.close(fd)
def transmit(msg,secret):return request('10.0.2.2',CONF['receiver_port'],msg,secret)
def perform(obj):
 if obj.get('delay'):
  print('NODE_DELAY_READY '+obj['action']+' '+obj['task'],flush=True)
  time.sleep(min(float(obj['delay']),2))
 key=obj.get('key',CONF['default_key']);secret=CONF['keys'].get(key,'test-only-unregistered');task=obj['task'];contract=CONF['tasks'][task]
 marker=D/(claim(contract['values'])+'.used');packet=D/(claim(contract['values'])+'.submit.json')
 if obj['action']=='compute':
  with LOCK:
   durable(marker,canonical({'boot':BOOT,'task':task}))
  reservation=transmit(envelope('reserve',key,task,BOOT,secret),secret)
  if reservation['status']!='reserved':return {'reservation':reservation,'computed':False,'boot':BOOT}
  if obj.get('stop_after_reserve'):return {'reservation':reservation,'computed':False,'boot':BOOT}
  source=D/(claim(contract['values'])+'.input');durable(source,(' '.join(map(str,contract['values']))+'\n').encode())
  # One direct worker execution for the whole task; no computation retry/resume API.
  p=subprocess.run([WORKER,str(source),str(contract['chunk'])],capture_output=True,timeout=10)
  durable(D/(claim(contract['values'])+'.execution.json'),canonical({'boot':BOOT,'rc':p.returncode,'stdout_sha256':digest(p.stdout)}))
  if p.returncode!=0:return {'computed':True,'error':'worker failed','boot':BOOT}
  msg=envelope('submit',key,task,BOOT,secret,ticket=reservation['ticket'],rows=p.stdout.decode())
  durable(packet,canonical(msg))
  durable(D/(claim(contract['values'])+'.sending'),b'1\n')
  if obj.get('prepare_only'):return {'computed':True,'prepared':True,'boot':BOOT}
  return {'computed':True,'reply':transmit(msg,secret),'boot':BOOT,'envelope_sha256':digest(canonical(msg))}
 if obj['action']=='replay':
  if not (D/(claim(contract['values'])+'.sending')).exists():raise ValueError('no previously attempted complete submission')
  msg=json.loads(packet.read_text());secret=CONF['keys'][msg['key']]
  return {'reply':transmit(msg,secret),'boot':BOOT,'original_boot':msg['boot'],'envelope_sha256':digest(canonical(msg))}
 if obj['action']=='audit':return transmit(envelope('audit',key,task,BOOT,secret),secret)
 if obj['action']=='reserve':return transmit(envelope('reserve',key,task,BOOT,secret),secret)
 if obj['action']=='inject':
  msg=json.loads(packet.read_text())
  if 'rows' in obj:msg['rows']=obj['rows']
  if 'boot' in obj:msg['boot']=obj['boot']
  if 'ticket' in obj:msg['ticket']=obj['ticket']
  if 'key' in obj:msg['key']=key
  if 'unit' in obj:msg['unit']=obj['unit']
  msg.pop('mac');msg=sign(msg,secret)
  return transmit(msg,secret)
 raise ValueError('unknown node action')
class Handler(test_control.BoundedHandler):
 def log_message(self,*a):pass
 def do_POST(self):
  try:
   obj=test_control.request(self)
   if obj['action']=='info':result={'boot':BOOT,'files':{p.name:digest(p.read_bytes()) for p in D.iterdir() if p.is_file()}}
   else:result=perform(obj)
   test_control.response(self,result)
  except Exception as ex:test_control.response(self,{'error':type(ex).__name__},403 if isinstance(ex,PermissionError) else 400)
def control_server(directory,config,token,bind='127.0.0.1',port=9001):
 global D,BOOT,CONF
 test_control.validate_token(token)
 D=pathlib.Path(directory);BOOT=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip();CONF=config
 service=http.server.ThreadingHTTPServer((bind,port),Handler);service.control_token=token;service.daemon_threads=True;return service

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--data',type=pathlib.Path,default=pathlib.Path('/data'));p.add_argument('--test-control-token-file',type=pathlib.Path,required=True);p.add_argument('--bind',default='127.0.0.1');p.add_argument('--port',type=int,default=9001);a=p.parse_args()
 token=test_control.token_file(a.test_control_token_file)
 with control_server(a.data,json.loads((a.data/'node.json').read_text()),token,a.bind,a.port) as service:
  print('NODE_READY '+BOOT,flush=True);service.serve_forever()
