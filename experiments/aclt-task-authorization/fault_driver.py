# SPDX-License-Identifier: Apache-2.0
"""Explicit test-only process gates; never used by the normal runner."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from common import regular,decode_config,encode,environment,environment_digest
from durability import durable_new
from runner import launch

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    env=sub.add_parser('environment');env.add_argument('--report',type=Path,required=True)
    pause=sub.add_parser('pause')
    for name in ['config','public','commitment','artifact','input','bundle','state','ready']:pause.add_argument('--'+name,type=Path,required=True)
    pause.add_argument('--task-id',required=True);pause.add_argument('--at',choices=['after-intent','after-permit'],required=True)
    kill=sub.add_parser('kill');kill.add_argument('--ready',type=Path,required=True)
    args=p.parse_args()
    if args.command=='environment':
        durable_new(args.report,encode(environment()));print(environment_digest().hex())
    elif args.command=='kill':
        data=json.loads(regular(args.ready));pid=data['pid']
        cmd=Path('/proc')/str(pid)/'cmdline'
        if str(Path(__file__).resolve()).encode() not in regular(cmd):raise RuntimeError('refuse unrelated PID')
        os.kill(pid,signal.SIGKILL);print('KILLED_TEST_PROCESS')
    else:
        def hook(stage):
            if stage==args.at:
                durable_new(args.ready,json.dumps({'pid':os.getpid(),'stage':stage}).encode())
                while True:time.sleep(0.1)
        launch(regular(args.bundle),regular(args.commitment),args.task_id,regular(args.artifact),[regular(args.input)],decode_config(args.config),args.public,args.state,test_hook=hook)
