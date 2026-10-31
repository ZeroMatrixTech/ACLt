#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Finite signed S2 calls or the durable single-attempt worker adapter."""
import argparse
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.formal_migration import s2,s2_worker,policy as p,s2_fixture as fixture,foundation as f
from tools.formal_migration.s2_transport import rpc
from tools.verification_profile import codec as c

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for k in ('config','bundles','private','output'):ap.add_argument('--'+k,type=Path,required=True)
    ap.add_argument('--host',required=True);ap.add_argument('--port',type=int,required=True);ap.add_argument('--index',type=int,default=0);ap.add_argument('--role',choices=['REQUESTER',*s2.ROLES],required=True);ap.add_argument('--op',required=True)
    ap.add_argument('--now',type=int,default=3000);ap.add_argument('--epoch',type=int,default=1);ap.add_argument('--reuse',type=Path);ap.add_argument('--runtime',type=Path);ap.add_argument('--directory',type=Path);ap.add_argument('--crash-hook');ap.add_argument('--bad-capability',action='store_true');ap.add_argument('--bad-signature',action='store_true');a=ap.parse_args()
    a.output.mkdir(mode=0o700);cfg=c.decode(a.config.read_bytes());bundles=c.decode(a.bundles.read_bytes());b=bundles[a.index];rid=p.bundle(b)
    if a.op=='WORK':
        def hook(point):
            if point==a.crash_hook:os._exit(73)
        result=s2_worker.run(cfg,b,a.role,a.private,a.host,a.port,a.runtime,a.directory,a.now,hook)
        (a.output/'result.cbor').write_bytes(c.encode(result));print(json.dumps(dict(status=result['status'])));return
    actor=f.principal_digest(cfg['requester'] if a.role=='REQUESTER' else cfg['providers'][a.role])
    prop=s2.proposal(cfg,rid,a.role,b) if a.role in s2.ROLES else None
    body=dict(receipt=rid)
    if a.op=='CREATE':body=dict(bundle=b,receipt_signature=fixture.receipt_sign(a.private,b))
    elif a.op in ('ACTIVATE','CONSUME'):
        body.update(assignment=prop['assignment'],epoch=a.epoch)
        if a.op=='CONSUME':body.update(capability=b'z'*32 if a.bad_capability else s2.capability(cfg,prop),intent=os.urandom(32))
    req=c.decode(a.reuse.read_bytes()) if a.reuse else s2.request(cfg,a.private,actor,a.op,body,a.now)
    if a.bad_signature:req['signature']=b'\0'*256
    (a.output/'request.cbor').write_bytes(c.encode(req))
    try:
        raw=rpc(a.host,a.port,c.encode(req));(a.output/'response.cbor').write_bytes(raw);q=s2.check_response(cfg,req,raw)
        (a.output/'result.cbor').write_bytes(c.encode(q));print(json.dumps(dict(status='ACCEPTED',checkpoint=q['checkpoint']['head'].hex(),seq=q['checkpoint']['seq'])))
    except (OSError,ConnectionError,ValueError) as exc:
        # Rejection/transport failure is NOT an authenticated negative business fact.
        print(json.dumps(dict(status='NO_AUTHENTICATED_RESULT',reason=str(exc))));sys.exit(2)
if __name__=='__main__':main()
