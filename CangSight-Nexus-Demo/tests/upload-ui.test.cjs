'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{
 constructor(){this.children=[];this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.open=false;this.files=[];this.textContent='';}
 append(...xs){this.children.push(...xs);}replaceChildren(...xs){this.children=xs;}showModal(){this.open=true;}close(){this.open=false;this.onclose?.();}
}
function page(){
 const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};let transport=async()=>({uploads:[]});const calls=[],selections=[];
 const ctx={$:get,document:{createElement:()=>new Element()},flow:{running:false},starting:false,reviewBusy:false,csrf:'token',location:{origin:'http://localhost'},
  crypto:require('node:crypto').webcrypto,FormData:class{append(){}},toast(){},selectCase:async id=>{selections.push(id);return{id};},
  fetch:async(path,options)=>{calls.push([path,options]);return {ok:true,json:async()=>transport(path,options)};}};
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
