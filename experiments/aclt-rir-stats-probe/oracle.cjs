// SPDX-License-Identifier: Apache-2.0
// Optional existing Wasm engine oracle: semantic output/traps only, never gas.
const fs = require('fs'), path = require('path'), crypto = require('crypto');
const [left,right,report] = process.argv.slice(2);
if (!left || !right || !report) throw new Error('usage: node oracle.cjs A B NEW_REPORT');
class HostTrap extends Error { constructor(outcome,code) {super(outcome);this.outcome=outcome;this.code=code;} }
function execute(mod, c) {
  const inputs=[c.input];
  let instance, output=[];
  const memory=()=>new Uint8Array(instance.exports.memory.buffer);
  const imports={aclt:{
    input_count:()=>inputs.length,
    input_len:index=>{index>>>=0;if(index>=inputs.length)throw new HostTrap('TRAP_HOST_ARGUMENT');return BigInt(inputs[index].length);},
    input_read:(index,offset,dst,len)=>{
      index>>>=0;dst>>>=0;len>>>=0;offset=BigInt.asUintN(64,offset);
      if(index>=inputs.length || offset+BigInt(len)>BigInt(inputs[index].length) || BigInt(dst)+BigInt(len)>BigInt(memory().length))throw new HostTrap('TRAP_HOST_ARGUMENT');
      memory().set(inputs[index].subarray(Number(offset),Number(offset)+len),dst);
    },
    output_write:(src,len)=>{
      src>>>=0;len>>>=0;
      if(BigInt(src)+BigInt(len)>BigInt(memory().length))throw new HostTrap('TRAP_HOST_ARGUMENT');
      const limit=c.limits.output_limit===undefined?16:c.limits.output_limit;
      if(BigInt(output.length)+BigInt(len)>BigInt(limit))throw new HostTrap('TRAP_OUTPUT_LIMIT');
      output.push(...memory().subarray(src,src+len));
    },
    abort:code=>{throw new HostTrap('ABORT',code>>>0);}
  }};
  instance=new WebAssembly.Instance(mod,imports);
  try {instance.exports.run();return {outcome:'OK',output_hex:Buffer.from(output).toString('hex')};}
  catch(e) {
    if(!(e instanceof HostTrap))throw e;
    return e.outcome==='ABORT'?{outcome:'ABORT',abort_code:e.code}:{outcome:e.outcome};
  }
}
const checks=[];
for(const [host,root] of [['A',left],['B',right]]) {
  for(const location of ['first-location','second-location']) {
    const execution=JSON.parse(fs.readFileSync(path.join(root,location,'execution.json'),'utf8'));
    for(const file of ['raw.wasm','normalized.wasm']) {
      const bytes=fs.readFileSync(path.join(root,location,file));
      if(!WebAssembly.validate(bytes))throw new Error('Wasm invalid');
      const mod=new WebAssembly.Module(bytes);
      const names=WebAssembly.Module.imports(mod);
      if(names.length!==5 || names.some(n=>n.module!=='aclt' || n.kind!=='function'))throw new Error('imports');
      for(const [index,c] of execution.cases.entries()) {
        if(c.name.startsWith('golden-') || c.actual.kind || c.limits.gas_limit!==50000000 || c.limits.call_depth_limit!==8 || !['OK','ABORT','TRAP_OUTPUT_LIMIT'].includes(c.actual.outcome))continue;
        c.input=fs.readFileSync(path.join(root,location,'cases',String(index).padStart(3,'0')+'-'+c.name,'input.bin'));
        const actual=execute(mod,c);
        for(const [key,val] of Object.entries(c.actual)) {
          if(key==='gas_used' || key==='outcome_digest')continue;
          if(actual[key]!==val)throw new Error(JSON.stringify({host,location,file,case:c.name,actual,expected:c.actual}));
        }
        checks.push({host,location,file,case:c.name,actual});
      }
    }
  }
}
const result={status:'PASS',node:process.version,oracle_sha256:crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex'),scope:'Existing engine validates eight Wasm modules and checks semantic output/abort/output-limit only. Gas, call-depth and envelope binding are excluded.',checks:checks.length,results:checks};
fs.writeFileSync(report,JSON.stringify(result,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({status:result.status,checks:result.checks,scope:result.scope}));
