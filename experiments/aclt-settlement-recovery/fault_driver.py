# SPDX-License-Identifier: Apache-2.0
"""Test-only ready/fsync gates, reply drop, and guarded kill of an owned paused worker."""
import argparse
import os
import signal
import time
from context import *
from durability import durable_new


class DropReply(Exception): pass


def start_ticks(pid):
    return regular(Path('/proc')/str(pid)/'stat').rpartition(b') ')[2].split()[19].decode('ascii')


def pause(ready,point,info):
    durable_new(ready,json.dumps({'pid':os.getpid(),'start_ticks':start_ticks(os.getpid()),'point':point,**info},sort_keys=True).encode())
    while True: time.sleep(.1)


class FaultGate:
    def __init__(self,control): self.control=Path(control)
    def __call__(self,point,info):
        control=json.loads(regular(self.control))
        if not control: return
        need(set(control)=={'point','mode','op','policy_id','ready','token'},'test fault control fields')
        need(control['point'] in ['before_commit','after_commit'] and control['mode'] in ['pause','drop'],'test gate mode')
        need(control['mode']!='drop' or control['point']=='after_commit','reply drop must follow commit')
        if point!=control['point'] or info['op']!=control['op'] or info['policy_id']!=control['policy_id'] or info['status']!='SETTLED': return
        metadata={**info,'token':control['token']}
        if control['mode']=='pause': pause(control['ready'],point,metadata)
        durable_new(control['ready'],json.dumps({'pid':os.getpid(),'point':point,**metadata},sort_keys=True).encode())
        raise DropReply('test-only committed response loss')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='mode',required=True)
    gate=sub.add_parser('pause-execute')
    for n in ['config','public','state','binding','ready']: gate.add_argument('--'+n,type=Path,required=True)
    gate.add_argument('--task-id',required=True); gate.add_argument('--point',choices=['after_permit','after_outcome'],required=True)
    race=sub.add_parser('race-settle')
    for n in ['config','public','report','ready','release']: race.add_argument('--'+n,type=Path,required=True)
    race.add_argument('--policy-id',required=True)
    kill=sub.add_parser('kill'); kill.add_argument('--ready',type=Path,required=True); a=p.parse_args()
    if a.mode=='kill':
        data=json.loads(regular(a.ready)); pid=data['pid']; cmd=regular(Path('/proc')/str(pid)/'cmdline')
        need(str(Path(__file__).resolve()).encode() in cmd and (b'pause-execute' in cmd or b'race-settle' in cmd) and start_ticks(pid)==data['start_ticks'],'refuse unrelated/reused worker PID')
        os.kill(pid,signal.SIGKILL); print('KILLED_OWNED_PAUSED_WORKER')
    elif a.mode=='race-settle':
        import subprocess
        durable_new(a.ready,json.dumps({'pid':os.getpid(),'start_ticks':start_ticks(os.getpid()),'point':'race-ready'}).encode())
        while not a.release.exists(): time.sleep(.02)
        raise SystemExit(subprocess.run([sys.executable,'-B',str(HERE/'client.py'),'settle','--config',str(a.config),'--public',str(a.public),'--policy-id',a.policy_id,'--report',str(a.report)]).returncode)
    else:
        # context adds BASE to sys.path; load our wrapper explicitly, not the base executor.
        import importlib.util
        spec=importlib.util.spec_from_file_location('paused_recovery_executor',HERE/'executor.py'); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        def hook(point):
            if point==a.point: pause(a.ready,point,{'task':a.task_id})
        module.execute_once(config(a.config),a.public,a.state,regular(a.binding),a.task_id,test_hook=hook)
