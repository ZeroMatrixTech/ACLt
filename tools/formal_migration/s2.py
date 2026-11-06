# SPDX-License-Identifier: Apache-2.0
"""FM-S2 candidate single-authority state machine. NOT protocol admission.

All authority projections and signed request facts share one SQLite transaction.
The pure reducer is also used for offline replay. Old experimental APIs are absent.
"""
import copy
from contextlib import closing
import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import time
from tools.formal_migration import foundation as f, policy as p
from tools.verification_profile import codec as c

SCHEMA='ACLt/FM/S2/1'
ZERO=b'\0'*32
ROLES=('EXECUTOR','AUDITOR')
ACTIONS={'CREATE':{'bundle','receipt_signature'},'ACTIVATE':{'receipt','assignment','epoch'},
         'CONSUME':{'receipt','assignment','epoch','capability','intent'},
         'QUERY':{'receipt'},'FENCE':{'receipt'}}
REQUEST={'schema','genesis','actor','nonce','issued_at','expires_at','op','body','signature'}

def h(v):return c.domain_hash(SCHEMA,c.encode(v))
def fields(v,n):c.need(type(v) is dict and set(v)==set(n),'S2 fields')
def uint(v):c.need(type(v) is int and 0<=v<=p.U64,'S2 uint')
def pin(v):c.need(type(v) is bytes and len(v)==32,'S2 digest')
def signed_bytes(kind,v):return c.encode([SCHEMA,kind,v])
def sign(private,kind,v):
    with tempfile.TemporaryDirectory(prefix='fm-s2-sign-') as tmp:
        path=Path(tmp)/'input';path.write_bytes(signed_bytes(kind,v))
        return subprocess.run(['openssl','dgst','-sha256','-sign',str(private),'-sigopt','rsa_padding_mode:pkcs1',str(path)],capture_output=True,check=True,timeout=10).stdout

def verify_signature(der,kind,v,sig):
    c.need(type(sig) is bytes and len(sig)==256,'S2 signature size')
    f.crypto_verify(der,signed_bytes(kind,v),sig)

def request(config,private,actor,op,body,now,nonce=None):
    v=dict(schema=SCHEMA,genesis=h(config),actor=actor,nonce=nonce or os.urandom(32),issued_at=now,expires_at=now+120,op=op,body=body)
    return dict(v,signature=sign(private,'REQUEST',v))

def config_check(cfg):
    fields(cfg,{'schema','network','deployment','requester','providers','issuer_der','allowed_receipts','runtime_sha256','artifact','balance','caps','valid_from','valid_until','scope'})
    c.need(cfg['schema']==SCHEMA and cfg['scope']=='TEST_ONLY_NO_OFFICIAL_ADMISSION','S2 scope')
    for k in ('network','deployment','runtime_sha256'):pin(cfg[k])
    f.principal(cfg['requester']);c.need(cfg['requester']['role']=='REQUESTER','requester role')
    fields(cfg['providers'],ROLES)
    records=[cfg['requester'],*cfg['providers'].values()]
    for r in records:
        f.principal(r);c.need(r['status']=='ACTIVE' and r['network_id']==cfg['network'] and r['deployment_id']==cfg['deployment'],'pinned role context')
    c.need(all(r['role']=='PROVIDER' for r in cfg['providers'].values()),'provider role')
    ders=[r['public_key_der'] for r in records]+[cfg['issuer_der']]
    c.need(len(set(ders))==4 and len(cfg['issuer_der'])==294,'separate role/issuer keys')
    c.need(type(cfg['artifact']) is bytes and 0<len(cfg['artifact'])<=16384,'fixed artifact')
    c.need(type(cfg['allowed_receipts']) is list and 1<=len(cfg['allowed_receipts'])<=64,'finite receipt allowlist')
    for rid in cfg['allowed_receipts']:pin(rid)
    c.need(len(set(cfg['allowed_receipts']))==len(cfg['allowed_receipts']),'duplicate receipt')
    uint(cfg['balance']);uint(cfg['valid_from']);uint(cfg['valid_until']);c.need(cfg['valid_from']<cfg['valid_until'],'config expiry')
    fields(cfg['caps'],{'provider','cluster','receipt','window','global'})
    for row in cfg['caps'].values():
        fields(row,{'concurrency','value','attempts'})
        for v in row.values():uint(v);c.need(v>0,'positive cap')

def initial(cfg):return dict(free=cfg['balance'],held=0,tasks={},nonces={},last_time=cfg['valid_from'])
def aid(cfg,rid,role):return h([h(cfg),rid,role,'ASSIGNMENT'])
def proposal(cfg,rid,role,bundle):
    e=bundle['receipt']['execution'];record=cfg['providers'][role]
    return dict(schema=SCHEMA,genesis=h(cfg),receipt=rid,assignment=aid(cfg,rid,role),provider=f.principal_digest(record),role=role,epoch=1,deadline=e['deadline'],receipt_execution=e,rir_digest=c.domain_hash('ACLt/RIR-0/Artifact/1',cfg['artifact']),runtime_sha256=cfg['runtime_sha256'],input_ref=bundle['receipt']['input_refs'][0]['digest'])
