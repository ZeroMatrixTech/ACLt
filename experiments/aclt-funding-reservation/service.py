# SPDX-License-Identifier: Apache-2.0
"""Opt-in plaintext LAN test-asset reservation service; no initialization endpoint."""
import argparse
import socketserver
from wire import *
from ledger import Ledger


class Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = False


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(10)
        try:
            packet = receive(self.request)
            send(self.request, self.server.ledger.handle(packet))
        except Exception:
            try: send(self.request, encode({'error': 'EXPERIMENT_FUNDING_FAILURE'}))
            except Exception: pass


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for n in ['database', 'private', 'public', 'enrollment', 'ready']: p.add_argument('--'+n, type=Path, required=True)
    p.add_argument('--host', required=True); a = p.parse_args()
    enrollment = {bytes.fromhex(k): bytes.fromhex(v) for k, v in json.loads(regular(a.enrollment)).items()}
    ledger = Ledger(a.database, a.private, a.public, enrollment)
    with Server((a.host, 0), Handler) as server:
        server.ledger = ledger
        with a.ready.open('x') as f: json.dump({'host': a.host, 'port': server.server_address[1]}, f)
        server.serve_forever()
