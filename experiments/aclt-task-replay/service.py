# SPDX-License-Identifier: Apache-2.0
"""Experimental journal/acceptance LAN service; private keys stay on A."""
import argparse,json,socketserver
from context import *
from ledger import Ledger
from network import receive,send

class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address=False
    daemon_threads=True
class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(10)
        try:
            packet=receive(self.request);reply=self.server.ledger.handle(packet)
            # Test-only reply loss after COMMIT, never an authorization bypass.
            if self.server.drop_file is not None:
                body=decode(decode(reply)['payload']);key=body['op']+' '+body['grant_id'].hex()
                if body['status'] in ['ALLOW','ACCEPTED'] and key in self.server.drop_file.read_text().splitlines():return
            send(self.request,reply)
        except Exception:
            try:send(self.request,encode({'error':'EXPERIMENT_ENDPOINT_FAILURE'}))
            except Exception:pass
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['database','private','public','providers','ready']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--host',required=True);p.add_argument('--test-drop-file',type=Path);a=p.parse_args()
    providers={bytes.fromhex(k):bytes.fromhex(v) for k,v in json.loads(a.providers.read_text()).items()};ledger=Ledger(a.database,a.private,a.public,providers)
    with Server((a.host,0),Handler) as server:
        server.ledger=ledger;server.drop_file=a.test_drop_file
        with a.ready.open('x') as f:json.dump({'host':a.host,'port':server.server_address[1],'authority_id':ledger.authority_id.hex()},f)
        print('READY',flush=True);server.serve_forever()
