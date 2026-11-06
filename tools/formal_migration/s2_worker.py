# SPDX-License-Identifier: Apache-2.0
"""Honest pinned-host test adapter, NOT a complete sandbox/RPR.

Durable intent precedes authoritative consume. A restart never re-invokes guest,
even if the first process died before invocation. UNKNOWN is retained for FM-S3.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
from tools.formal_migration import s2,policy as p,s3_authority,s3_results
from tools.formal_migration.s2_transport import rpc
from tools.verification_profile import codec as c

def durable(path,raw):
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb') as out:out.write(raw);out.flush();os.fsync(out.fileno())
    finally:
        directory=os.open(Path(path).parent,os.O_DIRECTORY)
        try:os.fsync(directory)
        finally:os.close(directory)

def run(cfg,bundle,role,private,host,port,exe,directory,now,hook=None,*,s3b=False):
    s2.config_check(cfg);c.need(role in s2.ROLES,'worker role');hook=hook or (lambda _:None)
    rid=p.bundle(bundle);c.need(rid in cfg['allowed_receipts'],'worker receipt pin')
    prop=s2.proposal(cfg,rid,role,bundle);actor=prop['provider'];directory=Path(directory);directory.mkdir(mode=0o700,exist_ok=True)
    c.need(not directory.is_symlink(),'worker directory symlink')
    lock=os.open(directory/'lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        binding=c.encode([s2.h(cfg),rid,role,actor]);identity=directory/'binding'
        if identity.exists():c.need(identity.read_bytes()==binding,'worker directory rebound')
        else:durable(identity,binding)
        if (directory/'intent').exists():
            if (directory/'observation').exists():return c.decode((directory/'observation').read_bytes())
            return dict(status='UNKNOWN_NO_REEXECUTION')
        c.need(hashlib.sha256(Path(exe).read_bytes()).digest()==cfg['runtime_sha256'],'runtime binary pin')
        c.need(bundle['components'][0]['content']==cfg['artifact'],'worker artifact pin')
        query=s2.request(cfg,private,actor,'QUERY',dict(receipt=rid),now)
        q=s2.check_response(cfg,query,rpc(host,port,c.encode(query)))
        lease=q['result']['task']['leases'][role]
        c.need(lease['state']=='ACTIVE' and lease['proposal']==prop and lease['capability']==s2.capability(cfg,prop),'dispatch current lease')
        intent=s2.h([binding,os.urandom(32)])
        durable(directory/'intent',c.encode(dict(binding=binding,intent=intent,dispatch_checkpoint=q['checkpoint'])))
        hook('AFTER_INTENT')
        body=dict(receipt=rid,assignment=prop['assignment'],epoch=1,capability=lease['capability'],intent=intent)
        req=s2.request(cfg,private,actor,'CONSUME',body,now)
        # An unknown transport result never authorizes a guest call or an auto-retry.
        try:reply=s2.check_response(cfg,req,rpc(host,port,c.encode(req)),q['checkpoint'])
        except (OSError,ConnectionError,ValueError):return dict(status='UNKNOWN_NO_REEXECUTION')
        c.need(reply['result']['state']=='CONSUMED' and reply['result']['intent']==intent and reply['result']['proposal']==prop,'RPR consume gate')
        durable(directory/'consume',c.encode(reply));hook('AFTER_CONSUME')
        values=c.decode(bundle['inputs'][0]['content']);inp=struct.pack('<QQ',2,len(values))+b''.join(struct.pack('<q',x) for x in values)
        durable(directory/'input',inp);durable(directory/'artifact',cfg['artifact'])
        if s3b:
            s3_authority.check_bundle(bundle)
            start_body = dict(receipt=rid, profile=s3_authority.profile_ref(), role=role,
                              assignment=prop['assignment'], epoch=1, intent=intent,
                              consume_event=s3_results.consumed_event(reply, prop['assignment'], intent))
            start_req = s2.request(cfg,private,actor,'S3_START',start_body,now)
            try:
                entry = s2.check_response(cfg,start_req,rpc(host,port,c.encode(start_req)),reply['checkpoint'])
            except (OSError,ConnectionError,ValueError):
                return dict(status='UNKNOWN_NO_REEXECUTION')
            durable(directory/'s3-start',c.encode(dict(start_body,start=entry['result']['start'])))
        durable(directory/'invocation',c.encode(dict(intent=intent)));hook('BEFORE_GUEST')
        e=bundle['receipt']['execution']
        args=[str(Path(exe).resolve()),'--artifact',str(directory/'artifact'),str(directory/'input'),str(e['fuel']),str(e['output_bytes_limit']),'8','20000000',str(e['memory_bytes']//65536),prop['rir_digest'].hex()]
        try:
            result=subprocess.run(args,capture_output=True,timeout=30)
            obj=json.loads(result.stdout)
            c.need((obj['status'],result.returncode) in [('TASK_OUTCOME',0),('REJECTED',2),('HOST_FAULT',3)],'core exit mismatch')
            if obj['status']!='TASK_OUTCOME':c.need('outcome_digest' not in obj and 'canonical_outcome_hex' not in obj,'host fault is not task outcome')
            observation=dict(status='LOCAL_OBSERVATION_ONLY',intent=intent,core=c.encode(obj),returncode=result.returncode)
        except (OSError,subprocess.TimeoutExpired,ValueError,KeyError):observation=dict(status='HOST_FAULT_NO_TASK_OUTCOME',intent=intent)
        hook('AFTER_GUEST');durable(directory/'observation',c.encode(observation));return observation
    finally:os.close(lock)


def s3_result_body(directory):
    directory = Path(directory)
    binding = c.decode((directory/'s3-start').read_bytes())
    observation = c.decode((directory/'observation').read_bytes())
    c.need(observation['intent'] == binding['intent'], 'S3b local intent mismatch')
    core = c.decode(observation['core'])
    c.need(core['status'] == 'TASK_OUTCOME' and core['result']['outcome'] == 'OK',
           'S3b result adapter requires a completed OK outcome')
    return dict(binding, outcome=bytes.fromhex(core['canonical_outcome_hex']))
