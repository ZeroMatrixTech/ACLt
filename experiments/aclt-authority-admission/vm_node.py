# SPDX-License-Identifier: Apache-2.0
"""Explicitly test-only VM control plane. Never an internet-facing API."""
import http.server
import sys
import json
from pathlib import Path
import secrets
import time
from protocol import canonical, claim, digest, envelope, exchange, sign_request
from worker import Worker, durable_new

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"tools"))
import test_control
CONFIG = None
DATA = Path("/data")


def node(obj):
    key = obj.get('key', 'a')
    config = dict(CONFIG['base'], key=key, **CONFIG['keys'][key])
    port = CONFIG['gateways'][obj.get('gateway', 'primary')]
    def transmit(message):
        reply = exchange('10.0.2.2', port, message, timeout=10)
        durable_new(Path('/evidence')/('wire-'+secrets.token_hex(16)+'.json'),
                    canonical({'request': message, 'response': reply}))
        return reply
    return Worker(DATA/'results', config, '/data/authority.pub', '/experiment/worker-bin',
                  transmit)


class Handler(test_control.BoundedHandler):
    def log_message(self, *unused):
        pass

    def do_POST(self):
        try:
            obj = test_control.request(self)
            action = obj['action']
            if obj.get('delay'):
                print('DELAY_READY ' + action, flush=True)
                time.sleep(min(obj['delay'], 2))
            if action == 'info':
                result = {'boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                          'files': {p.name: digest(p.read_bytes()) for p in (DATA/'results').glob('*') if p.is_file()}}
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
                    packet = (DATA/'results')/(claim(w.config['tasks'][task]['values'])+'.submit.json')
                    message = json.loads(packet.read_text())
                    message.pop('mac')
                    message.update(obj.get('changes', {}))
                    result = w.send(sign_request(message, w.config['secret']))
                else:
                    raise ValueError('unknown test action')
            test_control.response(self,result)
        except Exception as exc:
            test_control.response(self,{'error':type(exc).__name__},403 if isinstance(exc,PermissionError) else 400)


def control_server(directory,config,token,bind='127.0.0.1',port=9001):
    global CONFIG,DATA
    test_control.validate_token(token)
    DATA=Path(directory);CONFIG=config
    service=http.server.ThreadingHTTPServer((bind,port),Handler);service.control_token=token;service.daemon_threads=True;return service

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,default=Path('/data'));p.add_argument('--test-control-token-file',type=Path,required=True);p.add_argument('--bind',default='127.0.0.1');p.add_argument('--port',type=int,default=9001);a=p.parse_args()
    token=test_control.token_file(a.test_control_token_file)
    (a.data/'results').mkdir(exist_ok=True)
    with control_server(a.data,json.loads((a.data/'config.json').read_text()),token,a.bind,a.port) as service:
        print('NODE_READY',flush=True);service.serve_forever()
