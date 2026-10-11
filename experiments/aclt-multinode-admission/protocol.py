"""Enrolled simulation protocol. No real-world identity/independence attestation."""
import hashlib,hmac,json,secrets,socket
def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
def digest(data):return hashlib.sha256(data).hexdigest()
def claim(values):return digest(('ACLT-LOCAL-CLAIM-1\nstats-int-v1\n'+' '.join(map(str,values))).encode())
def rows(values,chunk):
 return ''.join(f'{i//chunk} {i} {len(v)} {sum(v)} {min(v)} {max(v)}\n' for i in range(0,len(values),chunk) for v in [values[i:i+chunk]])
def sign(payload,secret):
 m=dict(payload);m['mac']=hmac.new(secret.encode(),canonical(payload),hashlib.sha256).hexdigest();return m
def check(message,secret):
 obj=dict(message);mac=obj.pop('mac',None)
 if not isinstance(mac,str) or not hmac.compare_digest(mac,hmac.new(secret.encode(),canonical(obj),hashlib.sha256).hexdigest()):raise ValueError('authentication failed')
 return obj
def request(host,port,message,secret,timeout=15):
 with socket.create_connection((host,port),timeout=timeout) as s:
  s.settimeout(timeout);s.sendall(canonical(message)+b'\n');raw=s.makefile('rb').readline(1048577)
 if not raw.endswith(b'\n') or len(raw)>1048576:raise ValueError('response framing')
 reply=check(json.loads(raw),secret)
 if reply.get('nonce')!=message['nonce']:raise ValueError('response nonce mismatch')
 return reply['reply']
def envelope(op,key,task,boot,secret,**extra):
 return sign(dict(v=1,op=op,key=key,task=task,boot=boot,nonce=secrets.token_hex(16),**extra),secret)
