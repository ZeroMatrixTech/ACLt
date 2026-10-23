# SPDX-License-Identifier: Apache-2.0
"""Restricted integer/void-control I/O slice, not a general RIR validator."""
import hashlib

class Reject(ValueError):
    pass

def need(ok, message):
    if not ok: raise Reject(message)

def u(n):
    need(type(n) is int and 0 <= n < 2**32, 'u32')
    out=bytearray()
    while True:
        b=n&127;n>>=7;out.append(b|(128 if n else 0))
        if not n:return bytes(out)

def s(n):
    out=bytearray()
    while True:
        b=n&127;n>>=7;done=(n==0 and not b&64) or (n==-1 and b&64)
        out.append(b|(0 if done else 128))
        if done:return bytes(out)

class Reader:
    def __init__(self, raw): self.raw=raw;self.pos=0
    def take(self,n):
        need(0<=n<=len(self.raw)-self.pos,'truncated')
        out=self.raw[self.pos:self.pos+n];self.pos+=n;return out
    def byte(self):return self.take(1)[0]
    def num(self,signed=False,bits=32):
        n=0
        for i in range((bits+6)//7):
            b=self.byte();n|=(b&127)<<(7*i)
            if b<128:
                if signed and b&64:n-=1<<(7*(i+1))
                need((-2**(bits-1)<=n<2**(bits-1)) if signed else 0<=n<2**bits,'LEB range')
                return n
        raise Reject('LEB length')
    def count(self, maximum):
        n=self.num();need(n<=maximum,'slice count limit');return n
    def text(self):
        try:return self.take(self.count(1024)).decode('utf-8')
        except UnicodeDecodeError as exc:raise Reject('UTF8') from exc
    def done(self):need(self.pos==len(self.raw),'trailing bytes')

def text(x):
    b=x.encode();return u(len(b))+b

def section(i,p):return bytes([i])+u(len(p))+p

ABI={'input_count':([], [0x7f]), 'input_len':([0x7f],[0x7e]),
     'input_read':([0x7f,0x7e,0x7f,0x7f],[]),'output_write':([0x7f,0x7f],[]),'abort':([0x7f],[])}
SIMPLE={0x00,0x01,0x0f,0x1a,0x1b,0x45,0x46,0x47,0x50,0x51,0x52,0x6a,0x6b,0x7c,0x7d,0xa7,0xad}
INDEX={0x0c,0x0d,0x10,0x20,0x21,0x22,0x23,0x24}
MEM={0x28:(0x7f,4,False),0x29:(0x7e,8,False),0x2d:(0x7f,1,False),
     0x36:(0x7f,4,True),0x37:(0x7e,8,True),0x3a:(0x7f,1,True)}

def decode_seq(r, depth=0):
    need(depth<=128,'slice control nesting')
    nodes=[]
    while True:
        op=r.byte()
        if op in (0x05,0x0b):return nodes,op
        node={'op':op,'args':[]}
        if op in (2,3,4):
            need(r.byte()==0x40,'slice supports void blocks only')
            body,end=decode_seq(r,depth+1);node['body']=body
            if end==5:
                need(op==4,'else outside if');other,end=decode_seq(r,depth+1);node['else']=other
            need(end==0x0b,'block end')
        elif op in INDEX:node['args']=[r.num()]
        elif op in MEM:
            align,offset=r.num(),r.num();need(2**align<=MEM[op][1] if align<32 else False,'alignment')
            node['args']=[align,offset]
        elif op in (0x41,0x42):node['args']=[r.num(True,32 if op==0x41 else 64)]
        else:need(op in SIMPLE,'opcode outside I/O slice: '+hex(op))
        nodes.append(node)

def encode_seq(nodes):
    out=b''
    for node in nodes:
        op=node['op'];out+=bytes([op]);args=node['args']
        if op in (2,3,4):
            out+=b'\x40'+encode_seq(node['body'])
            if node.get('else'):out+=b'\x05'+encode_seq(node['else'])
            out+=b'\x0b'
        elif op in INDEX:out+=u(args[0])
        elif op in MEM:out+=u(args[0])+u(args[1])
        elif op in (0x41,0x42):out+=s(args[0])
    return out

class Module:
    def __init__(self,raw):
        self.raw=bytes(raw)
        need(len(raw)<=4*1024*1024 and raw[:8]==b'\0asm\x01\0\0\0','Wasm header/size')
        r=Reader(raw[8:]);parts={};last=0;self.removed=[]
        while r.pos<len(r.raw):
            i=r.byte();p=r.take(r.num())
            if not i:
                cr=Reader(p);n=cr.text();need(n in {'name','producers','target_features'},'custom section outside slice')
                self.removed.append(n);continue
            need(i>last and i not in parts,'section order/duplicate');last=i;parts[i]=p
        need(set(parts)=={1,2,3,5,6,7,10},'module shape outside I/O slice')
        r=Reader(parts[1]);self.types=[]
        for _ in range(r.count(64)):
            need(r.byte()==0x60,'function type');params=list(r.take(r.count(16)));results=list(r.take(r.count(1)))
            need(all(x in (0x7f,0x7e) for x in params+results),'noninteger type')
            self.types.append((params,results))
        r.done();self.imports=[]
        r=Reader(parts[2]);seen=set()
        for _ in range(r.count(5)):
            mod,n=r.text(),r.text();need(r.byte()==0,'nonfunction import');index=r.num()
            need(mod=='aclt' and n in ABI and n not in seen,'unknown/duplicate ABI import')
            need(index<len(self.types) and self.types[index]==ABI[n],'ABI signature')
            self.imports.append((n,index));seen.add(n)
        need(seen==set(ABI),'this fixture requires the five ABI imports');r.done()
        r=Reader(parts[3]);self.functions=[r.num() for _ in range(r.count(32))];r.done()
        need(self.functions and all(i<len(self.types) for i in self.functions),'function type index')
        r=Reader(parts[5]);need(r.num()==1 and r.byte()==1,'one bounded memory')
        self.initial=r.num();self.maximum=r.num();r.done();need(self.initial==self.maximum==2,'fixture two-page memory')
        r=Reader(parts[6]);self.globals=[]
        for _ in range(r.count(1024)):
            typ,mut,op=r.byte(),r.byte(),r.byte();need(typ in (0x7f,0x7e) and mut in (0,1) and op==(0x41 if typ==0x7f else 0x42),'global initializer')
            val=r.num(True,32 if typ==0x7f else 64);need(r.byte()==0x0b,'global end');self.globals.append((typ,mut,val))
        r.done();r=Reader(parts[7]);self.exports=[];self.trimmed=[];seen=set()
        for _ in range(r.count(16)):
            n,k,index=r.text(),r.byte(),r.num();need(n not in seen,'duplicate export');seen.add(n)
            if n=='run':
                need(k==0 and len(self.imports)<=index<len(self.imports)+len(self.functions),'run index');self.run=index
                need(self.signature(index)==([],[]),'run signature');self.exports.append((n,k,index))
            elif n=='memory':need(k==2 and index==0,'memory export');self.exports.append((n,k,index))
            else:need(n in {'__heap_base','__data_end'} and k==3 and index<len(self.globals),'unknown export');self.trimmed.append(n)
        need({x[0] for x in self.exports}=={'run','memory'},'run/memory exports');r.done()
        r=Reader(parts[10]);need(r.count(32)==len(self.functions),'function/code count');self.code=[]
        for _ in self.functions:
            body=Reader(r.take(r.count(512*1024)));locals_=[]
            for _ in range(body.count(4096)):
                count=body.count(4096);typ=body.byte();need(typ in (0x7f,0x7e) and len(locals_)+count<=4096,'locals')
                locals_.extend([typ]*count)
            nodes,end=decode_seq(body);need(end==0x0b,'function end');body.done();self.code.append((locals_,nodes))
        r.done();self.max_stack=0
        for i in range(len(self.functions)):self.validate_function(i)

    def signature(self,index):
        need(0<=index<len(self.imports)+len(self.functions),'call index')
        t=self.imports[index][1] if index<len(self.imports) else self.functions[index-len(self.imports)]
        return self.types[t]

    def validate_function(self,i):
        params,results=self.types[self.functions[i]];need(not results,'slice defined functions return void')
        locals_=params+self.code[i][0]
        def seq(nodes,stack,labels,height):
            unreachable=False
            def pop(typ=None):
                if len(stack)==height and unreachable:return typ
                need(len(stack)>height,'operand underflow');actual=stack.pop()
                need(typ is None or actual==typ,'operand type');return actual
            for node in nodes:
                op=node['op'];a=node['args']
                if op in (2,3,4):
                    if op==4:pop(0x7f)
                    seq(node['body'],stack.copy(),labels+[[]],len(stack))
                    if op==4:seq(node.get('else',[]),stack.copy(),labels+[[]],len(stack))
                elif op in (0,0x0c,0x0f):
                    if op==0x0c:need(a[0]<len(labels),'branch depth')
                    stack[height:]=[];unreachable=True
                elif op==0x0d:need(a[0]<len(labels),'branch depth');pop(0x7f)
                elif op==0x10:
                    ps,rs=self.signature(a[0])
                    for typ in reversed(ps):pop(typ)
                    stack.extend(rs)
                elif op in (0x20,0x21,0x22):
                    need(a[0]<len(locals_),'local index');typ=locals_[a[0]]
                    if op!=0x20:pop(typ)
                    if op!=0x21:stack.append(typ)
                elif op in (0x23,0x24):
                    need(a[0]<len(self.globals),'global index');typ,mut,_=self.globals[a[0]]
                    if op==0x24:need(mut==1,'immutable global');pop(typ)
                    else:stack.append(typ)
                elif op in MEM:
                    typ,_,store=MEM[op]
                    if store:pop(typ)
                    pop(0x7f)
                    if not store:stack.append(typ)
                elif op in (0x41,0x42):stack.append(0x7f if op==0x41 else 0x7e)
                elif op==0x1a:pop()
                elif op==0x1b:
                    pop(0x7f);typ=pop();pop(typ);stack.append(typ)
                elif op in (0x45,0x50):pop(0x7f if op==0x45 else 0x7e);stack.append(0x7f)
                elif op in (0x46,0x47,0x51,0x52,0x6a,0x6b,0x7c,0x7d):
                    typ=0x7f if op in (0x46,0x47,0x6a,0x6b) else 0x7e
                    pop(typ);pop(typ);stack.append(typ if op in (0x6a,0x6b,0x7c,0x7d) else 0x7f)
                elif op==0xa7:pop(0x7e);stack.append(0x7f)
                elif op==0xad:pop(0x7f);stack.append(0x7e)
                elif op!=1:raise Reject('unsupported type rule')
                need(len(stack)<=4096,'operand stack cap');self.max_stack=max(self.max_stack,len(stack))
            need(len(stack)==height,'block/function leftover values')
        seq(self.code[i][1],[],[[]],0)

    def canonical(self):
        types=u(len(self.types))+b''.join(b'\x60'+u(len(p))+bytes(p)+u(len(r))+bytes(r) for p,r in self.types)
        imports=u(len(self.imports))+b''.join(text('aclt')+text(n)+b'\0'+u(t) for n,t in self.imports)
        funcs=u(len(self.functions))+b''.join(u(t) for t in self.functions)
        globals_=u(len(self.globals))+b''.join(bytes([t,m,0x41 if t==0x7f else 0x42])+s(v)+b'\x0b' for t,m,v in self.globals)
        exports=u(len(self.exports))+b''.join(text(n)+bytes([k])+u(i) for n,k,i in self.exports)
        code=u(len(self.code))
        for locals_,nodes in self.code:
            groups=[]
            for t in locals_:
                if groups and groups[-1][1]==t:groups[-1][0]+=1
                else:groups.append([1,t])
            body=u(len(groups))+b''.join(u(n)+bytes([t]) for n,t in groups)+encode_seq(nodes)+b'\x0b'
            code+=u(len(body))+body
        return b'\0asm\x01\0\0\0'+b''.join(section(i,p) for i,p in [(1,types),(2,imports),(3,funcs),(5,b'\x01\x01'+u(self.initial)+u(self.maximum)),(6,globals_),(7,exports),(10,code)])

def normalize(raw):
    m=Module(raw);body=m.canonical()
    return body,{'lowering_version':'aclt.rir.io16-lowering@1','imports':[{'module':'aclt','name':n,'type':m.types[t]} for n,t in m.imports],'exports':[n for n,_,_ in m.exports],'removed_custom_sections':m.removed,'removed_exports':m.trimmed,'max_operand_stack':m.max_stack,'defined_functions':len(m.functions),'scope':'restricted integer/void-control I/O slice only'}

# Shared primitive encoding rules, copied unchanged from the candidate slice-1 codec.
def cbor(x):
    def h(major,n):
        for limit,ai,width in [(24,0,0),(256,24,1),(65536,25,2),(2**32,26,4),(2**64,27,8)]:
            if n<limit:return bytes([(major<<5)|(n if not width else ai)])+(n.to_bytes(width,'big') if width else b'')
        raise Reject('CBOR range')
    if type(x) is int:need(x>=0,'uint');return h(0,x)
    if isinstance(x,bytes):return h(2,len(x))+x
    if isinstance(x,str):
        b=x.encode();return h(3,len(b))+b
    if isinstance(x,list):return h(4,len(x))+b''.join(cbor(v) for v in x)
    if isinstance(x,dict):
        pairs=sorted((cbor(k),cbor(v)) for k,v in x.items());return h(5,len(pairs))+b''.join(k+v for k,v in pairs)
    raise Reject('CBOR type')

def artifact(body):return cbor({'schema_version':1,'encoding_profile_id':'acl.enc.rir-0@1','rir_version':[0,1,0],'entry':'run','input_arity':1,'body':body})
def tagged(blob):
    tag=b'ACLt/RIR-0/Artifact/1';return hashlib.sha256(bytes([len(tag)])+tag+blob).hexdigest()

def decode_artifact(raw):
    """Strict small candidate-envelope reader; not the full P0-1/RIR codec."""
    need(type(raw) is bytes and len(raw)<=1024*1024,'slice artifact size')
    r=Reader(raw)
    def value(depth=0):
        need(depth<=16,'CBOR depth');initial=r.byte();major=initial>>5;ai=initial&31
        if ai<24:n=ai
        else:
            widths={24:1,25:2,26:4,27:8};need(ai in widths,'CBOR indefinite/simple')
            width=widths[ai];n=int.from_bytes(r.take(width),'big')
            need(n>={1:24,2:256,4:65536,8:2**32}[width],'CBOR nonminimal')
        if major==0:return n
        if major==2:return r.take(n)
        if major==3:
            try:return r.take(n).decode('utf8')
            except UnicodeDecodeError as exc:raise Reject('CBOR UTF8') from exc
        need(n<=64,'CBOR container limit')
        if major==4:return [value(depth+1) for _ in range(n)]
        if major==5:
            out={};last=None
            for _ in range(n):
                start=r.pos;k=value(depth+1);encoded=r.raw[start:r.pos]
                need(type(k) is str and (last is None or last<encoded),'CBOR key/order/duplicate');last=encoded
                out[k]=value(depth+1)
            return out
        raise Reject('CBOR primitive')
    obj=value();r.done()
    need(type(obj) is dict and set(obj)=={'schema_version','encoding_profile_id','rir_version','entry','input_arity','body'},'artifact fields')
    need(obj['schema_version']==1 and obj['encoding_profile_id']=='acl.enc.rir-0@1' and obj['rir_version']==[0,1,0] and obj['entry']=='run' and obj['input_arity']==1 and type(obj['body']) is bytes,'artifact field values')
    need(artifact(obj['body'])==raw,'candidate canonical envelope')
    module=Module(obj['body']);need(module.canonical()==obj['body'],'candidate canonical Wasm')
    return module
