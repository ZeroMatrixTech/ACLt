# SPDX-License-Identifier: Apache-2.0
"""A new replay experiment; prior commitment/authorization implementations stay unchanged."""
from pathlib import Path
import sys
import hashlib
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
AUTH=HERE.parent/'aclt-task-authorization'
if str(AUTH) not in sys.path:sys.path.insert(0,str(AUTH))
import common as base
from auth_crypto import sign,create_keys
from auth_crypto import verify as _verify
from authorization import validate_grant as _validate_grant,grant_id
from durability import durable_new,state_directory,sync_directory
from codec import encode,decode,need,Rejected
HostFault=base.HostFault
sha=lambda data:hashlib.sha256(data).digest()
ZERO=bytes(32)

def tagged(tag,data):
    raw=tag.encode('ascii');return sha(bytes([len(raw)])+raw+data)

def translated(fn,*args,**kw):
    try:return fn(*args,**kw)
    except base.Rejected as exc:raise Rejected(str(exc)) from exc

def bind(*a,**kw):return translated(base.bind,*a,**kw)
def load(*a):return translated(base.load,*a)
def task_id(*a):return translated(base.task_id,*a)
def profile():return translated(base.profile)
def verify(*a):return translated(_verify,*a)
def validate_grant(*a):return translated(_validate_grant,*a)
def regular(path):return base.regular(path)
def config(path):return translated(base.decode_config,path)
def execution_tuple(*a):return translated(base.execution_tuple,*a)
def recorded_fields_match(actual,expected,digest_fields):
    return (type(actual) is dict and set(actual)==set(expected)
            and all(actual[k]==v for k,v in expected.items() if k not in digest_fields))

def b32(value):need(type(value) is bytes and len(value)==32,'32-byte reference required')

def environment_digest():
    sources={p.name:sha(regular(p)) for p in sorted(HERE.glob('*.py'))}
    return tagged('ACLt/Experiment/ReplayEnvironment/1',encode({'base':base.environment(),'replay_sources':sources}))

def stream_id(role,authority,task=ZERO,unit=ZERO):
    return tagged('ACLt/Experiment/CausalStream/1',encode([role,authority,task,unit]))

def event_id(raw):return tagged('ACLt/Experiment/CausalEvent/1',raw)

def event_bytes(stream,seq,prev,kind,payload_ref,parents):
    return encode({'schema_id':'aclt.exp.causal-event@1','stream':stream,'seq':seq,'prev':prev,
                   'kind':kind,'payload_ref':payload_ref,'parents':sorted(set(parents))})
