# SPDX-License-Identifier: Apache-2.0
"""Small length-framed canonical CBOR transport; LAN traffic is not encrypted."""
import hmac
import secrets
import socket
from common import encode,decode,sha,need,HostFault,Rejected
from authorization import REQUEST_SCHEMA,REQUEST_FIELDS,RESPONSE_SCHEMA,grant_id
from auth_crypto import verify

MAX_FRAME=16384

def recv_exact(sock,length):
    data=bytearray()
    while len(data)<length:
        part=sock.recv(length-len(data))
        if not part:raise HostFault('authorization connection closed')
        data.extend(part)
    return bytes(data)

def receive(sock):
    n=int.from_bytes(recv_exact(sock,4),'big')
    if not 0<n<=MAX_FRAME:raise HostFault('authorization frame limit')
    return recv_exact(sock,n)

def send(sock,data):
    if not 0<len(data)<=MAX_FRAME:raise HostFault('authorization frame limit')
    sock.sendall(len(data).to_bytes(4,'big')+data)

def exchange(config,packet):
    try:
        with socket.create_connection((config['host'],config['port']),timeout=4) as sock:
            sock.settimeout(4);send(sock,packet);return receive(sock)
    except (OSError,TimeoutError) as exc:raise HostFault('authorization service unavailable') from exc

def make_request(config,body,op):
    request={'schema_id':REQUEST_SCHEMA,'authority_id':config['authority_id'],'op':op,
             'grant_id':grant_id(body),'execution_tuple_digest':body['execution_tuple_digest'],
             'provider_ref':config['provider_ref'],'nonce':secrets.token_bytes(16)}
    raw=encode(request)
    return encode({'payload':raw,'mac':hmac.digest(config['provider_secret'],raw,'sha256')})

def request_view(packet,config,body,op):
    obj=decode(packet);need(type(obj) is dict and set(obj)=={'payload','mac'},'saved request envelope')
    need(type(obj['payload']) is bytes and type(obj['mac']) is bytes and hmac.compare_digest(obj['mac'],hmac.digest(config['provider_secret'],obj['payload'],'sha256')),'saved request authentication')
    req=decode(obj['payload']);need(type(req) is dict and set(req)==REQUEST_FIELDS,'saved request fields')
    expect={'schema_id':REQUEST_SCHEMA,'authority_id':config['authority_id'],'op':op,'grant_id':grant_id(body),
            'execution_tuple_digest':body['execution_tuple_digest'],'provider_ref':config['provider_ref']}
    need(all(req.get(k)==v for k,v in expect.items()) and type(req['nonce']) is bytes and len(req['nonce'])==16,'saved request binding')
    return req

def check_response(packet,response,config,public,body,op):
    request=request_view(packet,config,body,op)
    try:result=verify(response,public,config['public_digest'])
    except Rejected as exc:raise HostFault('untrusted authority response') from exc
    expected={'schema_id':RESPONSE_SCHEMA,'authority_id':config['authority_id'],'request_digest':sha(packet),
              'op':op,'grant_id':grant_id(body),'nonce':request['nonce']}
    if type(result) is not dict or set(result)!=set(expected)|{'status','reason'} or any(result.get(k)!=v for k,v in expected.items()):raise HostFault('authority response binding mismatch')
    if result['status']!='ALLOW':raise Rejected('authority denied '+op+': '+str(result['reason']))
    return result

def authorize(config,public,body,op,transport=None):
    request=make_request(config,body,op)
    response=(transport or (lambda data:exchange(config,data)))(request)
    check_response(request,response,config,public,body,op)
    return request,response
