# SPDX-License-Identifier: Apache-2.0
"""Explicit experimental LAN authorization endpoint. No TLS, failover or rollback protection."""
import argparse
import json
from pathlib import Path
import socketserver
from common import encode,decode,HostFault,Rejected
from authorization import Authority
from wire import receive,send

class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address=False
    daemon_threads=True

class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(5)
        try:
            packet=receive(self.request);response=self.server.authority.handle(packet)
            # Explicit harness-only fault: drop an ALLOW reply after durable consume.
            selector=self.server.test_drop_file
            if selector is not None:
                body=decode(decode(response)['payload'])
                if body['op']=='CONSUME' and body['status']=='ALLOW' and body['grant_id'].hex() in selector.read_text().split():return
            send(self.request,response)
        except Exception:
            try:send(self.request,encode({'error':'AUTHORIZATION_ENDPOINT_FAILURE'}))
            except Exception:pass

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['database','private','public','providers','ready']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--test-drop-consume-file',type=Path);p.add_argument('--host',required=True);p.add_argument('--port',type=int,default=0);a=p.parse_args()
    providers={bytes.fromhex(k):bytes.fromhex(v) for k,v in json.loads(a.providers.read_text()).items()}
    authority=Authority(a.database,a.private,a.public,providers)
    with Server((a.host,a.port),Handler) as server:
        server.authority=authority;server.test_drop_file=a.test_drop_consume_file
        with a.ready.open('x') as f:json.dump({'host':a.host,'port':server.server_address[1],'authority_id':authority.authority_id.hex()},f)
        print('READY',flush=True);server.serve_forever()
