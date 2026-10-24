# SPDX-License-Identifier: Apache-2.0
"""Authenticated experiment requests, signed causal responses, bounded LAN framing."""
import hmac
import secrets
import socket
from context import *
MAX_FRAME=16*1024*1024

def receive(sock):
    def exact(n):
        data=bytearray()
        while len(data)<n:
            part=sock.recv(n-len(data))
            if not part:raise HostFault('connection closed')
            data.extend(part)
        return bytes(data)
    n=int.from_bytes(exact(4),'big');need(0<n<=MAX_FRAME,'frame cap');return exact(n)

def send(sock,data):need(0<len(data)<=MAX_FRAME,'frame cap');sock.sendall(len(data).to_bytes(4,'big')+data)

def exchange(cfg,packet):
    try:
        with socket.create_connection((cfg['host'],cfg['port']),timeout=5) as sock:
            sock.settimeout(10);send(sock,packet);return receive(sock)
    except (OSError,TimeoutError) as exc:raise HostFault('causal endpoint unavailable') from exc

def request(cfg,gid,op,data,nonce=None):
    raw=encode({'schema_id':'aclt.exp.causal-request@1','authority_id':cfg['authority_id'],'provider_ref':cfg['provider_ref'],'grant_id':gid,'nonce':nonce if nonce is not None else secrets.token_bytes(16),'op':op,'data':data})
    return encode({'payload':raw,'mac':hmac.digest(cfg['provider_secret'],raw,'sha256')})

def response(packet,reply,cfg,public):
    req=decode(decode(packet)['payload']);obj=verify(reply,public,cfg['public_digest'])
    expected={'schema_id':'aclt.exp.causal-response@1','authority_id':cfg['authority_id'],'request_digest':sha(packet),'op':req['op'],'grant_id':req['grant_id'],'nonce':req['nonce']}
    need(type(obj) is dict and set(obj)==set(expected)|{'status','reason','event_ref','receipt'} and all(obj[k]==v for k,v in expected.items()),'causal response binding')
    b32(obj['event_ref']);return obj