def capability(cfg,prop):return h(['CAPABILITY',h(cfg),prop])

def verify_request(cfg,req,now,actions=ACTIONS):
    fields(req,REQUEST)
    c.need(req['schema']==SCHEMA and req['genesis']==h(cfg),'S2 genesis/schema')
    pin(req['actor']);pin(req['nonce']);uint(req['issued_at']);uint(req['expires_at'])
    c.need(type(req['op']) is str and req['op'] in actions,'unsupported S2 operation')
    fields(req['body'],actions[req['op']])
    records=[cfg['requester'],*cfg['providers'].values()]
    record=next((r for r in records if f.principal_digest(r)==req['actor']),None)
    c.need(record is not None,'unknown actor pin')
    check_request_time(cfg,req,record,now)
    c.need(req['expires_at']-req['issued_at']<=120,'request lifetime')
    verify_signature(record['public_key_der'],'REQUEST',{k:req[k] for k in req if k!='signature'},req['signature'])
    return record

def check_request_time(cfg,req,record,now):
    c.need(cfg['valid_from']<=now<cfg['valid_until'] and record['valid_from']<=req['issued_at']<=now<req['expires_at']<=record['valid_until'],'expired request/config')

def exposure(cfg,state):
    out={}
    for rid,t in state['tasks'].items():
        for role,l in t['leases'].items():
            if l['state'] not in ('ACTIVE','CONSUMED'):continue
            prop=l['proposal'];value=t['bundle']['funding']['execution_limit' if role=='EXECUTOR' else 'verification_limit']
            keys=['provider:'+prop['provider'].hex(),'cluster:UNKNOWN_SHARED','receipt:'+rid,'window:FIXED_DEPLOYMENT','global:ALL']
            for key in keys:
                row=out.setdefault(key,dict(concurrency=0,value=0,attempts=0))
                row['concurrency']+=1;row['value']+=value;row['attempts']+=1
    for key,row in out.items():
        cap=cfg['caps'][key.split(':')[0]]
        c.need(all(row[k]<=cap[k] for k in row),'exposure cap '+key.split(':')[0])
    return out

def check_funding_conservation(cfg, state):
    tasks = state['tasks'].values()
    paid = sum(task.get('settlement', {}).get('paid', 0) for task in tasks)
    held = sum(task['funding_held'] for task in tasks)
    c.need(state['free'] + state['held'] + paid == cfg['balance'] and state['held'] == held,
           'funding conservation')

def task_view(t):
    return dict(receipt=t['rid'],funding_held=t['funding_held'],fenced=t['fenced'],leases=t['leases'],terminal='NOT_IMPLEMENTED_FM_S3',settlement='DISABLED')

