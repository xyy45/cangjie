'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{
 constructor(){this.events=[];this.children=[];this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.open=false;this.files=[];this.textContent='';}
 dispatchEvent(event){this.events.push(event.type);}
 append(...xs){this.children.push(...xs);}replaceChildren(...xs){this.children=xs;}showModal(){this.open=true;}close(){this.open=false;this.onclose?.();}
}
function page(){
 const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};let transport=async()=>({uploads:[]});const calls=[],selections=[];
 const ctx={$:get,document:{createElement:()=>new Element()},flow:{running:false},starting:false,reviewBusy:false,csrf:'token',location:{origin:'http://localhost'},
  TextDecoder,Event,crypto:require('node:crypto').webcrypto,FormData:class{append(){}},toast(){},selectCase:async id=>{selections.push(id);return{id};},
  fetch:async(path,options)=>{calls.push([path,options]);const value=await transport(path,options);return {ok:!value.error,status:value.error?400:200,json:async()=>value};}};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync('nexus/demo/static/upload.js','utf8')+'\nglobalThis.ui=UploadUI;',ctx);
 return {get,calls,selections,setApi(fn){transport=fn;},ui:ctx.ui};
}
const draft={id:'upload_a',status:'DRAFT',filename:'fee.cj',goal:'计算费用',version:1,source_sha256:'hash',functions:[{name:'fee',params:[{name:'x',type:'Int64'}],return_type:'Int64'}]};
test('preparing a file leaves expected values unknown until user supplies examples',async()=>{
 const {get,setApi}=page();await get('upload-open').onclick();get('upload-file').files=[{}];get('upload-goal').value='计算费用';setApi(async()=>draft);
 await get('upload-prepare').onclick();const examples=JSON.parse(get('upload-examples').value);
 assert.equal(examples[0].expected,null);assert.equal(get('upload-function').children.length,1);
 assert.equal(get('upload-consent').checked,false);
});
test('confirmation requires consent and preserves exact JSON text then selects uploaded workspace',async()=>{
 const {get,calls,setApi,selections}=page();await get('upload-open').onclick();get('upload-file').files=[{}];get('upload-goal').value='计算费用';setApi(async()=>draft);await get('upload-prepare').onclick();
 const count=calls.length;await get('upload-confirm').onclick();assert.equal(calls.length,count);
 get('upload-consent').checked=true;get('upload-function').value='fee';get('upload-examples').value='[{"args":[9007199254740993],"expected":1,"suite":"target"}]';
 setApi(async()=>({...draft,status:'CONFIRMED'}));await get('upload-confirm').onclick();
 const body=JSON.parse(calls.at(-1)[1].body);assert.match(body.examples_json,/9007199254740993/);assert.equal(body.consent,true);
 assert.deepEqual(selections,['upload_a']);
});
test('closing a pending prepare prevents its late response from restoring a stale draft',async()=>{
 const {get,setApi}=page();await get('upload-open').onclick();get('upload-file').files=[{}];get('upload-goal').value='计算费用';let resolve;
 setApi(()=>new Promise(r=>resolve=r));const pending=get('upload-prepare').onclick();await new Promise(r=>setImmediate(r));get('upload-dialog').close();resolve(draft);await pending;
 assert.equal(get('upload-dialog').open,false);assert.equal(get('upload-confirm').disabled,true);
});

function file(name,text){const bytes=Buffer.from(text);return{name,size:bytes.length,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)};}
async function ready(p){await p.get('upload-open').onclick();p.get('upload-file').files=[{}];p.get('upload-goal').value='计算费用';p.setApi(async()=>draft);await p.get('upload-prepare').onclick();}
async function importing(p,kind,selected){const input=p.get('upload-'+kind+'-file');input.files=[selected];return input.onchange({target:input});}
test('text import fills the editable goal locally and refuses to replace a prepared goal',async()=>{
 const p=page();await p.get('upload-open').onclick();const count=p.calls.length;
 await importing(p,'goal',file('goal.md','数量必须大于0。'));
 assert.equal(p.get('upload-goal').value,'数量必须大于0。');assert.equal(p.calls.length,count);
 p.get('upload-file').files=[{}];p.setApi(async()=>draft);await p.get('upload-prepare').onclick();
 await importing(p,'goal',file('other.txt','different'));assert.equal(p.get('upload-goal').value,draft.goal);
});
test('JSON import preserves exact large integers through confirmation and resets consent',async()=>{
 const p=page();await ready(p);p.get('upload-consent').checked=true;
 const text='[\n {"args":[9007199254740993],"expected":9007199254740993,"suite":"target"},\n {"args":[2],"expected":2,"suite":"regression"}\n]';
 await importing(p,'examples',file('tests.json',text));
 assert.equal(p.get('upload-examples').value,text);assert.equal(p.get('upload-consent').checked,false);
 p.get('upload-consent').checked=true;p.setApi(async()=>({...draft,status:'CONFIRMED'}));await p.get('upload-confirm').onclick();
 assert.equal(JSON.parse(p.calls.at(-1)[1].body).examples_json,text);
});
test('bad extension, empty, oversized, malformed or non-UTF8 imports leave existing input untouched',async()=>{
 const p=page();await ready(p);const before=p.get('upload-examples').value;
 for(const selected of [file('bad.txt','[]'),file('bad.json',''),file('bad.json','{'),file('bad.json','{}'),file('big.json',' '.repeat(8193)),{name:'bad.json',size:1,arrayBuffer:async()=>Uint8Array.from([255]).buffer}]){
  await importing(p,'examples',selected);assert.equal(p.get('upload-examples').value,before);assert.ok(p.get('upload-status').textContent);
 }
});
test('late JSON reads cannot overwrite a manual edit, a function switch, source switch or a closed dialog',async()=>{
 for(const action of ['edit','function','source','close']){
  const p=page();await ready(p);let resolve;const pending=importing(p,'examples',{name:'slow.json',size:2,arrayBuffer:()=>new Promise(r=>resolve=r)});
  assert.equal(p.get('upload-confirm').disabled,true);
  if(action==='edit'){p.get('upload-examples').value='manual';p.get('upload-examples').oninput();}
  if(action==='function')p.get('upload-function').onchange();
  if(action==='source')p.get('upload-file').onchange();
  if(action==='close')p.get('upload-dialog').close();
  const before=p.get('upload-examples').value;resolve(new TextEncoder().encode('[]').buffer);await pending;
  assert.equal(p.get('upload-examples').value,before);
 }
});
test('a second import wins over a delayed first read and confirmed tests cannot be replaced',async()=>{
 const p=page();await ready(p);let resolve;
 const pending=importing(p,'examples',{name:'slow.json',size:2,arrayBuffer:()=>new Promise(r=>resolve=r)});
 await importing(p,'examples',file('current.json','[{"args":[2],"expected":2,"suite":"target"}]'));
 const value=p.get('upload-examples').value;resolve(new TextEncoder().encode('[]').buffer);await pending;assert.equal(p.get('upload-examples').value,value);
 p.get('upload-consent').checked=true;p.setApi(async()=>({...draft,status:'CONFIRMED',examples_json:value}));await p.get('upload-confirm').onclick();
 await importing(p,'examples',file('new.json','[]'));assert.equal(p.get('upload-examples').value,value);
});

