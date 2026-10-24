# SPDX-License-Identifier: Apache-2.0
"""Atomic authority journal/projections and immutable acceptance receipts; experiment only."""
from contextlib import closing
from pathlib import Path
import hmac
import os
import secrets
import sqlite3
import time
from context import *
from journal import sql_put,sql_append,snapshot_check

class Ledger:
    def __init__(self,path,private,public,providers,initialize=False,clock=time.time):
        self.path=Path(path);self.private=Path(private);self.public=Path(public);self.providers=dict(providers);self.clock=clock
        self.public_digest=sha(regular(public));self.enrollment=sha(encode({p.hex():sha(s) for p,s in providers.items()}))
        if initialize:
            fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
            with closing(sqlite3.connect(self.path)) as c:
                c.execute('PRAGMA synchronous=FULL');c.executescript('CREATE TABLE meta(key TEXT PRIMARY KEY,value BLOB);'
                  'CREATE TABLE objects(digest BLOB PRIMARY KEY,data BLOB NOT NULL);'
                  'CREATE TABLE journal(seq INTEGER PRIMARY KEY,digest BLOB UNIQUE,data BLOB NOT NULL);'
                  'CREATE TABLE tasks(task BLOB PRIMARY KEY,commit_ref BLOB,artifact_ref BLOB,input_ref BLOB,event BLOB);'
                  'CREATE TABLE grants(task BLOB,unit BLOB,epoch INTEGER,body BLOB,packet BLOB,gid BLOB UNIQUE,issue_event BLOB,consume_event BLOB,PRIMARY KEY(task,unit));'
                  'CREATE TABLE accepted(gid BLOB PRIMARY KEY,submission BLOB,receipt BLOB,event BLOB);')
                c.executemany('INSERT INTO meta VALUES(?,?)',[('authority_id',secrets.token_bytes(16)),('public_digest',self.public_digest),('enrollment',self.enrollment)]);c.commit()
            sync_directory(self.path.parent)
        with closing(self.connect()) as c:
            self.authority_id=dict(c.execute('SELECT key,value FROM meta'))['authority_id']
        self.stream=stream_id('authority',self.authority_id)
    def connect(self):
        need(self.path.is_file() and not self.path.is_symlink(),'existing authority journal required')
        c=sqlite3.connect(self.path.absolute().as_uri()+'?mode=rw',uri=True,isolation_level=None,timeout=10)
        try:
            c.execute('PRAGMA synchronous=FULL');c.execute('PRAGMA journal_mode=DELETE')
            meta=dict(c.execute('SELECT key,value FROM meta'))
            need(meta['public_digest']==self.public_digest and meta['enrollment']==self.enrollment,'frozen issuer/enrollment mismatch')
            if hasattr(self,'authority_id'):need(meta['authority_id']==self.authority_id,'authority deployment mismatch')
            return c
        except BaseException:c.close();raise
    def register(self,commitment,artifact,data):
        identity=task_id(commitment);bind(commitment,identity,artifact,[data]);tid=bytes.fromhex(identity)
        c=self.connect()
        try:
            c.execute('BEGIN IMMEDIATE');refs=[sql_put(c,b) for b in [commitment,artifact,data]]
            row=c.execute('SELECT commit_ref,artifact_ref,input_ref,event FROM tasks WHERE task=?',(tid,)).fetchone()
            if row is not None:need(list(row[:3])==refs,'task registry mismatch');c.execute('COMMIT');return row[3]
            event=sql_append(c,self.stream,'REGISTER',{'task':tid,'commitment_ref':refs[0],'artifact_ref':refs[1],'input_ref':refs[2]})
            c.execute('INSERT INTO tasks VALUES(?,?,?,?,?)',(tid,*refs,event));c.execute('COMMIT');return event
        except BaseException:
            if c.in_transaction:c.execute('ROLLBACK')
            raise
        finally:c.close()
    def issue(self,commitment,provider,unit,env,epoch,start,end):
        need(provider in self.providers,'unenrolled provider');tup,td=execution_tuple(commitment,provider,unit,env)
        body=validate_grant({'schema_id':'aclt.exp.execution-grant@1','authority_id':self.authority_id,'grant_nonce':secrets.token_bytes(16),
               **{k:tup[k] for k in ['experimental_task_id','provider_ref','unit_ref','environment_digest','scope_digest']},'execution_tuple_digest':td,'epoch':epoch,'not_before':start,'expires_at':end})
        packet=sign(body,self.private);gid=grant_id(body);c=self.connect()
        try:
            c.execute('BEGIN IMMEDIATE');task=c.execute('SELECT event FROM tasks WHERE task=?',(body['experimental_task_id'],)).fetchone();need(task is not None,'unregistered task')
            old=c.execute('SELECT epoch,consume_event FROM grants WHERE task=? AND unit=?',(body['experimental_task_id'],unit)).fetchone()
            if old is not None:
                need(old[1] is None and epoch>old[0],'consumed slot or non-increasing epoch');c.execute('DELETE FROM grants WHERE task=? AND unit=?',(body['experimental_task_id'],unit))
            pref=sql_put(c,packet);event=sql_append(c,self.stream,'ISSUE',{'grant_ref':pref,'task':body['experimental_task_id']},[task[0]])
            c.execute('INSERT INTO grants VALUES(?,?,?,?,?,?,?,NULL)',(body['experimental_task_id'],unit,epoch,encode(body),packet,gid,event));c.execute('COMMIT')
            return encode({'grant':packet,'issue_event':event,'register_event':task[0]})
        except BaseException:
            if c.in_transaction:c.execute('ROLLBACK')
            raise
        finally:c.close()
    def checked_prefix(self,c,pack,body,issue,consume=None,complete=False):
        head=snapshot_check(pack);events=[decode(raw) for raw in pack['events']]
        kinds=['DISPATCH_REQUEST','DISPATCH_CHECKED','INTENT']
        if complete:kinds+=['PERMIT','INVOKE','OUTCOME']
        need([e['kind'] for e in events] in ([kinds] if complete else [['DISPATCH_REQUEST'],kinds]),'worker prefix phases')
        need(pack['stream']==stream_id('worker',self.authority_id,body['experimental_task_id'],body['unit_ref']),'worker prefix stream')
        def value(event):return decode(pack['objects'][event['payload_ref'].hex()])
        first=value(events[0]);required={'task','grant_id','execution_tuple_digest','commitment_ref','artifact_ref','input_ref','delivery_ref'}
        need(set(first)==required and first['task']==body['experimental_task_id'] and first['grant_id']==grant_id(body) and first['execution_tuple_digest']==body['execution_tuple_digest'],'worker dispatch binding')
        row=c.execute('SELECT commit_ref,artifact_ref,input_ref,event FROM tasks WHERE task=?',(body['experimental_task_id'],)).fetchone()
        need([first[n] for n in ['commitment_ref','artifact_ref','input_ref']]==list(row[:3]) and issue in events[0]['parents'],'worker task object references')
        delivery=decode(pack['objects'][first['delivery_ref'].hex()]);need(delivery['issue_event']==issue and delivery['register_event']==row[3] and verify(delivery['grant'],self.public,self.public_digest)==body,'worker delivery binding')
        for index,op,eventref in [(1,'CHECK',None),(3,'CONSUME',consume)]:
            if len(events)<=index:continue
            event=events[index];v=value(event);need(set(v)=={'request_ref','response_ref'},'worker permission fields')
            reqraw=pack['objects'][v['request_ref'].hex()];req=decode(decode(reqraw)['payload']);reply=verify(pack['objects'][v['response_ref'].hex()],self.public,self.public_digest)
            need(reply['schema_id']=='aclt.exp.causal-response@1' and reply['authority_id']==self.authority_id and reply['op']==op and reply['status']=='ALLOW' and reply['grant_id']==grant_id(body) and reply['request_digest']==sha(reqraw) and reply['nonce']==req['nonce'],'worker signed permission binding')
            need(reply['event_ref'] in event['parents'] and (eventref is None or eventref==reply['event_ref']),'worker permission parent')
            erow=c.execute('SELECT data FROM journal WHERE digest=?',(reply['event_ref'],)).fetchone();need(erow is not None,'unknown authority permission event')
            aevent=decode(erow[0]);apayload=decode(c.execute('SELECT data FROM objects WHERE digest=?',(aevent['payload_ref'],)).fetchone()[0]);need(aevent['kind']==op and apayload['status']=='ALLOW' and apayload['request_ref']==sha(reqraw),'authority permission decision')
        if len(events)>=3:need(value(events[2])=={'task':body['experimental_task_id'],'grant_id':grant_id(body),'execution_tuple_digest':body['execution_tuple_digest']},'intent binding')
        if complete:need(value(events[4])=={'grant_id':grant_id(body)},'invocation binding')
        return head

    def handle(self,packet):
        wrapper=decode(packet);need(type(wrapper) is dict and set(wrapper)=={'payload','mac'},'request wrapper')
        need(type(wrapper['payload']) is bytes and type(wrapper['mac']) is bytes,'request types');req=decode(wrapper['payload'])
        fields={'schema_id','authority_id','provider_ref','grant_id','nonce','op','data'}
        need(type(req) is dict and set(req)==fields and req['schema_id']=='aclt.exp.causal-request@1','request fields')
        for k in ['provider_ref','grant_id']:b32(req[k])
        need(type(req['nonce']) is bytes and len(req['nonce'])==16 and req['op'] in ['CHECK','CONSUME','SUBMIT'],'request nonce/op')
        secret=self.providers.get(req['provider_ref']);need(secret is not None and hmac.compare_digest(wrapper['mac'],hmac.digest(secret,wrapper['payload'],'sha256')) and req['authority_id']==self.authority_id,'request authentication')
        c=self.connect()
        try:
            c.execute('BEGIN IMMEDIATE');request_ref=sql_put(c,packet)
            row=c.execute('SELECT body,issue_event,consume_event,task FROM grants WHERE gid=?',(req['grant_id'],)).fetchone()
            status='DENY';reason='UNKNOWN_GRANT';receipt=b'';parents=[]
            if req['op'] in ['CHECK','CONSUME']:
                kind=req['op'];allowed=False
                try:
                    need(row is not None,'unknown/stale grant');body=decode(row[0]);now=int(self.clock())
                    need(body['provider_ref']==req['provider_ref'] and body['not_before']<=now<body['expires_at'] and row[2] is None,'inactive grant')
                    pack=req['data'];head=self.checked_prefix(c,pack,body,row[1]);last=decode(pack['events'][-1]);payload=decode(pack['objects'][last['payload_ref'].hex()])
                    need(pack['stream']==stream_id('worker',self.authority_id,body['experimental_task_id'],body['unit_ref']),'worker stream binding')
                    need(len(pack['events'])==(1 if kind=='CHECK' else 3),'authorization worker prefix length')
                    need([decode(r)['kind'] for r in pack['events']]==(['DISPATCH_REQUEST'] if kind=='CHECK' else ['DISPATCH_REQUEST','DISPATCH_CHECKED','INTENT']),'authorization worker prefix phases')
                    need(last['kind']==('DISPATCH_REQUEST' if kind=='CHECK' else 'INTENT') and payload['grant_id']==req['grant_id'],'authorization causal parent')
                    need(payload['execution_tuple_digest']==body['execution_tuple_digest'],'authorization tuple')
                    parents=[row[1],head];allowed=True;reason='ACTIVE';status='ALLOW'
                except Rejected as exc:reason=str(exc)
                event=sql_append(c,self.stream,kind,{'request_ref':request_ref,'grant_id':req['grant_id'],'status':status,'reason':reason,'time':int(self.clock())},parents)
                if allowed and kind=='CONSUME':c.execute('UPDATE grants SET consume_event=? WHERE gid=?',(event,req['grant_id']))
            else:
                kind='SUBMIT_REJECTED';reason='INVALID_SUBMISSION'
                try:
                    need(row is not None and row[2] is not None,'no consumed grant')
                    body=decode(row[0]);need(body['provider_ref']==req['provider_ref'],'submission provider')
                    raw=req['data']['submission'];prepared=req['data']['prepared_event'];prepared_payload=req['data']['prepared_payload']
                    need(type(raw) is bytes,'submission bytes');digest=sha(raw)
                    se=decode(req['data']['send_event']);sp=decode(req['data']['send_payload'])
                    need(se['kind']=='SEND' and se['payload_ref']==sha(req['data']['send_payload']) and sp=={'submission_digest':digest,'attempt_nonce':req['nonce']},'send event binding')
                    send_ref=event_id(req['data']['send_event'])
                    accepted=c.execute('SELECT submission,receipt,event FROM accepted WHERE gid=?',(req['grant_id'],)).fetchone()
                    if accepted is not None:
                        # Replay never reexecutes guest or revalidates math; stable original receipt.
                        if digest==accepted[0]:kind='SUBMIT_DUPLICATE';status='DUPLICATE';receipt=accepted[1];reason='SAME_IMMUTABLE_PACKET'
                        else:kind='SUBMIT_CONFLICT';status='CONFLICT';reason='DIFFERENT_PACKET'
                        parents=[accepted[2],send_ref] if kind=='SUBMIT_DUPLICATE' else [accepted[2]]
                    else:
                        sub=decode(raw);need(type(sub) is dict and set(sub)=={'body','worker'},'submission package')
                        sb=decode(sub['body']);required={'schema_id','authority_id','grant_id','task','unit','provider','tuple','outcome_ref','output_ref','worker_head','submission_nonce'}
                        need(set(sb)==required and sb['schema_id']=='aclt.exp.submission@1','submission body fields')
                        need(sb['authority_id']==self.authority_id and sb['grant_id']==req['grant_id'] and sb['task']==body['experimental_task_id'] and sb['unit']==body['unit_ref'] and sb['provider']==req['provider_ref'] and sb['tuple']==body['execution_tuple_digest'],'submission tuple binding')
                        need(type(sb['submission_nonce']) is bytes and len(sb['submission_nonce'])==16,'submission nonce')
                        head=self.checked_prefix(c,sub['worker'],body,row[1],row[2],complete=True);need(head==sb['worker_head'],'submission worker head')
                        need(sub['worker']['stream']==stream_id('worker',self.authority_id,sb['task'],sb['unit']),'submission stream')
                        last=decode(sub['worker']['events'][-1]);need(last['kind']=='OUTCOME','submission must end at complete outcome')
                        outcome_payload=decode(sub['worker']['objects'][last['payload_ref'].hex()]);need(outcome_payload['outcome_ref']==sb['outcome_ref'] and outcome_payload['output_ref']==sb['output_ref'],'submission outcome reference')
                        outcome=decode(sub['worker']['objects'][sb['outcome_ref'].hex()]);output=sub['worker']['objects'][sb['output_ref'].hex()] if sb['output_ref']!=ZERO else None
                        validate_outcome(outcome,output,body)
                        tref=c.execute('SELECT commit_ref FROM tasks WHERE task=?',(body['experimental_task_id'],)).fetchone()[0]
                        limits=load(c.execute('SELECT data FROM objects WHERE digest=?',(tref,)).fetchone()[0])['execution_limits']
                        need(outcome['result']['gas_used']<=limits['gas_limit'] and (output is None or len(output)<=limits['output_limit']),'outcome resource binding')
                        pe=decode(prepared);need(set(pe)=={'schema_id','stream','seq','prev','kind','payload_ref','parents'} and pe['schema_id']=='aclt.exp.causal-event@1' and pe['parents']==[],'prepared event schema')
                        need(pe['kind']=='PREPARED' and pe['prev']==head and pe['seq']==len(sub['worker']['events'])+1 and pe['stream']==sub['worker']['stream'] and pe['payload_ref']==sha(prepared_payload),'prepared event prefix')
                        need(decode(prepared_payload)=={'submission_digest':digest,'body_digest':sha(sub['body'])},'prepared payload binding')
                        # Store exact package and pre-signed receipt in the same acceptance transaction.
                        sql_put(c,raw);rbody={'schema_id':'aclt.exp.acceptance-receipt@1','authority_id':self.authority_id,'task':sb['task'],'unit':sb['unit'],'grant_id':req['grant_id'],'execution_tuple_digest':sb['tuple'],'submission_digest':digest,'outcome_digest':outcome['outcome_digest']}
                        receipt=sign(rbody,self.private);rref=sql_put(c,receipt);kind='ACCEPT';status='ACCEPTED';reason='BOUND_EVIDENCE_ACCEPTED';parents=[row[2],event_id(prepared),send_ref]
                except (Rejected,KeyError,TypeError,IndexError) as exc:
                    status='REJECTED';reason=type(exc).__name__+': '+str(exc)
                payload={'request_ref':request_ref,'grant_id':req['grant_id'],'status':status,'reason':reason,'receipt_ref':sql_put(c,receipt) if receipt else ZERO}
                event=sql_append(c,self.stream,kind,payload,parents)
                if kind=='ACCEPT':c.execute('INSERT INTO accepted VALUES(?,?,?,?)',(req['grant_id'],digest,receipt,event))
            c.execute('COMMIT')
        except BaseException:
            if c.in_transaction:c.execute('ROLLBACK')
            raise
        finally:c.close()
        # Lost response after durable ACCEPT is recovered by identical-packet replay.
        return sign({'schema_id':'aclt.exp.causal-response@1','authority_id':self.authority_id,'request_digest':sha(packet),
                     'op':req['op'],'grant_id':req['grant_id'],'nonce':req['nonce'],'status':status,'reason':reason,'event_ref':event,'receipt':receipt},self.private)
    def export(self):
        with closing(self.connect()) as c:
            c.execute('BEGIN');events=[r[0] for r in c.execute('SELECT data FROM journal ORDER BY seq')];objects={r[0].hex():r[1] for r in c.execute('SELECT digest,data FROM objects')};projection=self.projection(c)
            head=event_id(events[-1]) if events else ZERO
            anchor=sign({'schema_id':'aclt.exp.journal-checkpoint@1','authority_id':self.authority_id,'stream':self.stream,'count':len(events),'head':head,'projection_digest':sha(encode(projection))},self.private);c.execute('COMMIT')
        return {'schema_id':'aclt.exp.authority-export@1','authority_id':self.authority_id,'stream':self.stream,'events':events,'objects':objects,'projection':projection},anchor
    def projection(self,c):
        return {'tasks':sorted(r[0].hex() for r in c.execute('SELECT task FROM tasks')),
                'slots':{r[0].hex():{'task':r[1].hex(),'unit':r[2].hex(),'epoch':r[3],'consumed':r[4].hex() if r[4] else '', 'accepted':r[5].hex() if r[5] else ''} for r in c.execute('SELECT g.gid,g.task,g.unit,g.epoch,g.consume_event,a.submission FROM grants g LEFT JOIN accepted a ON a.gid=g.gid')}}

