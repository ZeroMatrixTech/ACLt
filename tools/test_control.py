# SPDX-License-Identifier: Apache-2.0
"""Test HTTP controls with token authentication and explicit request framing."""
import http.server
import hmac
import json
import os
from pathlib import Path
import stat

TIMEOUT=3

def validate_token(token):
    if type(token) is not bytes or not 32<=len(token)<=256 or any(x<33 or x>126 for x in token):raise ValueError('invalid test control token')
    return token

def token_file(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        meta=os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_uid!=os.getuid() or stat.S_IMODE(meta.st_mode)&0o077:
            raise ValueError('test control token must be an owned private regular file')
        with os.fdopen(fd,'rb',closefd=False) as f:token=f.read(257).strip()
    finally:os.close(fd)
    return validate_token(token)

def request(handler):
    """Authenticate before reading body or invoking any side-effecting callback."""
    handler.connection.settimeout(TIMEOUT)
    headers=handler.headers
    auth=headers.get_all('Authorization',[])
    if len(auth)!=1 or not hmac.compare_digest(auth[0].encode(),b'Bearer '+handler.server.control_token):
        raise PermissionError('test control authorization required')
    lengths=headers.get_all('Content-Length',[])
    if len(lengths)!=1 or headers.get_all('Transfer-Encoding',[]):raise ValueError('one Content-Length required')
    text=lengths[0]
    if not text or not text.isascii() or not text.isdecimal():raise ValueError('frame length')
    count=int(text)
    if count<=0:raise ValueError('positive frame length required')
    raw=handler.rfile.read(count)
    if len(raw)!=count:raise ValueError('incomplete frame')
    def unique(pairs):
        obj={}
        for key,value in pairs:
            if key in obj:raise ValueError('duplicate JSON key')
            obj[key]=value
        return obj
    def reject(_):raise ValueError('non-JSON constant')
    obj=json.loads(raw,object_pairs_hook=unique,parse_constant=reject)
    if type(obj) is not dict:raise ValueError('object required')
    return obj

def response(handler,value,status=200):
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    handler.send_response(status);handler.send_header('Content-Type','application/json');handler.send_header('Content-Length',str(len(raw)));handler.send_header('Connection','close');handler.end_headers();handler.wfile.write(raw);handler.close_connection=True

class BoundedHandler(http.server.BaseHTTPRequestHandler):
    def setup(self):
        super().setup();self.connection.settimeout(TIMEOUT)
