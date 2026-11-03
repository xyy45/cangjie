'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{
 constructor(tag=''){this.tagName=tag;this.children=[];this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.open=false;this.files=[];this.textContent='';}
 append(...xs){this.children.push(...xs);}replaceChildren(...xs){this.children=xs;}showModal(){this.open=true;}close(){this.open=false;this.onclose?.();}
}
function page(){
 const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};let api=async()=>({uploads:[]});const calls=[];
 const ctx={$:get,document:{createElement:tag=>new Element(tag)},starting:false,reviewBusy:false,flow:{running:false},csrf:'token',location:{origin:'http://localhost'},TextDecoder,
  crypto:require('node:crypto').webcrypto,FormData:class{constructor(){this.fields=[];}append(...x){this.fields.push(x);}},selectCase:async id=>({id}),
  fetch:async(path,options)=>{calls.push([path,options]);return{ok:true,json:async()=>api(path,options)};}};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync('nexus/demo/static/upload.js','utf8'),ctx);
 return{get,calls,setApi(fn){api=fn;}};
}
const project={id:'upload_project',kind:'PROJECT',status:'DRAFT',filename:'billing.zip',source_sha256:'hash',version:1,goal:'跨文件订单修复',production_paths:['src/fee.cj','src/order.cj'],original_manifest:{'cjpm.toml':'a','src/fee.cj':'b','src/order.cj':'c','src/tests_test.cj':'d'},original_tests:[{id:'OrderTests.one'}],functions:[{name:'total',path:'src/order.cj',params:[{name:'x',type:'Int64'}],return_type:'Int64'}]};
async function ready(p){await p.get('upload-open').onclick();p.get('upload-mode').value='project';p.get('upload-mode').onchange();p.get('upload-file').files=[{name:'billing.zip',size:100}];p.get('upload-goal').value=project.goal;p.setApi(async()=>project);await p.get('upload-prepare').onclick();}
function inputs(node){return [node,...node.children.flatMap(inputs)].filter(n=>n.type==='checkbox');}

test('ZIP import uses project endpoint and displays original tree, functions and editable range',async()=>{
 const p=page();await ready(p);
 assert.equal(p.calls.at(-1)[0],'/api/uploads/repair/project');
 assert.equal(p.get('upload-project').hidden,false);assert.match(p.get('upload-project-summary').textContent,/2/);
 assert.equal(inputs(p.get('upload-project-tree')).length,2);
 assert.match(p.get('upload-function').children[0].textContent,/src\/order.cj/);
 p.get('upload-consent').checked=true;p.get('upload-function').value='total';p.get('upload-examples').value='[]';p.setApi(async()=>({...project,status:'CONFIRMED'}));await p.get('upload-confirm').onclick();
 assert.deepEqual(JSON.parse(p.calls.at(-1)[1].body).allowed_paths,['src/fee.cj','src/order.cj']);
});

test('directory import preserves browser-relative paths and excludes stale single file selection',async()=>{
 const p=page();await p.get('upload-open').onclick();p.get('upload-mode').value='directory';p.get('upload-mode').onchange();
 p.get('upload-file').files=[{name:'stale.cj'}];p.get('upload-directory').files=[{name:'cjpm.toml',webkitRelativePath:'billing/cjpm.toml'},{name:'fee.cj',webkitRelativePath:'billing/src/fee.cj'}];
 p.get('upload-goal').value=project.goal;p.setApi(async()=>project);await p.get('upload-prepare').onclick();
 const fields=p.calls.at(-1)[1].body.fields;assert.equal(p.calls.at(-1)[0],'/api/uploads/repair/project');
 assert.deepEqual(JSON.parse(fields.find(x=>x[0]==='paths_json')[1]),['billing/cjpm.toml','billing/src/fee.cj']);
 assert.equal(fields.filter(x=>x[0]==='files').length,2);assert.equal(fields.filter(x=>x[0]==='file').length,0);
});

test('mode changes invalidate late prepare and reset consent and project scope',async()=>{
 const p=page();await p.get('upload-open').onclick();p.get('upload-file').files=[{}];p.get('upload-goal').value=project.goal;let resolve;
 p.setApi(()=>new Promise(r=>resolve=r));const pending=p.get('upload-prepare').onclick();await new Promise(r=>setImmediate(r));
 p.get('upload-mode').value='project';p.get('upload-mode').onchange();resolve(project);await pending;
 assert.equal(p.get('upload-confirm').disabled,true);assert.equal(p.get('upload-consent').checked,false);assert.equal(p.get('upload-project').hidden,true);
});

test('changing editable scope revokes consent and no source files are pre-authorized beyond three',async()=>{
 const p=page();await ready(p);p.get('upload-consent').checked=true;const checks=inputs(p.get('upload-project-tree'));
 checks[0].checked=false;checks[0].onchange();assert.equal(p.get('upload-consent').checked,false);
 checks[1].checked=false;checks[1].onchange();p.get('upload-consent').checked=true;await p.get('upload-confirm').onclick();
 assert.match(p.get('upload-status').textContent,/1.*3/);
});
