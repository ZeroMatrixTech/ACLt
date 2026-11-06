#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Opt-in candidate authority, no remote initialization/legacy/settlement API."""
import argparse
import json
import os
from pathlib import Path
import socketserver
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.formal_migration import s2, s3_authority
from tools.formal_migration.s2_transport import receive,send
from tools.verification_profile import codec as c
class Server(socketserver.ThreadingTCPServer):
    daemon_threads=True
    allow_reuse_address=False
class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(20)
        try:
            raw=receive(self.request);result=self.server.ledger.handle(raw)
            fault=self.server.fault
            if fault and fault.exists() and (fault.read_text().strip()=='DROP_REPLY' or (fault.read_text().strip()=='DROP_CONSUME_REPLY' and c.decode(raw)['op']=='CONSUME')):
                fault.unlink();return
            send(self.request,result)
        except (c.CodecError,ValueError,ConnectionError,OSError) as exc:
            # Unsigned errors are diagnostic only, never authority facts/permissions.
            try:send(self.request,c.encode(dict(error=str(exc))))
            except (OSError,ValueError):pass
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','private','database','ready'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--s3b',action='store_true');p.add_argument('--create',action='store_true');p.add_argument('--host',required=True);p.add_argument('--clock-file',type=Path);p.add_argument('--fault-file',type=Path);a=p.parse_args()
    cfg=c.decode(a.config.read_bytes())
    def hook(point):
        if a.fault_file and a.fault_file.exists() and a.fault_file.read_text().strip()==point:
            a.fault_file.unlink();os._exit(71 if point=='BEFORE_COMMIT' else 72)
    clock=(lambda:int(a.clock_file.read_text())) if a.clock_file else None
    if a.s3b and clock is None:p.error('--s3b requires --clock-file')
    if a.create and not a.s3b:p.error('--create is limited to S3b')
    ledger_type=s3_authority.Ledger if a.s3b else s2.Ledger
    ledger=ledger_type(a.database,cfg,a.private,clock=clock,hook=hook,create=a.create)
    with Server((a.host,0),Handler) as server:
        server.ledger=ledger;server.fault=a.fault_file
        with a.ready.open('x') as out:json.dump(dict(host=a.host,port=server.server_address[1],pid=os.getpid(),genesis=s2.h(cfg).hex()),out)
        server.serve_forever()
