'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{constructor(){this.children=[];this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.open=false;this.files=[];this.textContent='';}append(...xs){this.children.push(...xs);}replaceChildren(...xs){this.children=xs;}showModal(){this.open=true;}close(){this.open=false;this.onclose?.();}}
const contract='{"version":1,"kind":"relation","function":"fee","domains":{"x":{"min":0,"max":9007199254740993}},"relations":[{"id":"REL-SAME","text":"相同输入返回一致","precondition":"left_arg0 == right_arg0","assertion":"left_result == right_result"}],"seed":0,"max_pairs":16,"excluded_inputs":[]}';
function page({project=false}={}){
 const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);},calls=[];
 const draft={id:'upload_a',status:'DRAFT',filename:'fee.cj',goal:'原样返回',version:1,source_sha256:'hash',functions:[{name:'fee',params:[{name:'x',type:'Int64'}],return_type:'Int64'}]};
 if(project)Object.assign(draft,{kind:'PROJECT',production_paths:['src/a.cj'],original_tests:[],original_manifest:{'src/a.cj':'a','cjpm.toml':'b'}});
 let transport=async(path,options)=>path==='/api/uploads/repair'&&!options.method?{uploads:[]}:path.endsWith('/confirm')?{...draft,status:'CONFIRMED'}:draft;
 const ctx={$:get,document:{createElement:()=>new Element()},flow:{running:false},starting:false,reviewBusy:false,csrf:'token',location:{origin:'http://localhost'},TextDecoder,crypto:require('node:crypto').webcrypto,FormData:class{append(){}},toast(){},selectCase:async()=>({}),setTimeout:()=>1,clearTimeout(){},fetch:async(path,options={})=>{calls.push([path,options]);return{ok:true,json:async()=>transport(path,options)};}};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync('nexus/demo/static/upload.js','utf8'),ctx);return{get,calls,draft,setApi(fn){transport=fn;}};
}
async function ready(p){await p.get('upload-open').onclick();p.get('upload-file').files=[{}];p.get('upload-goal').value='原样返回';await p.get('upload-prepare').onclick();}
function file(text){const bytes=Buffer.from(text);return{name:'relations.json',size:bytes.length,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)};}
function read(p,f){const input=p.get('upload-relations-file');input.files=f?[f]:[];assert.equal(typeof input.onchange,'function');return input.onchange({target:input});}
test('relation import preserves16KiB exact integer text and requires explicit consent',async()=>{
 const p=page();await ready(p);p.get('upload-consent').checked=true;const text=' '.repeat(8500)+contract;await read(p,file(text));
 assert.equal(p.get('upload-relations').value,text);assert.equal(p.get('upload-consent').checked,false);assert.match(p.get('upload-relations-aliases').textContent,/left_arg0.*x.*right_arg0.*x.*left_result.*right_result/);
 const count=p.calls.length;await p.get('upload-confirm').onclick();assert.equal(p.calls.length,count);
 p.get('upload-consent').checked=true;await p.get('upload-confirm').onclick();assert.equal(JSON.parse(p.calls.at(-1)[1].body).relations_json,text);
});
test('cancel malformed UTF8 and oversized relation files preserve current editor',async()=>{
 const p=page();await ready(p);p.get('upload-relations').value=contract;
 for(const f of [null,file('[]'),file('null'),file('{'),file(' '.repeat(16385)),{name:'bad.json',size:1,arrayBuffer:async()=>Uint8Array.from([255]).buffer}]){await read(p,f);assert.equal(p.get('upload-relations').value,contract);}
});
test('late relation import cannot replace manual function source scope or closed state',async()=>{
 for(const change of ['edit','function','source','scope','close']){
  const p=page({project:change==='scope'});await ready(p);let resolve;const pending=read(p,{name:'slow.json',size:contract.length,arrayBuffer:()=>new Promise(r=>resolve=r)});assert.equal(p.get('upload-confirm').disabled,true);
  if(change==='edit'){p.get('upload-relations').value='manual';p.get('upload-relations').oninput();}
  if(change==='function')p.get('upload-function').onchange();if(change==='source')p.get('upload-file').onchange();if(change==='close')p.get('upload-dialog').close();
  if(change==='scope'){const input=p.get('upload-project-tree').children.flatMap(n=>n.children).find(n=>n.type==='checkbox');input.checked=false;input.onchange();}
  const before=p.get('upload-relations').value;resolve(new TextEncoder().encode(contract).buffer);await pending;assert.equal(p.get('upload-relations').value,before,change);
 }
});
test('old confirmation omits relations and frozen records load original text read-only',async()=>{
 const p=page();await ready(p);p.get('upload-consent').checked=true;await p.get('upload-confirm').onclick();assert.ok(!('relations_json' in JSON.parse(p.calls.at(-1)[1].body)));
 await p.get('upload-open').onclick();p.setApi(async()=>({...p.draft,status:'CONFIRMED',relations_json:contract,examples_json:'[]'}));p.get('upload-recent').value=p.draft.id;await p.get('upload-recent').onchange();assert.equal(p.get('upload-relations').value,contract);assert.equal(p.get('upload-relations').disabled,true);
});
