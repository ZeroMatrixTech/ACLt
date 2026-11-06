# SPDX-License-Identifier: Apache-2.0
"""Offline finite test genesis builder; generated private keys are not delivery inputs."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from tools.formal_migration import foundation as f,policy as p,s2
from tools.verification_profile import codec as c

def keypair(path):
    subprocess.run(['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048','-out',str(path)],capture_output=True,check=True,timeout=30);path.chmod(0o600)
    return subprocess.check_output(['openssl','pkey','-in',str(path),'-pubout','-outform','DER'])
def record(der,role,network,deployment):
    return dict(schema_version=1,encoding_profile_id=c.ENCODING,protocol_version=[0,5,0],network_id=network,deployment_id=deployment,principal_id=c.domain_hash(f.IDENTITY_TAG,der),key_id=hashlib.sha256(der).digest(),public_key_der=der,role=role,suite=f.SUITE,valid_from=1000,valid_until=10000,status='ACTIVE')
def receipt_sign(private,bundle):
    with tempfile.TemporaryDirectory() as tmp:
        file=Path(tmp)/'receipt';file.write_bytes(p.signing_input(bundle))
        return subprocess.check_output(['openssl','dgst','-sha256','-sign',str(private),'-sigopt','rsa_padding_mode:pkcs1',str(file)])
def rebind(b):
    r=b['receipt'];r['funding_ref']=p.ref('FUNDING',b['funding']);r['settlement_ref']=p.ref('SETTLEMENT',b['settlement']);r['input_refs']=[p.ref('LOGICAL',x) for x in b['inputs']];r['component_refs']=[p.ref(x['kind'],x) for x in b['components']];return b

def build(root,out,runtime_sha256,count=3,*,artifact=None):
    out=Path(out);out.mkdir(mode=0o700);network=os.urandom(32);deployment=os.urandom(32);records={}
    for name,role in [('requester','REQUESTER'),('executor','PROVIDER'),('auditor','PROVIDER')]:records[name]=record(keypair(out/(name+'.pem')),role,network,deployment)
    issuer=keypair(out/'issuer.pem');vectors=json.loads((root/'tests/formal_migration/policy-vectors.json').read_text())['vectors'];template=c.decode(bytes.fromhex(next(r['cbor_hex'] for r in vectors if r['id']=='bundle')))
    if artifact is None:
        artifact=bytes.fromhex(json.loads((root/'experiments/aclt-rir-stats-probe/tests/independent-vectors.json').read_text())['vectors'][0]['artifact_hex'])
    bundles=[]
    for i in range(count):
        b=copy.deepcopy(template)
        for x in (b['receipt'],b['funding'],b['settlement'],b['inputs'][0]):x.update(network_id=network,deployment_id=deployment)
        scope=dict(requester_ref=f.principal_digest(records['requester']),nonce=hashlib.sha256(str(i).encode()).digest(),created_at=2000,expires_at=6000)
        for x in (b['receipt'],b['funding'],b['settlement']):x['scope']=copy.deepcopy(scope)
        b['inputs'][0]['publisher_ref']=scope['requester_ref'];b['inputs'][0]['content']=c.encode([3,-2,7,i]);b['receipt']['execution'].update(fuel=50000000,memory_bytes=131072,recovery_queries=32)
        for component in b['components']:
            if component['kind']=='RIR':component['content']=artifact
            elif component['kind']=='RUNTIME':component['content']=c.encode(dict(binary_sha256=runtime_sha256,support='RIR_STATS_INDEPENDENT_CORE_1',sandbox='HONEST_PINNED_TEST_HOST_NOT_OS_SANDBOX'))
        rebind(b);p.bundle(b);bundles.append(b)
    cap=lambda n,v,a:dict(concurrency=n,value=v,attempts=a)
    cfg=dict(schema=s2.SCHEMA,network=network,deployment=deployment,requester=records['requester'],providers=dict(EXECUTOR=records['executor'],AUDITOR=records['auditor']),issuer_der=issuer,allowed_receipts=[p.bundle(b) for b in bundles],runtime_sha256=runtime_sha256,artifact=artifact,balance=68,caps=dict(provider=cap(2,14,2),cluster=cap(4,24,4),receipt=cap(2,12,2),window=cap(4,24,4),**{'global':cap(4,24,4)}),valid_from=1000,valid_until=9000,scope='TEST_ONLY_NO_OFFICIAL_ADMISSION')
    s2.config_check(cfg);(out/'config.cbor').write_bytes(c.encode(cfg));(out/'bundles.cbor').write_bytes(c.encode(bundles));return cfg,bundles
