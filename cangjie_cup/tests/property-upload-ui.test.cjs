'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{constructor(){this.children=[];this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.open=false;this.files=[];this.textContent='';}append(...xs){this.children.push(...xs);}replaceChildren(...xs){this.children=xs;}showModal(){this.open=true;}close(){this.open=false;this.onclose?.();}}
const contract='{"version":1,"kind":"single","function":"fee","domains":{"x":{"min":0,"max":9007199254740993}},"properties":[{"id":"PROP-SAME","text":"保持原值","precondition":"True","assertion":"result == arg0"}],"seed":0,"max_cases":16,"excluded_inputs":[]}';
function page({project=false}={}){
 const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);},calls=[];
 const draft={id:'upload_a',status:'DRAFT',filename:'fee.cj',goal:'原样返回',version:1,source_sha256:'hash',functions:[{name:'fee',params:[{name:'x',type:'Int64'}],return_type:'Int64'}]};
 if(project)Object.assign(draft,{kind:'PROJECT',production_paths:['src/a.cj'],original_tests:[],original_manifest:{'src/a.cj':'a','cjpm.toml':'b'}});
 let transport=async(path,options)=>path==='/api/uploads/repair'&&!options.method?{uploads:[]}:path.endsWith('/confirm')?{...draft,status:'CONFIRMED'}:draft;
 const ctx={$:get,document:{createElement:()=>new Element()},flow:{running:false},starting:false,reviewBusy:false,csrf:'token',location:{origin:'http://localhost'},
  TextDecoder,crypto:require('node:crypto').webcrypto,FormData:class{append(){}},toast(){},selectCase:async()=>({}),setTimeout:()=>1,clearTimeout(){},
  fetch:async(path,options={})=>{calls.push([path,options]);return{ok:true,json:async()=>transport(path,options)};}};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync('nexus/demo/static/upload.js','utf8'),ctx);
 return{get,calls,draft,setApi(fn){transport=fn;}};
}
async function ready(p){await p.get('upload-open').onclick();p.get('upload-file').files=[{}];p.get('upload-goal').value='原样返回';await p.get('upload-prepare').onclick();}
function file(text){const bytes=Buffer.from(text);return{name:'properties.json',size:bytes.length,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)};}
function read(p,f){const input=p.get('upload-properties-file');input.files=f?[f]:[];assert.equal(typeof input.onchange,'function');return input.onchange({target:input});}
test('properties import allows16KiB, preserves exact Int64 text and needs explicit confirmation',async()=>{
 const p=page();await ready(p);p.get('upload-consent').checked=true;const text=' '.repeat(8500)+contract;
 await read(p,file(text));assert.equal(p.get('upload-properties').value,text);assert.equal(p.get('upload-consent').checked,false);
 assert.match(p.get('upload-properties-aliases').textContent,/arg0.*x.*result.*Int64/);
 const n=p.calls.length;await p.get('upload-confirm').onclick();assert.equal(p.calls.length,n);
 p.get('upload-consent').checked=true;await p.get('upload-confirm').onclick();
 const body=JSON.parse(p.calls.at(-1)[1].body);assert.equal(body.properties_json,text);assert.match(body.properties_json,/9007199254740993/);
});
test('bad cancelled and oversized property reads preserve the editor',async()=>{
 const p=page();await ready(p);p.get('upload-properties').value=contract;
 for(const f of [null,file('[]'),file('null'),file('{'),file(' '.repeat(16385)),{name:'bad.json',size:1,arrayBuffer:async()=>Uint8Array.from([255]).buffer}]){
  await read(p,f);assert.equal(p.get('upload-properties').value,contract);
 }
});
test('late property reads cannot restore old data after edit function source scope or close',async()=>{
 for(const change of ['edit','function','source','scope','close']){
  const p=page({project:change==='scope'});await ready(p);let resolve;
  const pending=read(p,{name:'slow.json',size:contract.length,arrayBuffer:()=>new Promise(r=>resolve=r)});
  assert.equal(p.get('upload-confirm').disabled,true);
  if(change==='edit'){p.get('upload-properties').value='manual';p.get('upload-properties').oninput();}
  if(change==='function')p.get('upload-function').onchange();
  if(change==='source')p.get('upload-file').onchange();
  if(change==='scope'){const input=p.get('upload-project-tree').children.flatMap(n=>n.children).find(n=>n.type==='checkbox');input.checked=false;input.onchange();}
  if(change==='close')p.get('upload-dialog').close();
  const before=p.get('upload-properties').value;resolve(new TextEncoder().encode(contract).buffer);await pending;
  assert.equal(p.get('upload-properties').value,before,change);
 }
});
test('existing no-property confirmation omits field and frozen records load property text read-only',async()=>{
 const p=page();await ready(p);p.get('upload-consent').checked=true;await p.get('upload-confirm').onclick();
 assert.ok(!('properties_json' in JSON.parse(p.calls.at(-1)[1].body)));
 await p.get('upload-open').onclick();p.setApi(async()=>({...p.draft,status:'CONFIRMED',properties_json:contract,examples_json:'[]'}));
 p.get('upload-recent').value=p.draft.id;await p.get('upload-recent').onchange();
 assert.equal(p.get('upload-properties').value,contract);assert.equal(p.get('upload-properties').disabled,true);
});
