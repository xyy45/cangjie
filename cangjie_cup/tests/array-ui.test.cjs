'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{constructor(){this.children=[];this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.open=false;this.files=[];this.textContent='';}append(...xs){this.children.push(...xs);}replaceChildren(...xs){this.children=xs;}showModal(){this.open=true;}close(){this.open=false;this.onclose?.();}}
const visible=n=>[n.textContent,...n.children.map(visible)].join(' ');
function ui(file,name){const ctx={document:{createElement:()=>new Element()}};vm.createContext(ctx);vm.runInContext(fs.readFileSync('nexus/demo/static/'+file+'.js','utf8')+'\nglobalThis.ui='+name+';',ctx);return ctx.ui;}
const candidate={id:'c',tree_hash:'tree',build_state:'PASS',test_state:'PASS'};
function upload(){
 const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);},calls=[];
 const draft={id:'upload_a',version:1,status:'DRAFT',filename:'a.cj',goal:'数组业务',source_sha256:'hash',functions:[{name:'total',params:[{name:'items',type:'Array<Int64>'},{name:'quantity',type:'Int64'},{name:'label',type:'String'},{name:'flag',type:'Bool'}],return_type:'Array<Int64>'}]};
 let response=async(path,options)=>path==='/api/uploads/repair'&&!options.method?{uploads:[]}:path.endsWith('/confirm')?{...draft,status:'CONFIRMED'}:draft;
 const ctx={$:get,document:{createElement:()=>new Element()},flow:{running:false},starting:false,reviewBusy:false,csrf:'token',location:{origin:'http://localhost'},TextDecoder,crypto:require('node:crypto').webcrypto,FormData:class{append(){}},toast(){},selectCase:async()=>({}),setTimeout:()=>1,clearTimeout(){},fetch:async(path,options={})=>{calls.push([path,options]);return{ok:true,json:async()=>response(path,options)};}};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync('nexus/demo/static/upload.js','utf8'),ctx);return{get,draft,calls,setApi(fn){response=fn;}};
}
async function ready(p){await p.get('upload-open').onclick();p.get('upload-file').files=[{}];p.get('upload-goal').value='数组业务';await p.get('upload-prepare').onclick();}
function file(name,text){const bytes=Buffer.from(text);return{name,size:bytes.length,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)};}
async function importing(p,kind,f){const node=p.get('upload-'+kind+'-file');node.files=[f];return node.onchange({target:node});}
test('Array scaffold uses an independent empty array and keeps expected unknown; help names readonly limits',async()=>{
 const p=upload();await ready(p);const examples=JSON.parse(p.get('upload-examples').value);assert.deepEqual(examples[0].args,[[],0,'',false]);assert.equal(examples[0].expected,null);
 examples[0].args[0].push(1);assert.deepEqual(examples[1].args[0],[]);
 assert.match(p.get('upload-source-help').textContent,/Array<Int64>/);assert.match(p.get('upload-source-help').textContent,/16/);assert.match(p.get('upload-source-help').textContent,/只读/);
});
test('Array imports keep exact raw nested Int64 JSON and all confirmed models readonly',async()=>{
 const p=upload();await ready(p);const raw='[{"args":[[-9223372036854775808,9223372036854775807],0,"中",false],"expected":[],"suite":"target"},{"args":[[],1,"",true],"expected":[1],"suite":"regression"}]';
 const models={oracle:'{"version":4,"function":"total","domains":{"items":{"values":[[],[9223372036854775807]]}}}',properties:'{"version":3,"kind":"single"}',relations:'{"version":3,"kind":"relation"}',sequences:'{"version":3,"kind":"sequence"}'};
 await importing(p,'examples',file('cases.json',raw));for(const [kind,text] of Object.entries(models))await importing(p,kind,file(kind+'.json',text));
 p.get('upload-consent').checked=true;await p.get('upload-confirm').onclick();const body=JSON.parse(p.calls.at(-1)[1].body);assert.equal(body.examples_json,raw);for(const [kind,text] of Object.entries(models))assert.equal(body[kind+'_json'],text);
 await p.get('upload-open').onclick();p.setApi(async()=>({...p.draft,status:'CONFIRMED',examples_json:raw,...Object.fromEntries(Object.entries(models).map(([k,v])=>[k+'_json',v]))}));p.get('upload-recent').value='upload_a';await p.get('upload-recent').onchange();
 assert.equal(p.get('upload-examples').value,raw);assert.equal(p.get('upload-examples').disabled,true);for(const [kind,text] of Object.entries(models)){assert.equal(p.get('upload-'+kind).value,text);assert.equal(p.get('upload-'+kind).disabled,true);}
});
test('Array delayed import cannot overwrite hand edits',async()=>{
 const p=upload();await ready(p);let resolve;const pending=importing(p,'examples',{name:'slow.json',size:2,arrayBuffer:()=>new Promise(r=>resolve=r)});p.get('upload-examples').value='manual Array';p.get('upload-examples').oninput();resolve(new TextEncoder().encode('[]').buffer);await pending;assert.equal(p.get('upload-examples').value,'manual Array');
});
test('Array property prefers server exact nested args and returns; unsafe fallback never rounds',()=>{
 const view=ui('properties','PropertyUI'),box=new Element(),report={candidate_id:'c',binding:{tree_hash:'tree'},state:'FAIL',failures:[{property_id:'PROP-A',property_text:'数组',args:[[9223372036854775807]],args_text:'[[9223372036854775807]]',actual_return:[9223372036854775807],actual_return_text:'[9223372036854775807]',assertion_value:false,expected_property:true}]};
 view.render(box,{}, {...candidate,properties:report},true);assert.match(visible(box),/9223372036854775807/);assert.doesNotMatch(visible(box),/9223372036854776000/);
 delete report.failures[0].args_text;delete report.failures[0].actual_return_text;view.render(box,{}, {...candidate,properties:report},true);assert.doesNotMatch(visible(box),/9223372036854776000/);assert.match(visible(box),/待核对/);
});
test('Array state and nested args use exact text, including empty state and real return prefix',()=>{
 const box=new Element(),view=ui('sequences','SequenceUI');view.renderPaths(box,[{initial_state:[],context:[[9223372036854775807]],context_text:'[[9223372036854775807]]',steps:[{step_index:0,args:[[9223372036854775807]],args_text:'[[9223372036854775807]]',before_state:[],actual_return:[9223372036854775807],actual_return_text:'[9223372036854775807]',expected_state:[]}]}]);
 const text=visible(box);assert.match(text,/初始状态.*\[\]/);assert.match(text,/前态.*\[\]/);assert.match(text,/实际返回.*9223372036854775807/);assert.doesNotMatch(text,/9223372036854776000|undefined/);
 const fallback=new Element();view.renderPaths(fallback,[{initial_state:[],context:[[9223372036854775807]],steps:[{args:[[9223372036854775807]]}]}]);assert.doesNotMatch(visible(fallback),/9223372036854776000/);
});
test('Array relation, Oracle and feedback do not round nested arguments without canonical text',()=>{
 const boxes=[new Element(),new Element(),new Element()],args=[[9223372036854775807]],binding={tree_hash:'tree'};
 ui('relations','RelationUI').render(boxes[0],{}, {...candidate,relations:{candidate_id:'c',binding,state:'FAIL',failures:[{left_args:args,right_args:args,left_actual_return:[],right_actual_return:[1]}]}},true);
 ui('exploration','ExplorationUI').render(boxes[1],{}, {...candidate,exploration:{candidate_id:'c',binding,state:'FAIL',failures:[{args,expected:'0',actual:'1'}]}},true);
 ui('feedback','FeedbackUI').render(boxes[2],{previous_candidate_id:'c',tree_hash:'tree',failure_cases:[{kind:'business_property',args,actual_return:args[0]}]},candidate);
 for(const box of boxes){assert.doesNotMatch(visible(box),/9223372036854776000/);assert.match(visible(box),/待核对/);}
});
test('Array current UNKNOWN overrides old PASS in all four views and keeps reject available',()=>{
 const js=fs.readFileSync('nexus/demo/static/demo.js','utf8'),start=js.indexOf('function validationCandidate('),end=js.indexOf('function renderRounds(',start);
 for(const [field,file,name] of [['exploration','exploration','ExplorationUI'],['properties','properties','PropertyUI'],['relations','relations','RelationUI'],['sequences','sequences','SequenceUI']]){
  const pass={candidate_id:'c',binding:{tree_hash:'tree',model:'array'},state:'PASS'},unknown={...pass,state:'UNKNOWN'};
  const ctx={current:{independent_rule:true,independent_properties:true,independent_relations:true,independent_sequences:true},realTask:{candidates:[{...candidate,[field]:unknown}]}};vm.createContext(ctx);vm.runInContext(js.slice(start,end)+'\nglobalThis.check=validationCandidate;',ctx);
  const result=ctx.check({...candidate,check_set_hash:'hash',[field]:pass});assert.equal(result.check_set_hash,null);assert.equal(result[field].state,'UNKNOWN');
  assert.equal(ui(file,name).roundState({events:[{candidate_id:'c',type:{exploration:'EXPLORATION_FINISHED',properties:'PROPERTY_FINISHED',relations:'RELATION_FINISHED',sequences:'SEQUENCE_FINISHED'}[field],[field]:pass}]},{...candidate,[field]:unknown},true),'pending');
 }
 const a=js.indexOf('function currentReview()'),b=js.indexOf('function validationCandidate(',a),ctx={mode:'real',roundLoading:false,realCandidate:{id:'c',is_current_review:true},realTask:{candidate_id:'c',status:'REVIEW_PENDING'},flow:{status:'IN_DOUBT'}};vm.createContext(ctx);vm.runInContext(js.slice(a,b)+'\nglobalThis.reject=canRejectCurrent;',ctx);assert.equal(ctx.reject(),true);
});
test('Array rule help names versions, finite array domains and checked helpers',()=>{
 const html=fs.readFileSync('nexus/demo/templates/demo.html','utf8');assert.match(html,/Array&lt;Int64&gt;|Array<Int64>/);assert.match(html,/version=4/);assert.match(html,/array_len/);assert.match(html,/array_at/);assert.match(html,/array_sum/);assert.match(html,/array_append/);assert.match(html,/array_replace/);
});
