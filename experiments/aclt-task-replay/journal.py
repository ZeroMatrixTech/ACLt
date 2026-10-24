# SPDX-License-Identifier: Apache-2.0
"""Durable worker stream and transaction-local authority event append."""
from pathlib import Path
import fcntl
import os
from context import encode,decode,need,Rejected,HostFault,sha,ZERO,event_id,event_bytes,durable_new,sync_directory,regular

def check_events(events,stream):
    head=ZERO
    for seq,raw in enumerate(events,1):
        obj=decode(raw)
        need(set(obj)=={'schema_id','stream','seq','prev','kind','payload_ref','parents'} and obj['schema_id']=='aclt.exp.causal-event@1','event fields')
        need(obj['stream']==stream and type(obj['seq']) is int and obj['seq']==seq and obj['prev']==head,'journal sequence/previous hash')
        need(type(obj['parents']) is list and len(obj['parents'])<=8 and all(type(v) is bytes and len(v)==32 for v in obj['parents']),'parent types')
        need(obj['parents']==sorted(set(obj['parents'])),'parent order/duplicates');head=event_id(raw)
    return head

class Journal:
    def __init__(self,path,stream,create=False):
        self.path=Path(path);self.stream=stream
        if create:
            self.path.mkdir(mode=0o700,exist_ok=False)
            for n in ['objects','events']:(self.path/n).mkdir(mode=0o700)
            durable_new(self.path/'stream',stream);sync_directory(self.path);sync_directory(self.path.parent)
        need(not self.path.is_symlink() and regular(self.path/'stream')==stream,'worker journal stream mismatch')
    def put(self,data):
        digest=sha(data);path=self.path/'objects'/digest.hex()
        if path.exists():need(regular(path)==data,'object digest collision')
        else:
            try:durable_new(path,data)
            except base_rejected():need(regular(path)==data,'concurrent object mismatch')
        return digest
    def events(self):
        paths=sorted((self.path/'events').iterdir())
        need([p.name for p in paths]==[f'{i:08}.cbor' for i in range(1,len(paths)+1)],'missing or unexpected worker journal files')
        events=[regular(p) for p in paths];check_events(events,self.stream);return events
    def append(self,kind,payload,parents=()):
        # flock protects allocation of event sequence; launch exclusivity is separate.
        fd=os.open(self.path/'lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX);events=self.events();prev=event_id(events[-1]) if events else ZERO
            pref=self.put(encode(payload));raw=event_bytes(self.stream,len(events)+1,prev,kind,pref,parents)
            durable_new(self.path/'events'/f'{len(events)+1:08}.cbor',raw);return event_id(raw)
        finally:os.close(fd)
    def snapshot(self):
        events=self.events();objects={p.name:regular(p) for p in sorted((self.path/'objects').iterdir())}
        for key,value in objects.items():need(sha(value).hex()==key,'worker object corruption')
        return {'schema_id':'aclt.exp.worker-journal@1','stream':self.stream,'events':events,'objects':objects}
    def get(self,digest):return regular(self.path/'objects'/digest.hex())

def base_rejected():
    from common import Rejected as OldRejected
    return OldRejected

def sql_put(c,data):
    digest=sha(data);row=c.execute('SELECT data FROM objects WHERE digest=?',(digest,)).fetchone()
    if row is None:c.execute('INSERT INTO objects VALUES(?,?)',(digest,data))
    else:need(row[0]==data,'authority object collision')
    return digest

def sql_append(c,stream,kind,payload,parents=()):
    row=c.execute('SELECT seq,digest FROM journal ORDER BY seq DESC LIMIT 1').fetchone();seq=1 if row is None else row[0]+1;prev=ZERO if row is None else row[1]
    pref=sql_put(c,encode(payload));raw=event_bytes(stream,seq,prev,kind,pref,parents);digest=event_id(raw)
    c.execute('INSERT INTO journal VALUES(?,?,?)',(seq,digest,raw));return digest

def snapshot_check(pack):
    need(type(pack) is dict and set(pack)=={'schema_id','stream','events','objects'} and pack['schema_id']=='aclt.exp.worker-journal@1','worker snapshot shape')
    need(type(pack['events']) is list and type(pack['objects']) is dict,'worker snapshot types')
    for key,data in pack['objects'].items():need(type(data) is bytes and sha(data).hex()==key,'snapshot object hash')
    head=check_events(pack['events'],pack['stream'])
    for raw in pack['events']:
        event=decode(raw);need(event['payload_ref'].hex() in pack['objects'],'missing worker payload')
    return head
