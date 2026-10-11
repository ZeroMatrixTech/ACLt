import http.server,json,os,pathlib,socketserver,threading,time
from ledger import Store
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
def serve(receiver,port=9000,adminport=9001):
 class Handler(socketserver.StreamRequestHandler):
  def handle(self):
   self.connection.settimeout(10)
   try:
    raw=self.rfile.readline(1048577)
    if len(raw)>1048576 or not raw.endswith(b'\n'):return
    message=json.loads(raw);response=receiver.handle(message)
    if receiver.drop_next and message.get('op')=='submit':receiver.drop_next=False;return
    self.wfile.write(canonical(response)+b'\n')
   except Exception as ex:
    self.wfile.write(canonical({'error':type(ex).__name__+': '+str(ex)})+b'\n')
 class Admin(http.server.BaseHTTPRequestHandler):
  def log_message(self,*a):pass
  def do_POST(self):
   try:
    obj=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
    if obj['action']=='pause':receiver.pause_stage=obj['stage'];result={'armed':True}
    elif obj['action']=='drop-reply':receiver.drop_next=True;result={'armed':True}
    elif obj['action']=='status':result={task:receiver.store.audit(claim(c['values'])) for task,c in receiver.config['tasks'].items()}
    else:raise ValueError('unknown control action')
    data=canonical(result);self.send_response(200)
   except Exception as ex:data=canonical({'error':repr(ex)});self.send_response(500)
   self.end_headers();self.wfile.write(data)
 tcp=TCP(('0.0.0.0',port),Handler);threading.Thread(target=tcp.serve_forever,daemon=True).start()
 print('RECEIVER_READY',flush=True);http.server.ThreadingHTTPServer(('0.0.0.0',adminport),Admin).serve_forever()

if __name__=='__main__':
 import sys
 path=pathlib.Path('/data/manifest.json');manifest=json.loads(path.read_text());db='/data/ledger.sqlite'
 # Initialization is an explicit test administrator action on the first boot only.
 # /data/initialized is NEVER recreated by service startup.
 if '--initialize' in sys.argv:
  Receiver(manifest,db,True)
  with open('/data/initialized','x') as f:f.write('1\n');f.flush();os.fsync(f.fileno())
  fd=os.open('/data',os.O_RDONLY);os.fsync(fd);os.close(fd)
  print('INITIALIZED',flush=True)
 else:
  if pathlib.Path('/data/initialized').read_text()!='1\n':raise ValueError('operator initialization required')
  serve(Receiver(manifest,db))
