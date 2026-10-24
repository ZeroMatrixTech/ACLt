# SPDX-License-Identifier: Apache-2.0
"""Recovery LAN service; normal operation has no test control or fault callback."""
import argparse
import socketserver
from context import *
from recovery import RecoveryLedger
from fault_driver import FaultGate,DropReply


class Server(socketserver.ThreadingTCPServer):
    daemon_threads=True
    allow_reuse_address=False


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(10)
        try: send(self.request,self.server.ledger.handle(receive(self.request)))
        except DropReply: return  # close the real TCP stream without a response
        except Exception:
            try: send(self.request,encode({'error':'EXPERIMENT_RECOVERY_FAILURE'}))
            except Exception: pass


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['database','private','public','enrollment','ready']: p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--host',required=True); p.add_argument('--test-control',type=Path); a=p.parse_args()
    enrollment={bytes.fromhex(k):bytes.fromhex(v) for k,v in json.loads(regular(a.enrollment)).items()}
    ledger=RecoveryLedger(a.database,a.private,a.public,enrollment,test_hook=FaultGate(a.test_control) if a.test_control else None)
    with Server((a.host,0),Handler) as server:
        server.ledger=ledger
        with a.ready.open('x') as f: json.dump({'host':a.host,'port':server.server_address[1]},f)
        server.serve_forever()
