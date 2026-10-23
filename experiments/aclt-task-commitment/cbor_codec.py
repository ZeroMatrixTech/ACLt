# SPDX-License-Identifier: Apache-2.0
"""Small canonical CBOR codec for this experiment: uint/ASCII/bstr/array/text-key map."""
MAX_BYTES=16384
MAX_DEPTH=16
MAX_ITEMS=256

class Rejected(ValueError):
    pass

def need(ok,message):
    if not ok:raise Rejected(message)

def head(major,value):
    need(type(value) is int and 0<=value<2**64,'uint64 range')
    for upper,ai,width in [(24,0,0),(256,24,1),(65536,25,2),(2**32,26,4),(2**64,27,8)]:
        if value<upper:return bytes([(major<<5)|(value if not width else ai)])+(value.to_bytes(width,'big') if width else b'')
    raise Rejected('uint64 range')

def encode(value,depth=0):
    need(depth<=MAX_DEPTH,'CBOR depth')
    if type(value) is int:out=head(0,value)
    elif type(value) is bytes:out=head(2,len(value))+value
    elif type(value) is str:
        need(all(32<=ord(c)<=126 for c in value),'printable ASCII required')
        data=value.encode('ascii');out=head(3,len(data))+data
    elif type(value) is list:
        need(len(value)<=MAX_ITEMS,'array cap');out=head(4,len(value))+b''.join(encode(v,depth+1) for v in value)
    elif type(value) is dict:
        need(len(value)<=MAX_ITEMS and all(type(k) is str for k in value),'text-key map required')
        pairs=sorted((encode(k,depth+1),encode(v,depth+1)) for k,v in value.items())
        out=head(5,len(pairs))+b''.join(k+v for k,v in pairs)
    else:raise Rejected('unsupported CBOR type')
    need(len(out)<=MAX_BYTES,'CBOR byte cap');return out

def decode(raw):
    need(type(raw) is bytes and len(raw)<=MAX_BYTES,'CBOR byte cap')
    pos=0
    def take(n):
        nonlocal pos
        need(n<=len(raw)-pos,'truncated CBOR');data=raw[pos:pos+n];pos+=n;return data
    def item(depth=0):
        need(depth<=MAX_DEPTH,'CBOR depth');initial=take(1)[0];major=initial>>5;ai=initial&31
        if ai<24:n=ai
        else:
            need(ai in (24,25,26,27),'indefinite/simple CBOR forbidden');width={24:1,25:2,26:4,27:8}[ai]
            n=int.from_bytes(take(width),'big');need(n>={1:24,2:256,4:65536,8:2**32}[width],'nonminimal CBOR integer/length')
        if major==0:return n
        if major in (2,3):
            data=take(n)
            if major==2:return data
            need(all(32<=b<=126 for b in data),'printable ASCII required');return data.decode('ascii')
        need(major in (4,5) and n<=MAX_ITEMS,'unsupported CBOR/container cap')
        if major==4:return [item(depth+1) for _ in range(n)]
        result={};last=None
        for _ in range(n):
            start=pos;key=item(depth+1);encoded=raw[start:pos]
            need(type(key) is str and (last is None or last<encoded),'map key order/duplicate/type')
            last=encoded;result[key]=item(depth+1)
        return result
    value=item();need(pos==len(raw),'trailing CBOR');need(encode(value)==raw,'noncanonical CBOR');return value
