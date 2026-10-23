# SPDX-License-Identifier: Apache-2.0
"""Slice-only canonical lowering for an empty run module. Not an RIR validator."""
import hashlib,json
from pathlib import Path
VERSION='aclt.rir.empty-run-lowering@1'
class SliceError(ValueError): pass

def need(ok,label):
    if not ok: raise SliceError(label)
def uint(n):
    need(0<=n<2**32,'u32 range')
    out=bytearray()
    while True:
        b=n&127;n>>=7;out.append(b|(128 if n else 0))
        if not n:return bytes(out)
def sint(n):
    out=bytearray()
    while True:
        b=n&127;n>>=7
        done=(n==0 and not b&64) or (n==-1 and b&64)
        out.append(b|(0 if done else 128))
        if done:return bytes(out)
class Reader:
    def __init__(self,raw):self.raw=raw;self.pos=0
    def take(self,n):
        need(n>=0 and self.pos+n<=len(self.raw),'truncated')
        b=self.raw[self.pos:self.pos+n];self.pos+=n;return b
    def byte(self):return self.take(1)[0]
    def num(self,signed=False,bits=32):
        start=self.pos;n=0
        for i in range((bits+6)//7):
            b=self.byte();n|=(b&127)<<(i*7)
            if b<128:
                if signed and b&64:n-=1<<((i+1)*7)
                need((-2**(bits-1)<=n<2**(bits-1)) if signed else (0<=n<2**bits),'LEB range')
                need(self.raw[start:self.pos]==(sint(n) if signed else uint(n)),'nonminimal LEB')
                return n
        raise SliceError('LEB too long')
    def name(self):return self.take(self.num()).decode('utf-8')
    def done(self):need(self.pos==len(self.raw),'trailing data')
def name(x):
    b=x.encode();return uint(len(b))+b
def section(i,b):return bytes([i])+uint(len(b))+b

def normalize(raw):
    need(raw[:8]==b'\0asm\x01\0\0\0','Wasm header')
    r=Reader(raw[8:]);sections={};removed=[];last=0
    while r.pos<len(r.raw):
        i=r.byte();p=r.take(r.num())
        if i==0:
            cr=Reader(p);custom_name=cr.name()
            need(custom_name in {'name','producers','target_features'},'unexpected custom section')
            removed.append({'section':custom_name,'sha256':hashlib.sha256(p).hexdigest()});continue
        need(i>last and i not in sections,'section order/duplicate');last=i;sections[i]=p
    need(set(sections)=={1,3,5,6,7,10},'module shape outside empty-run slice')
    need(sections[1]==b'\x01\x60\x00\x00','one []->[] function type')
    need(sections[3]==b'\x01\x00','one defined function of type 0')
    m=Reader(sections[5]);need(m.num()==1 and m.byte()==1,'one max-bounded memory')
    initial=m.num();maximum=m.num();m.done();need(initial==maximum==2,'probe fixed two-page memory')
    g=Reader(sections[6]);ng=g.num();need(ng<=1024,'global cap');globals_out=uint(ng);global_desc=[]
    for _ in range(ng):
        t=g.byte();mut=g.byte();op=g.byte()
        need(t in (0x7f,0x7e) and mut in (0,1) and op==(0x41 if t==0x7f else 0x42),'constant integer global')
        val=g.num(signed=True,bits=32 if t==0x7f else 64);need(g.byte()==0x0b,'global end')
        globals_out+=bytes([t,mut,op])+sint(val)+b'\x0b'
        global_desc.append({'type':'i32' if t==0x7f else 'i64','mutable':bool(mut),'value':val})
    g.done()
    ex=Reader(sections[7]);exports=[];trimmed=[];seen=set()
    for _ in range(ex.num()):
        n=ex.name();k=ex.byte();index=ex.num();need(n not in seen,'duplicate export');seen.add(n)
        if n=='run':need(k==0 and index==0,'run binding');exports.append((n,k,index))
        elif n=='memory':need(k==2 and index==0,'memory binding');exports.append((n,k,index))
        elif n in {'__data_end','__heap_base'}:
            need(k==3 and index<ng,'known auxiliary global export');trimmed.append(n)
        else:raise SliceError('unexpected export '+n)
    ex.done();need({e[0] for e in exports}=={'run','memory'},'expected run and memory exports')
    c=Reader(sections[10]);need(c.num()==1,'one code body');body=c.take(c.num());c.done()
    need(body==b'\x00\x0b','only an empty run body is supported by this probe')
    export_bytes=uint(len(exports))+b''.join(name(n)+bytes([k])+uint(index) for n,k,index in exports)
    normalized=b'\0asm\x01\0\0\0'+b''.join(section(i,b) for i,b in [(1,sections[1]),(3,sections[3]),(5,b'\x01\x01'+uint(initial)+uint(maximum)),(6,globals_out),(7,export_bytes),(10,b'\x01'+uint(len(body))+body)])
    return normalized,{'lowering_version':VERSION,'imports':[],'exports':[{'name':n,'kind':k,'index':idx} for n,k,idx in exports],'memory':{'initial_pages':initial,'maximum_pages':maximum},'globals':global_desc,'body':'empty [] -> []','removed_custom_sections':removed,'removed_exports':trimmed,'scope':'structural empty-run slice checks only; no general Wasm typing, RIR gas or execution validation'}

def cbor(x):
    def h(major,n):
        for limit,ai,width in [(24,0,0),(256,24,1),(65536,25,2),(2**32,26,4),(2**64,27,8)]:
            if n<limit:return bytes([(major<<5)|(n if not width else ai)])+(n.to_bytes(width,'big') if width else b'')
        raise SliceError('CBOR range')
    if type(x) is int:need(x>=0,'uint only');return h(0,x)
    if isinstance(x,bytes):return h(2,len(x))+x
    if isinstance(x,str):
        b=x.encode();return h(3,len(b))+b
    if isinstance(x,list):return h(4,len(x))+b''.join(cbor(v) for v in x)
    if isinstance(x,dict):
        pairs=sorted((cbor(k),cbor(v)) for k,v in x.items())
        return h(5,len(pairs))+b''.join(k+v for k,v in pairs)
    raise SliceError('unsupported CBOR type')

def artifact(body):
    # Candidate text wire keys; this is not an accepted protocol encoder.
    return cbor({'schema_version':1,'encoding_profile_id':'acl.enc.rir-0@1','rir_version':[0,1,0],'entry':'run','input_arity':0,'body':body})
def tagged(blob):
    tag=b'ACLt/RIR-0/Artifact/1'
    return hashlib.sha256(bytes([len(tag)])+tag+blob).hexdigest()