def reduce(cfg,state,req,now):
    """Raises before caller COMMIT; rejected requests never change business state."""
    record=verify_request(cfg,req,now);c.need(now>=state['last_time'],'authority clock rollback')
    op=req['op'];b=req['body'];actor=req['actor'];requester=f.principal_digest(cfg['requester'])
    nonce=actor.hex()+':'+req['nonce'].hex();old=state['nonces'].get(nonce)
    if old is not None:
        c.need(old['request']==h(req),'idempotency conflict')
        if op in ('ACTIVATE','CONSUME'):
            t=state['tasks'][b['receipt'].hex()];c.need(not t['fenced'] and now<t['bundle']['receipt']['execution']['deadline'],'stale lease/deadline')
        if op=='QUERY':
            t=state['tasks'][b['receipt'].hex()]
            return state,dict(task=task_view(t),free=state['free'],held=state['held'],exposure=exposure(cfg,state))
        return state,old['result']
    nxt=copy.deepcopy(state)
    if op=='QUERY':
        pin(b['receipt']);t=nxt['tasks'].get(b['receipt'].hex());c.need(t is not None,'unknown receipt')
        used=t['queries'].get(actor.hex(),0);c.need(used<t['bundle']['receipt']['execution']['recovery_queries'],'query budget exhausted')
        t['queries'][actor.hex()]=used+1
        result=dict(task=copy.deepcopy(task_view(t)),free=nxt['free'],held=nxt['held'],exposure=exposure(cfg,nxt))
    elif op=='CREATE':
        c.need(actor==requester and record['role']=='REQUESTER','create role')
        bundle=b['bundle'];rid=p.bundle(bundle);c.need(rid in cfg['allowed_receipts'],'receipt not allowlisted')
        r=bundle['receipt'];c.need(r['network_id']==cfg['network'] and r['deployment_id']==cfg['deployment'],'receipt context')
        p.verify(dict(bundle=bundle,record=record,signature=b['receipt_signature'],expected_receipt=rid,expected_requester=requester,now=now))
        c.need(rid.hex() not in nxt['tasks'],'receipt already created')
        c.need(not any(t['bundle']['receipt']['scope']['nonce']==r['scope']['nonce'] for t in nxt['tasks'].values()),'requester nonce reused')
        # A finite allowlist binds the exact reviewed input/policies/component bytes.
        rir=bundle['components'][0];c.need(rir['kind']=='RIR' and rir['content']==cfg['artifact'],'artifact content pin')
        e=r['execution'];c.need(e['memory_bytes']==131072 and e['fuel']==50000000 and e['output_bytes_limit']==4096,'fixed core limits')
        leases={role:dict(proposal=proposal(cfg,rid,role,bundle),state='PROPOSED',intent=ZERO) for role in ROLES}
        t=dict(rid=rid,bundle=bundle,funding_held=0,leases=leases,fenced=False,queries={})
        nxt['tasks'][rid.hex()]=t;result=task_view(t)
    else:
        pin(b['receipt']);t=nxt['tasks'].get(b['receipt'].hex());c.need(t is not None,'unknown receipt')
        if op=='FENCE':
            c.need(actor==requester and now>=t['bundle']['receipt']['execution']['deadline'],'fence before deadline/role')
            t['fenced']=True
            for l in t['leases'].values():l['state']='FENCED'
            # Funds remain held pending FM-S3: expiry is NOT a verification terminal/refund.
            result=task_view(t)
        else:
            pin(b['assignment']);uint(b['epoch']);c.need(b['epoch']==1 and not t['fenced'] and now<t['bundle']['receipt']['execution']['deadline'],'stale epoch/lease/deadline')
            role=next((role for role in ROLES if t['leases'][role]['proposal']['assignment']==b['assignment']),None)
            c.need(role is not None,'foreign assignment');l=t['leases'][role]
            c.need(actor==l['proposal']['provider'] and record['role']=='PROVIDER','accept/consume role')
            if op=='ACTIVATE':
                c.need(l['state']=='PROPOSED','lease already activated')
                if t['funding_held']==0:
                    amount=t['bundle']['funding']['total_limit'];c.need(nxt['free']>=amount,'insufficient test funds')
                    nxt['free']-=amount;nxt['held']+=amount;t['funding_held']=amount
                l['state']='ACTIVE';l['capability']=capability(cfg,l['proposal'])
                result=copy.deepcopy(l)
            else:
                pin(b['capability']);pin(b['intent'])
                c.need(l['state']=='ACTIVE' and b['capability']==l['capability'],'consumed/inactive/capability mismatch')
                l['state']='CONSUMED';l['intent']=b['intent'];result=copy.deepcopy(l)
    exposure(cfg,nxt)
    check_funding_conservation(cfg,nxt)
    nxt['last_time']=now;nxt['nonces'][nonce]=dict(request=h(req),result=({'query':True} if op=='QUERY' else copy.deepcopy(result)))
    c.decode(c.encode(nxt))  # state must remain within the shared bounded codec
    return nxt,result