def validate_outcome(outcome,output,body):
    need(type(outcome) is dict and set(outcome)=={'result','outcome_digest','grant_id','tuple'},'outcome record fields')
    need(outcome['grant_id']==grant_id(body) and outcome['tuple']==body['execution_tuple_digest'],'outcome tuple')
    result=outcome['result'];need(type(result) is dict and type(result.get('gas_used')) is int and result['gas_used']>=8192,'outcome gas')
    need(result.get('outcome') in ['OK','ABORT','TRAP_GAS_EXHAUSTED','TRAP_OUTPUT_LIMIT','TRAP_CALL_DEPTH','TRAP_UNREACHABLE','TRAP_MEMORY_OOB','TRAP_HOST_ARGUMENT','TRAP_INTEGER_DIVIDE_BY_ZERO','TRAP_INTEGER_OVERFLOW'],'outcome kind')
    fields={'outcome','gas_used'}|({'output'} if result['outcome']=='OK' else {'abort_code'} if result['outcome']=='ABORT' else set())
    need(set(result)==fields,'outcome fields/output discard')
    if result['outcome']=='ABORT':need(type(result['abort_code']) is int and 0<=result['abort_code']<2**32,'abort code width')
    if result['outcome']=='OK':need(type(output) is bytes and result['output']==sha(output),'output attachment binding')
    else:need(output is None,'non-OK output forbidden')
    canonical=dict(result)
    if result['outcome']=='OK':canonical['output']=output
    # Original RIR digest domain/canonical rules, with raw output restored.
    from rir_adapter import modules
    wasm,_=modules();tag=b'ACLt/RIR-0/ExecutionOutcome/1'
    need(sha(bytes([len(tag)])+tag+wasm.cbor(canonical))==outcome['outcome_digest'],'RIR outcome digest mismatch')
