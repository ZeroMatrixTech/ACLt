# SPDX-License-Identifier: Apache-2.0
"""Explicitly test-only VM control plane. Never an internet-facing API."""
import http.server
import json
from pathlib import Path
import secrets
import time
from protocol import canonical, claim, digest, envelope, exchange, sign_request
from worker import Worker, durable_new

CONFIG = json.loads(Path('/data/config.json').read_text())


def node(obj):
    key = obj.get('key', 'a')
    config = dict(CONFIG['base'], key=key, **CONFIG['keys'][key])
    port = CONFIG['gateways'][obj.get('gateway', 'primary')]
    def transmit(message):
        reply = exchange('10.0.2.2', port, message, timeout=10)
        durable_new(Path('/evidence')/('wire-'+secrets.token_hex(16)+'.json'),
                    canonical({'request': message, 'response': reply}))
        return reply
    return Worker('/data/results', config, '/data/authority.pub', '/experiment/worker-bin',
                  transmit)


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *unused):
        pass

    def do_POST(self):
        try:
            n = int(self.headers['Content-Length'])
            if not 0 < n <= 1048576:
                raise ValueError('control frame')
            obj = json.loads(self.rfile.read(n))
            action = obj['action']
            if obj.get('delay'):
                print('DELAY_READY ' + action, flush=True)
                time.sleep(min(obj['delay'], 2))
            if action == 'info':
                result = {'boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                          'files': {p.name: digest(p.read_bytes()) for p in Path('/data/results').glob('*') if p.is_file()}}
            else:
                w = node(obj)
                task = obj['task']
                if action == 'compute':
                    result = w.compute(task, prepare_only=obj.get('prepare_only', False))
                elif action == 'replay':
                    result = w.replay(task)
                elif action == 'audit':
                    result = w.audit(task)
                elif action == 'reserve':
                    result = w.send(envelope(w.config, 'reserve', w.boot, task=task))
                elif action == 'inject':
                    packet = Path('/data/results')/(claim(w.config['tasks'][task]['values'])+'.submit.json')
                    message = json.loads(packet.read_text())
                    message.pop('mac')
                    message.update(obj.get('changes', {}))
                    result = w.send(sign_request(message, w.config['secret']))
                else:
                    raise ValueError('unknown test action')
            data = canonical(result)
            self.send_response(200)
        except Exception as exc:
            data = canonical({'error': type(exc).__name__, 'detail': str(exc)})
            self.send_response(400)
        self.end_headers()
        self.wfile.write(data)


if __name__ == '__main__':
    Path('/data/results').mkdir(exist_ok=True)
    service = http.server.ThreadingHTTPServer(('0.0.0.0', 9001), Handler)
    print('NODE_READY', flush=True)
    service.serve_forever()
