# SPDX-License-Identifier: Apache-2.0
"""Opt-in process gates, diagnostic submission variants, and public worker export."""
import argparse,json,os,signal,time,secrets
from context import *
from worker import launch,export_worker
from network import request,response,exchange

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    e=sub.add_parser('environment');e.add_argument('--report',type=Path,required=True)
    k=sub.add_parser('kill');k.add_argument('--ready',type=Path,required=True)
    pause=sub.add_parser('pause')
    for name in ['config','public','commitment','artifact','input','bundle','state','ready']:pause.add_argument('--'+name,type=Path,required=name!='bundle')
    pause.add_argument('--task-id',required=True);pause.add_argument('--at',choices=['after-intent','after-permit','after-outcome','after-prepared'],required=True)
    x=sub.add_parser('export');x.add_argument('--root',type=Path,required=True);x.add_argument('--report',type=Path,required=True)
    v=sub.add_parser('variant')
    for name in ['config','public','state','report']:v.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    if a.command=='environment':durable_new(a.report,encode({'environment_digest':environment_digest(),'base':base.environment()}));print(environment_digest().hex())
    elif a.command=='kill':
        pid=json.loads(regular(a.ready))['pid'];cmd=regular(Path('/proc')/str(pid)/'cmdline')
        need(str(Path(__file__).resolve()).encode() in cmd and b'pause' in cmd,'unrelated PID');os.kill(pid,signal.SIGKILL);print('KILLED_TEST_PROCESS')
    elif a.command=='export':
        workers=[export_worker(path.parent.parent) for path in sorted(a.root.rglob('journal/stream'))]
        durable_new(a.report,encode({'workers':workers}));print('EXPORTED',len(workers))
    elif a.command=='variant':
        cfg=config(a.config);raw=regular(a.state/'submission.cbor');subm=decode(raw);sb=decode(subm['body']);raw=raw+b'corrupt-tail'
        # A deliberately invalid candidate is diagnostic only. It never edits the
        # sealed packet or trusted worker stream; no guest invocation is available.
        nonce=secrets.token_bytes(16);sp=encode({'submission_digest':sha(raw),'attempt_nonce':nonce})
        se=event_bytes(subm['worker']['stream'],999,ZERO,'SEND',sha(sp),[])
        data={'submission':raw,'prepared_event':b'','prepared_payload':b'','send_event':se,'send_payload':sp}
        packet=request(cfg,sb['grant_id'],'SUBMIT',data,nonce);reply=exchange(cfg,packet);r=response(packet,reply,cfg,a.public)
        with a.report.open('x') as f:json.dump({'status':r['status'],'receipt_digest':sha(r['receipt']).hex()},f)
        print(json.dumps({'status':r['status']}))
    else:
        def hook(stage):
            if stage==a.at:
                durable_new(a.ready,json.dumps({'pid':os.getpid(),'stage':stage}).encode())
                while True:time.sleep(0.1)
        launch(regular(a.commitment),a.task_id,regular(a.artifact),[regular(a.input)],config(a.config),a.public,a.state,hook=hook)
