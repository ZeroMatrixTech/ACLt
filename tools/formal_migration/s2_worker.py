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
from tools.formal_migration import s2,policy as p,s3_authority,s3_results,s3_terminals
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

def run(cfg,bundle,role,private,host,port,exe,directory,now,hook=None,*,s3b=False,closure_fault=False):
    if closure_fault:
        c.need(s3b and role == 'EXECUTOR' and
               'closure_observer_der' in s3_authority.check_bundle(bundle),
               'closure fault injection requires the dedicated executor contract')
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
            unknown=dict(status='UNKNOWN_NO_REEXECUTION')
            if s3b and s3_authority.uses(bundle,'rpr_entry'):unknown['stage']=local_stage(directory)
            return unknown
        c.need(c.digest_consistency(hashlib.sha256(Path(exe).read_bytes()).digest() == cfg['runtime_sha256']),'runtime binary pin')
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
        descriptor=None
        if s3b:
            start_body = dict(receipt=rid, profile=s3_authority.profile_ref(bundle), role=role,
                              assignment=prop['assignment'], epoch=1, intent=intent,
                              consume_event=s3_results.consumed_event(reply, prop['assignment'], intent))
            start_op = 'S3_START'
            if s3_authority.uses(bundle, 'rpr_entry'):
                descriptor = s3_terminals.entry_descriptor(cfg, bundle, rid, role)
                c.need(c.digest_consistency(hashlib.sha256(inp).digest() == descriptor['input_sha256']), 'RPR entry input pin')
                c.need(c.digest_consistency(c.domain_hash('ACLt/RIR-0/Artifact/1',cfg['artifact']) == descriptor['rir_digest']),
                       'RPR entry artifact pin')
                start_body['entry'] = descriptor
                start_op = 'S3_ENTRY'
            start_req = s2.request(cfg,private,actor,start_op,start_body,now)
            try:
                entry = s2.check_response(cfg,start_req,rpc(host,port,c.encode(start_req)),reply['checkpoint'])
            except (OSError,ConnectionError,ValueError):
                return dict(status='UNKNOWN_NO_REEXECUTION')
            durable(directory/'s3-start',c.encode(dict(start_body,start=entry['result']['start'])))
        durable(directory/'invocation',c.encode(dict(intent=intent)));hook('BEFORE_GUEST')
        e=bundle['receipt']['execution']
        args=[str(Path(exe).resolve()),'--artifact',str(directory/'artifact'),str(directory/'input'),str(e['fuel']),str(e['output_bytes_limit']),'8','20000000',str(e['memory_bytes']//65536),prop['rir_digest'].hex()]
        if descriptor is not None:args=s3_terminals.invocation_args(descriptor,Path(exe).resolve(),directory/'artifact',directory/'input')
        if closure_fault:
            args.append('test-memory-fault')
        try:
            result=subprocess.run(args,capture_output=True,timeout=30)
            obj=json.loads(result.stdout)
            c.need((obj['status'],result.returncode) in [('TASK_OUTCOME',0),('REJECTED',2),('HOST_FAULT',3)],'core exit mismatch')
            if obj['status']!='TASK_OUTCOME':c.need('outcome_digest' not in obj and 'canonical_outcome_hex' not in obj,'host fault is not task outcome')
            observation=dict(status='LOCAL_OBSERVATION_ONLY',intent=intent,core=c.encode(obj),returncode=result.returncode)
        except (OSError,subprocess.TimeoutExpired,ValueError,KeyError):observation=dict(status='HOST_FAULT_NO_TASK_OUTCOME',intent=intent)
        hook('AFTER_GUEST')
        durable(directory/'observation',c.encode(observation))
        hook('AFTER_OBSERVATION')
        return observation
    finally:os.close(lock)


def local_stage(directory):
    """Worker-local evidence only; the authority projection decides start state."""
    directory = Path(directory)
    for name, stage in (('invocation', 'INVOCATION_RECORDED'), ('s3-start', 'EXECUTION_STARTED'),
                        ('consume', 'AUTHORIZATION_CONSUMED')):
        if (directory/name).exists():
            return stage
    return 'INTENT_ONLY'


def s3_binding(directory):
    """Role binding and start reference without the entry descriptor."""
    binding = c.decode((Path(directory)/'s3-start').read_bytes())
    binding.pop('entry', None)
    return binding


def s3_hostfault_body(directory, reason):
    """Authenticated self-report that the recorded entry produced no task outcome."""
    c.need(reason in ('IO', 'RESOURCE', 'INTERRUPTED'), 'S3 host fault reason')
    directory = Path(directory)
    observation = directory/'observation'
    if observation.exists():
        value = c.decode(observation.read_bytes())
        c.need(value['status'] != 'LOCAL_OBSERVATION_ONLY' or c.decode(value['core'])['status'] != 'TASK_OUTCOME',
               'a completed task outcome must be submitted as a result')
    return dict(s3_binding(directory), reason=reason)


def s3_result_body(directory):
    directory = Path(directory)
    binding = s3_binding(directory)
    observation = c.decode((directory/'observation').read_bytes())
    c.need(observation['intent'] == binding['intent'], 'S3b local intent mismatch')
    core = c.decode(observation['core'])
    c.need(core['status'] == 'TASK_OUTCOME', 'S3b result adapter requires a completed task outcome')
    raw = bytes.fromhex(core['canonical_outcome_hex'])
    c.need(c.digest_consistency(c.domain_hash('ACLt/RIR-0/ExecutionOutcome/1',raw).hex() == core['outcome_digest']),
           'S3b runtime outcome digest mismatch')
    return dict(binding, outcome=raw)