test('independent rule import keeps exact JSON, resets consent and binds confirmation',async()=>{
 const p=page();await ready(p);p.get('upload-consent').checked=true;
 const text='{"version":1,"function":"fee","domains":{"x":{"min":0,"max":9223372036854775807}},"expression":"x","seed":0,"max_cases":32}';
 assert.equal(typeof p.get('upload-oracle-file').onchange,'function');
 await importing(p,'oracle',file('oracle.json',text));
 assert.equal(p.get('upload-oracle').value,text);assert.equal(p.get('upload-consent').checked,false);
 p.get('upload-consent').checked=true;p.setApi(async()=>({...draft,status:'CONFIRMED'}));await p.get('upload-confirm').onclick();
 assert.equal(JSON.parse(p.calls.at(-1)[1].body).oracle_json,text);
});

test('function changes invalidate stale rule import and require re-confirmation',async()=>{
 const p=page();await ready(p);assert.equal(typeof p.get('upload-oracle-file').onchange,'function');let resolve;
 const pending=importing(p,'oracle',{name:'slow.json',size:2,arrayBuffer:()=>new Promise(r=>resolve=r)});
 p.get('upload-function').onchange();resolve(new TextEncoder().encode('{}').buffer);await pending;
 assert.equal(p.get('upload-oracle').value,'');assert.equal(p.get('upload-consent').checked,false);
});

test('editing public examples preserves the independent rule and resets consent',async()=>{
 const p=page();await ready(p);p.get('upload-oracle').value='confirmed-rule';p.get('upload-consent').checked=true;
 p.get('upload-examples').oninput();assert.equal(p.get('upload-oracle').value,'confirmed-rule');assert.equal(p.get('upload-consent').checked,false);
});
test('manual rule edits invalidate an in-flight rule import and reset consent',async()=>{
 const p=page();await ready(p);let resolve;
 const pending=importing(p,'oracle',{name:'slow.json',size:2,arrayBuffer:()=>new Promise(r=>resolve=r)});
 assert.equal(typeof p.get('upload-oracle').oninput,'function');
 p.get('upload-consent').checked=true;p.get('upload-oracle').value='manual';p.get('upload-oracle').oninput();
 resolve(new TextEncoder().encode('{}').buffer);await pending;
 assert.equal(p.get('upload-oracle').value,'manual');assert.equal(p.get('upload-consent').checked,false);
});


test('blank expected behavior allows local function reading and can be imported afterward',async()=>{
 const p=page();await p.get('upload-open').onclick();p.get('upload-file').files=[{}];p.setApi(async()=>({...draft,goal:''}));
 await p.get('upload-prepare').onclick();
 assert.equal(p.get('upload-function').value,'fee');assert.equal(p.get('upload-goal').disabled,false);
 assert.deepEqual(p.get('upload-dialog').events,['upload-functions-loaded']);
 await importing(p,'goal',file('goal.md','数量乘以单价'));
 assert.equal(p.get('upload-goal').value,'数量乘以单价');
 p.get('upload-consent').checked=true;
 p.setApi(async path=>path.endsWith('/goal')?{...draft,goal:'数量乘以单价'}:{...draft,status:'CONFIRMED'});
 await p.get('upload-confirm').onclick();
 assert.equal(JSON.parse(p.calls.at(-2)[1].body).goal,'数量乘以单价');
 assert.ok(p.calls.at(-1)[0].endsWith('/confirm'));
});

test('source reading renders the backend cause in the status shared by all steps',async()=>{
 const p=page();await p.get('upload-open').onclick();p.get('upload-file').files=[{}];p.setApi(async()=>({error:'未找到支持的函数'}));
 await p.get('upload-prepare').onclick();
 assert.equal(p.get('upload-status').textContent,'未找到支持的函数');
 assert.deepEqual(p.get('upload-dialog').events,[]);
 const template=fs.readFileSync('nexus/demo/templates/demo.html','utf8');
 assert.match(template,/<\/section>\s*<p id="upload-status"[^>]+><\/p>\s*<div class="upload-wizard-nav">/);
});
