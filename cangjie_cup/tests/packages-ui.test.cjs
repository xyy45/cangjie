'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{
 constructor(tag=''){this.tagName=tag;this.children=[];this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.open=false;this.files=[];this.textContent='';}
 append(...xs){this.children.push(...xs);}replaceChildren(...xs){this.children=xs;}showModal(){this.open=true;}close(){this.open=false;this.onclose?.();}
}
const text=node=>node.textContent+' '+node.children.map(text).join(' ');
function page(){
 const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};let reply={uploads:[]},ok=true;const calls=[];
 const context={$:get,document:{createElement:tag=>new Element(tag)},starting:false,reviewBusy:false,flow:{running:false},csrf:'fixture',location:{origin:'http://localhost'},TextDecoder,
  crypto:require('node:crypto').webcrypto,FormData:class{append(){}},selectCase:async id=>({id}),
  fetch:async(path,options)=>{calls.push([path,options]);return {ok,json:async()=>reply};}};
 vm.createContext(context);vm.runInContext(fs.readFileSync('nexus/demo/static/upload.js','utf8'),context);
 return {get,calls,setReply(value,success=true){reply=value;ok=success;}};
}
const project={id:'upload_packages',kind:'PROJECT',status:'DRAFT',filename:'scoped.zip',source_sha256:'a'.repeat(64),version:1,goal:'跨包修复',
 production_paths:['src/a.cj','src/b/same.cj'],original_manifest:{'cjpm.toml':'a','src/a.cj':'b','src/b/same.cj':'c'},original_tests:[],allowed_paths:['src/a.cj'],
 project_index:{version:2,graph_hash:'b'.repeat(64),packages:{bench:{},'bench.b':{}},dependency_graph:{version:1,packages:['bench','bench.b'],production_edges:[['bench','bench.b']],test_edges:[],
  imports:[{path:'src/a.cj',line:2,specifier:'bench.b.same',alias:'cost',kind:'symbol',origin:'WORKSPACE',target_package:'bench.b'}],topological_order:['bench.b','bench']}},
 functions:[{name:'bench.same',path:'src/a.cj',params:[{name:'n',type:'Int64'}],return_type:'Int64'},
 {name:'bench.b.same',path:'src/b/same.cj',params:[{name:'n',type:'Int64'}],return_type:'Int64'}]};
async function ready(p,value=project){await p.get('upload-open').onclick();p.get('upload-mode').value='project';p.get('upload-mode').onchange();p.get('upload-file').files=[{name:'scoped.zip'}];p.get('upload-goal').value=value.goal;p.setReply(value);await p.get('upload-prepare').onclick();}
function checks(node){return [node,...node.children.flatMap(checks)].filter(n=>n.type==='checkbox');}

test('package-local same names remain canonical and frozen graph is source-origin only',async()=>{
 const p=page();await ready(p,{...project,compiler_state:'PASS'});
 assert.deepEqual(p.get('upload-function').children.map(n=>n.value),['bench.same','bench.b.same']);
 assert.equal(p.get('upload-packages').hidden,false);
 assert.match(p.get('upload-package-origin').textContent,/源码声明依赖/);
 assert.doesNotMatch(p.get('upload-package-origin').textContent,/已通过|编译器确认/);
 assert.equal(p.get('upload-package-hash').textContent,'b'.repeat(64));
 assert.match(text(p.get('upload-package-graph')),/bench\s*→\s*bench.b/);
 assert.match(text(p.get('upload-package-imports')),/src\/a.cj:2.*bench.b.same.*cost/);
 assert.match(text(p.get('upload-project-tree')),/只读依赖/);
 const inputs=checks(p.get('upload-project-tree'));inputs[1].checked=true;inputs[1].onchange();
 assert.match(text(p.get('upload-project-tree')),/允许修改正文/);
});

test('canonical function selection and exact Int64 JSON text cross the confirmation boundary unchanged',async()=>{
 const p=page();await ready(p);const selected=checks(p.get('upload-project-tree')).find(n=>n.value==='src/b/same.cj');selected.checked=true;selected.onchange();p.get('upload-function').value='bench.b.same';p.get('upload-function').onchange();
 const examples='[ {"args":[9223372036854775807],"expected":9223372036854775807,"suite":"target"}, {"args":[-9223372036854775808],"expected":-9223372036854775808,"suite":"regression"} ]';
 p.get('upload-examples').value=examples;p.get('upload-consent').checked=true;p.setReply({...project,status:'CONFIRMED'});
 await p.get('upload-confirm').onclick();const body=JSON.parse(p.calls.at(-1)[1].body);
 assert.equal(body.function,'bench.b.same');assert.equal(body.examples_json,examples);
 assert.equal('scope' in body,false);assert.equal('graph_hash' in body,false);
});

test('legacy uploads hide package graph and switching sources removes stale scope',async()=>{
 const p=page();await ready(p);p.get('upload-mode').value='single';p.get('upload-mode').onchange();
 assert.equal(p.get('upload-packages').hidden,true);assert.equal(p.get('upload-consent').checked,false);
 const flat={...project,project_index:{version:1}};await ready(p,flat);assert.equal(p.get('upload-packages').hidden,true);
});

test('server validation errors preserve canonical selection, input JSON and unconfirmed scope',async()=>{
 const p=page();await ready(p);p.get('upload-function').value='bench.same';p.get('upload-examples').value='[]';p.get('upload-consent').checked=true;
 p.setReply({error:'预期值类型或测试分组无效'},false);await p.get('upload-confirm').onclick();
 assert.match(p.get('upload-status').textContent,/预期值类型/);assert.equal(p.get('upload-function').value,'bench.same');assert.equal(p.get('upload-examples').value,'[]');
});
