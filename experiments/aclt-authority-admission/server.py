# SPDX-License-Identifier: Apache-2.0
"""Bounded framed test transport; admin port is test-only and separately enabled."""
import argparse
import http.server
import json
import socketserver
import threading
import time
from pathlib import Path
from authority import Authority
from gateway import Gateway
from protocol import MAX_FRAME, canonical


class TCP(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def server(service, host, port):
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.connection.settimeout(10)
            try:
                raw = self.rfile.readline(MAX_FRAME + 1)
                if len(raw) > MAX_FRAME or not raw.endswith(b'\n'):
                    return
                reply = service.handle(json.loads(raw))
                if getattr(service, 'drop_next', False):
                    service.drop_next = False
                    return
                self.wfile.write(canonical(reply) + b'\n')
            except Exception as exc:
                self.wfile.write(canonical({'error': type(exc).__name__}) + b'\n')
    return TCP((host, port), Handler)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('role', choices=['authority', 'gateway'])
    p.add_argument('--config', required=True)
    p.add_argument('--port', type=int, default=9000)
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--initialize', action='store_true')
    p.add_argument('--test-admin-port', type=int)
    args = p.parse_args()
    config = json.loads(Path(args.config).read_text())
    if args.role == 'authority':
        service = Authority(config['manifest'], config['database'], config['private_key'],
                            config['public_key'], initialize=args.initialize)
    else:
        if args.initialize:
            p.error('gateway has no ledger to initialize')
        service = Gateway(config['host'], config['port'], timeout=config.get('timeout', 5))
    if args.test_admin_port:
        # Explicit test mode. Never start this endpoint on a public deployment.
        service.pause_stage = None
        def hook(stage):
            print('TX_STAGE ' + stage, flush=True)
            if service.pause_stage == stage:
                print('CHECKPOINT ' + stage, flush=True)
                time.sleep(60)
                raise TimeoutError('test checkpoint expired')
        service.hook = hook
        class Admin(http.server.BaseHTTPRequestHandler):
            def log_message(self, *unused):
                pass
            def do_POST(self):
                try:
                    n = int(self.headers['Content-Length'])
                    if not 0 < n <= 4096:
                        raise ValueError('admin frame')
                    obj = json.loads(self.rfile.read(n))
                    if obj['action'] == 'pause':
                        service.pause_stage = obj['stage']
                    elif obj['action'] == 'drop':
                        service.drop_next = True
                    elif obj['action'] == 'health':
                        pass
                    else:
                        raise ValueError('unknown admin action')
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{"ok":true}')
                except Exception:
                    self.send_response(400)
                    self.end_headers()
        admin = http.server.ThreadingHTTPServer((args.host, args.test_admin_port), Admin)
        threading.Thread(target=admin.serve_forever, daemon=True).start()
    with server(service, args.host, args.port) as s:
        print('READY ' + args.role + ' ' + str(s.server_address[1]), flush=True)
        s.serve_forever()


if __name__ == '__main__':
    main()
