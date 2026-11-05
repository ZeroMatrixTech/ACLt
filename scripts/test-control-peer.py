#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Standard-library client for bounded test controls; no remote task invocation."""
import http.client
import json
import socket
import sys

def need(ok,message):
    if not ok:raise ValueError(message)
def probe(endpoint):
    host,port,token,action=(endpoint[k] for k in ('host','port','token','valid_action'));passed=[]
    good=b'{}';authorization=('Authorization: Bearer '+token+'\r\n').encode()
    def call(name,headers,body,expected):
        with socket.create_connection((host,port),timeout=6) as sock:
            sock.settimeout(6);sock.sendall(b'POST / HTTP/1.1\r\nHost: test\r\n'+headers+b'Connection: close\r\n\r\n'+body)
            reply=http.client.HTTPResponse(sock);reply.begin();data=reply.read(131073);need(reply.status==expected,name+' unexpected status '+str(reply.status));need(len(data)<=131072,'response limit');json.loads(data)
        passed.append(name)
    # Inject attempts fail before the callback, even when no task/packet exists.
    raw=b'{"action":"inject","changes":{"rows":"forged"}}'
    call('missing-auth-inject',b'Content-Length: '+str(len(raw)).encode()+b'\r\n',raw,403)
    call('wrong-token',b'Authorization: Bearer wrong\r\nContent-Length: 2\r\n',good,403)
    for name,length in [('negative-length',b'-1'),('oversize-length',b'65537')]:call(name,authorization+b'Content-Length: '+length+b'\r\n',b'',400)
    call('missing-length',authorization,b'',400)
    call('duplicate-length',authorization+b'Content-Length: 2\r\nContent-Length: 2\r\n',good,400)
    for name,raw in [('duplicate-json',b'{"action":"info","action":"inject"}'),('nan-json',b'{"a":NaN}'),('deep-json',b'{"a":'+b'['*25+b'0'+b']'*25+b'}')]:call(name,authorization+b'Content-Length: '+str(len(raw)).encode()+b'\r\n',raw,400)
    raw=json.dumps({'action':action}).encode();call('authorized-read',authorization+b'Content-Length: '+str(len(raw)).encode()+b'\r\n',raw,200)
    with socket.create_connection((host,port),timeout=6) as sock:
        sock.settimeout(6);sock.sendall(b'POST / HTTP/1.1\r\n');need(sock.recv(1024)==b'','incomplete header not closed')
    passed.append('header-timeout')
    return dict(endpoint=endpoint['label'],checks=len(passed),cases=passed,status='PASS')
if __name__=='__main__':print(json.dumps(dict(status='PASS',endpoints=[probe(e) for e in json.load(sys.stdin)])))
