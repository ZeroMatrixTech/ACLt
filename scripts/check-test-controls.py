#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Real HTTP regressions locally or from physical B over LAN; never runs VMs."""
import argparse
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def need(ok,message):
    if not ok:raise ValueError(message)
def load(directory,name):
    # Legacy experiments have local module names; don't cross-bind their protocols.
    base=ROOT/directory;names=[p.stem for p in base.glob('*.py')]
    for n in ('protocol','worker','authority','ledger','receiver','node','vm_node'):
        if n in sys.modules:del sys.modules[n]
    sys.path.insert(0,str(base))
    try:return importlib.import_module(name)
    finally:sys.path.pop(0)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--peer');p.add_argument('--a-host',default='127.0.0.1');p.add_argument('--remote-root');a=p.parse_args()
    if a.output.exists():p.error('new output directory required')
    if a.peer and (not re.fullmatch(r'[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+',a.peer) or not a.remote_root or not re.fullmatch(r'/[A-Za-z0-9_/.-]+',a.remote_root) or '..' in Path(a.remote_root).parts or a.remote_root in ('/','/tmp','/home')):p.error('explicit peer and new dedicated absolute remote path required')
    a.output=a.output.resolve();a.output.mkdir(mode=0o700,parents=True);os.chmod(a.output,0o700)
    receiver=load('experiments/aclt-multinode-admission','receiver');node=load('experiments/aclt-multinode-admission','node');vm=load('experiments/aclt-authority-admission','vm_node')
    # Public synthetic enrollment only, independent of any existing test deployment.
    manifest={'keys':{'a':{'unit':'A','secret':'synthetic-test-only'}},'tasks':{'t':{'values':[3,-1,8],'chunk':2,'units':['A']}}}
    database=a.output/'ledger.sqlite';r=receiver.Receiver(manifest,str(database),True);services=[];threads=[];endpoints=[]
    tcp,disabled=receiver.servers(r,port=0);need(disabled is None,'admin enabled without opt-in');tcp.server_close()
    before=database.read_bytes()
    try:
        token=secrets.token_hex(32);tcp,admin=receiver.servers(r,port=0,bind=a.a_host,admin_bind=a.a_host,control_token=token.encode());tcp.server_close();services.append(admin);endpoints.append(dict(label='multinode-admin',host=a.a_host,port=admin.server_address[1],token=token,valid_action='status'))
        nd=a.output/'node';nd.mkdir();token=secrets.token_hex(32);service=node.control_server(nd,{},token.encode(),a.a_host,0);services.append(service);endpoints.append(dict(label='multinode-worker-control',host=a.a_host,port=service.server_address[1],token=token,valid_action='info'))
        vd=a.output/'authority-node';vd.mkdir();(vd/'results').mkdir();token=secrets.token_hex(32);service=vm.control_server(vd,{},token.encode(),a.a_host,0);services.append(service);endpoints.append(dict(label='authority-worker-control',host=a.a_host,port=service.server_address[1],token=token,valid_action='info'))
        for service in services:
            t=threading.Thread(target=service.serve_forever,daemon=True);t.start();threads.append(t)
        client=ROOT/'scripts/test-control-peer.py'
        if a.peer:
            ssh=['ssh','-F','/dev/null','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10',a.peer];remote=shlex.quote(a.remote_root)
            archive=io.BytesIO()
            with tarfile.open(fileobj=archive,mode='w') as t:
                data=client.read_bytes();i=tarfile.TarInfo('peer.py');i.size=len(data);i.mode=0o600;t.addfile(i,io.BytesIO(data))
            deploy=subprocess.run(ssh+[f'umask 077; mkdir -- {remote} && tar -xf - -C {remote}'],input=archive.getvalue(),capture_output=True,timeout=30);(a.output/'deploy.log').write_bytes(deploy.stdout+deploy.stderr);need(deploy.returncode==0,'remote deploy')
            hostname=subprocess.check_output(ssh+['hostname'],text=True,timeout=15).strip();need(hostname!=socket.gethostname(),'separate-host assumption not accepted')
            got=subprocess.check_output(ssh+[f'sha256sum {remote}/peer.py'],text=True,timeout=15).split()[0];need(got==hashlib.sha256(client.read_bytes()).hexdigest(),'remote client bytes')
            command=ssh+[f'python3 -B {remote}/peer.py']
        else:command=[sys.executable,'-B',str(client)]
        run=subprocess.run(command,input=json.dumps(endpoints).encode(),capture_output=True,timeout=90);(a.output/'client.log').write_bytes(run.stdout+run.stderr);need(run.returncode==0,'client failed; raw log retained');result=json.loads(run.stdout)
        need(database.read_bytes()==before,'rejected controls changed ledger');need(not r.drop_next and r.pause_stage is None,'unauthorized control flag changed');need(list(nd.iterdir())==[] and list((vd/'results').iterdir())==[],'unauthorized worker operation wrote state')
        files=['tools/test_control.py','scripts/test-control-peer.py','scripts/check-test-controls.py','experiments/aclt-multinode-admission/receiver.py','experiments/aclt-multinode-admission/node.py','experiments/aclt-authority-admission/vm_node.py']
        result.update(scope='physical two-host HTTP controls under DUALHOST-SSH-1' if a.peer else 'local loopback HTTP regression only',source_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in files},default_admin_disabled=True,business_state_unchanged=True,guest_invocations=0,new_gate_claim=False)
        (a.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    finally:
        for service in services:service.shutdown();service.server_close()
        for t in threads:t.join(timeout=10)
if __name__=='__main__':main()
