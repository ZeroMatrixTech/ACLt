
if not __debug__:
    raise SystemExit('assert-based validation requires Python without -O/PYTHONOPTIMIZE')

import http.server,json,os,pathlib,socketserver,threading,time
from ledger import Store
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/"tools"))
import test_control

from protocol import canonical,digest,claim,rows,sign,check

class Receiver:
 def __init__(self,manifest,database,initialize=False):
  self.config=manifest;self.sha=digest(canonical(manifest));self.pause_stage=None;self.pause_claim=None;self.drop_next=False
  self.store=Store.create(database,self.sha) if initialize else Store(database,self.sha)
  self.store.hook=self.hook
  aliases={}
  for task,c in manifest['tasks'].items():
   assert isinstance(c['chunk'],int) and c['chunk']>0 and c['values'] and len(c['values'])<=100000
   assert all(type(v)==int and -1000000000<=v<=1000000000 for v in c['values'])
   k=claim(c['values']);binding=canonical(dict(values=c['values'],chunk=c['chunk'],units=sorted(c['units'])))
   if k in aliases and aliases[k]!=binding:raise ValueError('ambiguous claim alias contract')
   aliases[k]=binding
 def hook(self,stage):
  if self.pause_stage==stage:
   print('CHECKPOINT '+stage,flush=True)
   until=time.monotonic()+90
   while time.monotonic()<until:time.sleep(.02)
   raise TimeoutError('unreleased transaction hook')
 def handle(self,msg):
  key=msg.get('key');credential=self.config['keys'].get(key)
  if not credential:raise ValueError('unknown key')
  obj=check(msg,credential['secret'])
  op=obj.get('op');base={'v','op','key','task','boot','nonce'}
  if set(obj)!=(base|({'ticket','rows'} if op=='submit' else set())) or op not in ['reserve','submit','audit'] or obj['v']!=1:raise ValueError('invalid message fields')
  if not isinstance(obj['boot'],str) or len(obj['boot'])!=36 or not isinstance(obj['nonce'],str) or len(obj['nonce'])!=32:raise ValueError('invalid binding')
  task=self.config['tasks'].get(obj['task']);unit=credential['unit']
  if task is None or unit not in task['units']:raise ValueError('ineligible task or unit')
  k=claim(task['values'])
  if op=='reserve':result=self.store.reserve(k,unit,obj['boot'])
  elif op=='audit':result=self.store.audit(k)
  else:
   if not isinstance(obj['rows'],str) or len(obj['rows'])>524288 or not isinstance(obj['ticket'],str):raise ValueError('invalid result')
   valid=obj['rows']==rows(task['values'],task['chunk'])
   result=self.store.submit(k,unit,obj['boot'],obj['ticket'],digest(obj['rows'].encode()),valid=valid)
  return sign({'nonce':obj['nonce'],'reply':result},credential['secret'])

class TCP(socketserver.ThreadingTCPServer):allow_reuse_address=True;daemon_threads=True
def servers(receiver,port=9000,bind='127.0.0.1',adminport=0,admin_bind='127.0.0.1',control_token=None):
 class Handler(socketserver.StreamRequestHandler):
  def handle(self):
   self.connection.settimeout(10)
   try:
    raw=self.rfile.readline(1048577)
    if len(raw)>1048576 or not raw.endswith(b'\n'):return
    message=json.loads(raw);reply=receiver.handle(message)
    if receiver.drop_next and message.get('op')=='submit':receiver.drop_next=False;return
    self.wfile.write(canonical(reply)+b'\n')
   except Exception as ex:self.wfile.write(canonical({'error':type(ex).__name__})+b'\n')
 class Admin(test_control.BoundedHandler):
  def log_message(self,*a):pass
  def do_POST(self):
   try:
    obj=test_control.request(self)
    if obj['action']=='pause':receiver.pause_stage=obj['stage'];result={'armed':True}
    elif obj['action']=='drop-reply':receiver.drop_next=True;result={'armed':True}
    elif obj['action']=='status':result={task:receiver.store.audit(claim(c['values'])) for task,c in receiver.config['tasks'].items()}
    else:raise ValueError('unknown control action')
    test_control.response(self,result)
   except Exception as ex:test_control.response(self,{'error':type(ex).__name__},403 if isinstance(ex,PermissionError) else 400)
 if control_token is not None:test_control.validate_token(control_token)
 tcp=TCP((bind,port),Handler)
 try:
  admin=None if control_token is None else http.server.ThreadingHTTPServer((admin_bind,adminport),Admin)
  if admin is not None:admin.control_token=control_token;admin.daemon_threads=True
  return tcp,admin
 except BaseException:tcp.server_close();raise

def serve(receiver,port=9000,bind='127.0.0.1',adminport=0,admin_bind='127.0.0.1',control_token=None):
 tcp,admin=servers(receiver,port,bind,adminport,admin_bind,control_token)
 try:
  if admin is not None:threading.Thread(target=admin.serve_forever,daemon=True).start()
  print('RECEIVER_READY',flush=True);tcp.serve_forever()
 finally:
  tcp.server_close()
  if admin is not None:admin.shutdown();admin.server_close()

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--initialize',action='store_true');p.add_argument('--manifest',type=pathlib.Path,default=pathlib.Path('/data/manifest.json'));p.add_argument('--database',default='/data/ledger.sqlite');p.add_argument('--bind',default='127.0.0.1');p.add_argument('--port',type=int,default=9000);p.add_argument('--test-admin-token-file',type=pathlib.Path);p.add_argument('--test-admin-bind',default='127.0.0.1');p.add_argument('--test-admin-port',type=int,default=9001);a=p.parse_args()
 token=test_control.token_file(a.test_admin_token_file) if a.test_admin_token_file else None
 manifest=json.loads(a.manifest.read_text())
 if a.initialize:Receiver(manifest,a.database,True)
 else:serve(Receiver(manifest,a.database),a.port,a.bind,a.test_admin_port,a.test_admin_bind,token)