class Ledger:
    @staticmethod
    def transition(cfg,state,req,now,events,clock=None):
        nxt,result=reduce(cfg,state,req,now)
        return nxt,result,now

    def __init__(self,path,cfg,private,clock=None,create=False,hook=None):
        config_check(cfg);verify_signature(cfg['issuer_der'],'GENESIS',h(cfg),sign(private,'GENESIS',h(cfg)));self.path=Path(path);self.cfg=cfg;self.private=private;self.clock=clock or (lambda:int(time.time()));self.hook=hook or (lambda _:None)
        if create:
            fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
            with closing(self.connect()) as db:
                db.executescript('CREATE TABLE meta(genesis BLOB NOT NULL,state BLOB NOT NULL); CREATE TABLE events(seq INTEGER PRIMARY KEY, raw BLOB NOT NULL, digest BLOB NOT NULL);')
                db.execute('INSERT INTO meta VALUES(?,?)',(h(cfg),c.encode(initial(cfg))))
        c.need(self.path.is_file() and not self.path.is_symlink(),'missing database')
        self.replay()  # refuse corruption/other genesis/old databases on every open
    def connect(self):
        db=sqlite3.connect(self.path,timeout=15,isolation_level=None);db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA journal_mode=DELETE');return db
    def state(self):
        with closing(self.connect()) as db:return c.decode(db.execute('SELECT state FROM meta').fetchone()[0])
    def replay(self):
        with closing(self.connect()) as db:
            db.execute('BEGIN');row=db.execute('SELECT genesis,state FROM meta').fetchone();c.need(row is not None and row[0]==h(self.cfg),'database genesis')
            state=initial(self.cfg);prev=ZERO;proof=[]
            for seq,(stored_seq,raw,digest) in enumerate(db.execute('SELECT seq,raw,digest FROM events ORDER BY seq'),1):
                c.need(stored_seq==seq,'stored event sequence')
                event=c.decode(raw);fields(event,{'schema','genesis','seq','prev','parents','now','request','state_digest','result_digest'})
                c.need(event['schema']==SCHEMA and event['genesis']==h(self.cfg) and event['seq']==seq and event['prev']==prev and event['parents']==([] if seq==1 else [prev]) and h(event)==digest,'event chain')
                state,result,_=self.transition(self.cfg,state,event['request'],event['now'],proof)
                proof.append(raw)
                c.need(h(state)==event['state_digest'] and h(result)==event['result_digest'],'replay projection')
                prev=digest
            c.need(c.encode(state)==row[1],'stored projection differs from replay')
            db.rollback();return dict(seq=seq if 'seq' in locals() else 0,head=prev,state_digest=h(state))
    def handle(self,raw):
        req=c.decode(raw)
        db=self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            now=self.clock();uint(now)
            state=c.decode(db.execute('SELECT state FROM meta').fetchone()[0])
            proof=[r[0] for r in db.execute('SELECT raw FROM events ORDER BY seq')]
            nxt,result,now=self.transition(self.cfg,state,req,now,proof,self.clock)
            last=db.execute('SELECT seq,digest FROM events ORDER BY seq DESC LIMIT 1').fetchone();seq,prev=(0,ZERO) if last is None else last
            if nxt!=state:
                seq+=1;c.need(seq<=256,'finite deployment event budget');event=dict(schema=SCHEMA,genesis=h(self.cfg),seq=seq,prev=prev,parents=[] if seq==1 else [prev],now=now,request=req,state_digest=h(nxt),result_digest=h(result));prev=h(event)
                db.execute('INSERT INTO events VALUES(?,?,?)',(seq,c.encode(event),prev));db.execute('UPDATE meta SET state=?',(c.encode(nxt),))
                proof.append(c.encode(event))
            checkpoint=dict(schema=SCHEMA,genesis=h(self.cfg),seq=seq,head=prev,state_digest=h(nxt))
            payload=dict(schema=SCHEMA,genesis=h(self.cfg),request=h(req),now=now,result=result,checkpoint=checkpoint,events=proof)
            # Sign before commit: signing failure cannot consume a business right.
            response=c.encode(dict(payload=payload,signature=sign(self.private,'RESPONSE',payload)))
            c.need(len(response)<=900000,'response proof size limit')
            self.hook('BEFORE_COMMIT');db.commit();self.hook('AFTER_COMMIT');return response
        except BaseException:
            db.rollback();raise
        finally:db.close()

def check_response(cfg,req,raw,anchor=None):
    v=c.decode(raw);fields(v,{'payload','signature'});q=v['payload'];fields(q,{'schema','genesis','request','now','result','checkpoint','events'})
    c.need(q['schema']==SCHEMA and q['genesis']==h(cfg) and q['request']==h(req),'response challenge/context')
    verify_signature(cfg['issuer_der'],'RESPONSE',q,v['signature']);uint(q['now'])
    c.need(cfg['valid_from']<=q['now']<cfg['valid_until'] and req['issued_at']<=q['now']<req['expires_at'],'response time context')
    cp=q['checkpoint']
    fields(cp,{'schema','genesis','seq','head','state_digest'});uint(cp['seq']);pin(cp['head']);pin(cp['state_digest'])
    c.need(cp['schema']==SCHEMA and cp['genesis']==h(cfg),'checkpoint context')
    prev=ZERO;seen={0:ZERO}
    c.need(type(q['events']) is list and len(q['events'])==cp['seq']<=256,'bounded inclusion proof')
    for seq,raw_event in enumerate(q['events'],1):
        event=c.decode(raw_event)
        c.need(event['schema']==SCHEMA and event['genesis']==h(cfg) and event['seq']==seq and event['prev']==prev and event['parents']==([] if seq==1 else [prev]),'inclusion chain')
        prev=h(event);seen[seq]=prev
    c.need(prev==cp['head'] and (not q['events'] or event['state_digest']==cp['state_digest']),'checkpoint inclusion')
    if not q['events']:c.need(cp['state_digest']==h(initial(cfg)),'initial checkpoint state')
    if anchor is not None:
        c.need(seen.get(anchor['seq'])==anchor['head'],'checkpoint consistency')
        c.need(cp['seq']>=anchor['seq'],'checkpoint rollback')
        if cp['seq']==anchor['seq']:c.need(cp==anchor,'checkpoint fork')
    return q
