# SPDX-License-Identifier: Apache-2.0
"""Imports and immutable descriptors for the experimental authorization boundary."""
import hashlib
import json
from pathlib import Path
import platform
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
COMMITMENT=HERE.parent/'aclt-task-commitment'
if str(COMMITMENT) not in sys.path:sys.path.insert(0,str(COMMITMENT))
from cbor_codec import encode,decode,need,Rejected
from commitment import bind,load,task_id,profile,tagged,sha

class HostFault(RuntimeError):pass

def bytes_n(value,n,name):need(type(value) is bytes and len(value)==n,name+' bytes/type')
def regular(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file():raise HostFault('regular file required')
    return path.read_bytes()

def environment():
    profile() # pin the reference machine before describing/loading it
    files=[p for p in HERE.glob('*.py') if p.is_file()]
    return {'schema_id':'aclt.exp.worker-environment@1','hostname':platform.node(),
            'kernel':platform.release(),'machine':platform.machine(),'python':platform.python_version(),
            'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'execution_profile_digest':profile()[1],
            'wrapper_sources':{p.name:sha(regular(p)) for p in sorted(files)}}

def environment_digest():return tagged('ACLt/Experiment/WorkerEnvironment/1',encode(environment()))

def execution_tuple(commitment,provider,unit,env):
    obj=load(commitment)
    for value,name in [(provider,'provider'),(unit,'unit'),(env,'environment')]:bytes_n(value,32,name)
    scope={'schema_id':'aclt.exp.execution-scope@1','experimental_task_id':bytes.fromhex(task_id(commitment)),
           'rir_digest':obj['rir_digest'],'inputs':obj['inputs'],'execution_profile_digest':obj['execution_profile_digest'],
           'execution_limits':obj['execution_limits'],'result_equivalence':obj['result_equivalence']}
    scope_digest=tagged('ACLt/Experiment/ExecutionScope/1',encode(scope))
    tup={'schema_id':'aclt.exp.execution-tuple@1','experimental_task_id':bytes.fromhex(task_id(commitment)),
         'provider_ref':provider,'unit_ref':unit,'environment_digest':env,'scope_digest':scope_digest}
    return tup,tagged('ACLt/Experiment/ExecutionTuple/1',encode(tup))

def decode_config(path):
    obj=json.loads(regular(path))
    required={'host','port','authority_id','public_digest','provider_ref','unit_ref','environment_digest','provider_secret'}
    need(type(obj) is dict and set(obj)==required,'worker config fields')
    for name in required-{'host','port'}:
        try:obj[name]=bytes.fromhex(obj[name])
        except (ValueError,TypeError) as exc:raise Rejected('config hex') from exc
        bytes_n(obj[name],16 if name=='authority_id' else 32,name)
    need(type(obj['host']) is str and type(obj['port']) is int and 1<=obj['port']<65536,'endpoint config')
    return obj
