'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{constructor(){this.children=[];this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.open=false;this.files=[];this.textContent='';}append(...xs){this.children.push(...xs);}replaceChildren(...xs){this.children=xs;}showModal(){this.open=true;}close(){this.open=false;this.onclose?.();}}
const visible=n=>[n.textContent,...n.children.map(visible)].join(' ');
function ui(file,name){const ctx={document:{createElement:()=>new Element()}};vm.createContext(ctx);vm.runInContext(fs.readFileSync('nexus/demo/static/'+file+'.js','utf8')+'\nglobalThis.ui='+name+';',ctx);return ctx.ui;}
const candidate={id:'c',tree_hash:'tree',build_state:'PASS',test_state:'PASS'};
function upload(){
 const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);},calls=[];
 const draft={id:'upload_s',version:1,status:'DRAFT',filename:'s.cj',goal:'String业务',source_sha256:'hash',functions:[{name:'ticket',params:[{name:'text',type:'String'},{name:'quantity',type:'Int64'},{name:'flag',type:'Bool'}],return_type:'String'}]};
 let response=async(path,options)=>path==='/api/uploads/repair'&&!options.method?{uploads:[]}:path.endsWith('/confirm')?{...draft,status:'CONFIRMED'}:draft;
 const ctx={$:get,document:{createElement:()=>new Element()},flow:{running:false},starting:false,reviewBusy:false,csrf:'token',location:{origin:'http://localhost'},TextDecoder,crypto:require('node:crypto').webcrypto,FormData:class{append(){}},toast(){},selectCase:async()=>({}),setTimeout:()=>1,clearTimeout(){},fetch:async(path,options={})=>{calls.push([path,options]);return{ok:true,json:async()=>response(path,options)};}};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync('nexus/demo/static/upload.js','utf8'),ctx);return{get,draft,calls,setApi(fn){response=fn;}};
}
async function ready(p){await p.get('upload-open').onclick();p.get('upload-file').files=[{}];p.get('upload-goal').value='String业务';await p.get('upload-prepare').onclick();}
function file(name,text){const bytes=Buffer.from(text);return{name,size:bytes.length,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)};}
async function importing(p,kind,f){const node=p.get('upload-'+kind+'-file');node.files=[f];return node.onchange({target:node});}
test('String scaffold uses empty argument and leaves expected unknown; help gives precise length limits',async()=>{
 const p=upload();await ready(p);const examples=JSON.parse(p.get('upload-examples').value);assert.deepEqual(examples[0].args,['',0,false]);assert.equal(examples[0].expected,null);
 assert.match(p.get('upload-source-help').textContent,/String/);assert.match(p.get('upload-source-help').textContent,/256/);assert.match(p.get('upload-source-help').textContent,/UTF-8/);
});
test('String imports preserve raw control and Int64 JSON text and confirmed values remain read-only',async()=>{
 const p=upload();await ready(p);const raw='[{"args":["中\\u0000",9223372036854775807,false],"expected":"","suite":"target"},{"args":["",0,true],"expected":"中","suite":"regression"}]';
 const model='{"version":3,"function":"ticket","domains":{"text":{"values":["","中"]}},"excluded_inputs":[]}';
 await importing(p,'examples',file('cases.json',raw));await importing(p,'oracle',file('oracle.json',model));p.get('upload-consent').checked=true;await p.get('upload-confirm').onclick();const body=JSON.parse(p.calls.at(-1)[1].body);assert.equal(body.examples_json,raw);assert.equal(body.oracle_json,model);
 await p.get('upload-open').onclick();p.setApi(async()=>({...p.draft,status:'CONFIRMED',examples_json:raw,oracle_json:model}));p.get('upload-recent').value='upload_s';await p.get('upload-recent').onchange();assert.equal(p.get('upload-examples').value,raw);assert.equal(p.get('upload-oracle').value,model);assert.equal(p.get('upload-examples').disabled,true);
});
test('delayed String import cannot overwrite later hand edit',async()=>{
 const p=upload();await ready(p);let resolve;const pending=importing(p,'examples',{name:'slow.json',size:2,arrayBuffer:()=>new Promise(r=>resolve=r)});p.get('upload-examples').value='manual String';p.get('upload-examples').oninput();resolve(new TextEncoder().encode('[]').buffer);await pending;assert.equal(p.get('upload-examples').value,'manual String');
});
test('Oracle observation feedback displays actual String args, quoted empty and observed provenance',()=>{
 const f={kind:'independent_rule',test_id:'NexusOracleV2.case0',args:['中',9223372036854775806],args_text:'["中",9223372036854775806]',expected:'"中"',actual:'""',actual_return:'',expected_value:'中',requirement_refs:['REQ-UPLOAD'],source:{log_ref:'records/string.log'}};
 const box=new Element();ui('feedback','FeedbackUI').render(box,{previous_candidate_id:'c',tree_hash:'tree',failure_cases:[f]},candidate);const text=visible(box);assert.match(text,/输入.*\["中",9223372036854775806\]/);assert.match(text,/实际结果.*""/);assert.match(text,/真实返回|实际返回|返回观测/);assert.doesNotMatch(text,/首条.*相等断言/);
});
test('String property and pair values remain quoted text, including HTML-shaped data',()=>{
 const box=new Element(),prop=ui('properties','PropertyUI'),data='<img src=x onerror=alert(1)>\n中';
 prop.render(box,{}, {...candidate,properties:{candidate_id:'c',binding:{tree_hash:'tree'},state:'FAIL',failures:[{property_id:'PROP-S',property_text:data,args:[''],actual_return:'',assertion_value:false,expected_property:true}]}},true);
 assert.match(visible(box),/实际返回.*""/);assert.match(visible(box),/<img/);assert.equal(box.children.some(n=>n.innerHTML!==undefined),false);
});
test('String sequence distinguishes empty state from missing, preserves control and exact numeric context',()=>{
 const box=new Element(),seq=ui('sequences','SequenceUI');seq.renderPaths(box,[{initial_state:'',context:['',9223372036854775806],context_text:'["",9223372036854775806]',test_id:'case',steps:[{step_index:0,before_state:'',actual_return:'\u0000\n中',expected_state:'中',args:[''],test_id:'case'}]}]);const text=visible(box);assert.match(text,/初始状态.*""/);assert.match(text,/实际返回.*\\u0000\\n中/);assert.match(text,/9223372036854775806/);assert.doesNotMatch(text,/9223372036854776000|undefined/);
});
test('current Oracle UNKNOWN overrides historical event PASS, and PASS needs a verified detail',()=>{
 const view=ui('exploration','ExplorationUI'),box=new Element(),pass={candidate_id:'c',binding:{tree_hash:'tree'},state:'PASS',public_test_state:'PASS'},task={events:[{type:'EXPLORATION_FINISHED',candidate_id:'c',exploration:pass}]};
 view.render(box,task,{...candidate,exploration:{...pass,state:'UNKNOWN',reason:'原件变化'}},true);assert.doesNotMatch(visible(box),/搜索通过|undefined/);assert.equal(view.roundState(task,{...candidate,exploration:{...pass,state:'UNKNOWN'}},true),'pending');
 assert.equal(view.roundState(task,candidate,true),'pending');assert.equal(view.roundState(task,{...candidate,exploration:pass},true),'passed');
});
test('String Oracle precise args prefer server canonical text',()=>{
 const view=ui('exploration','ExplorationUI'),box=new Element(),report={candidate_id:'c',binding:{tree_hash:'tree'},state:'FAIL',failures:[{args:['中',9223372036854775806],args_text:'["中",9223372036854775806]',actual:'""',expected:'"中"'}]};
 view.render(box,{}, {...candidate,exploration:report},true);assert.match(visible(box),/9223372036854775806/);assert.doesNotMatch(visible(box),/9223372036854776000/);
});
test('current Oracle summary and detail mismatch disables acceptance',()=>{
 const js=fs.readFileSync('nexus/demo/static/demo.js','utf8'),start=js.indexOf('function validationCandidate('),end=js.indexOf('function renderRounds(',start),ctx={current:{independent_rule:true},realTask:{candidates:[{...candidate,exploration:{candidate_id:'c',binding:{tree_hash:'tree'},state:'UNKNOWN'}}]}};
 vm.createContext(ctx);vm.runInContext(js.slice(start,end)+'\nglobalThis.check=validationCandidate;',ctx);const r=ctx.check({...candidate,check_set_hash:'valid',exploration:{candidate_id:'c',binding:{tree_hash:'tree'},state:'PASS'}});assert.equal(r.check_set_hash,null);assert.equal(r.exploration.state,'UNKNOWN');
});
test('rule help names String expression helpers and versioned finite domains',()=>{
 const html=fs.readFileSync('nexus/demo/templates/demo.html','utf8');assert.match(html,/byte_len/);assert.match(html,/rune_len/);assert.match(html,/values/);assert.match(html,/version=3/);
});
