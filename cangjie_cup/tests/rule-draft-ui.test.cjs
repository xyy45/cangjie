'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{constructor(){this.children=[];this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.open=false;this.files=[];this.textContent='';this.dataset={};}append(...xs){this.children.push(...xs);}replaceChildren(...xs){this.children=xs;}showModal(){this.open=true;}close(){this.open=false;this.onclose?.();}}
const examples='[{"args":[9007199254740993],"expected":9007199254740993,"suite":"target"},{"args":[1],"expected":1,"suite":"regression"}]';
const oracle='{"version":1,"function":"fee","domains":{"x":{"min":0,"max":9223372036854775807}},"expression":"x","seed":0,"max_cases":32}';
function page({state='SUCCEEDED',contentStatus='DRAFT_READY',project=false,goal='原样返回输入'}={}){
 const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};const calls=[];
 const upload={id:'upload_a',status:'DRAFT',filename:'fee.cj',goal,version:1,source_sha256:'sourcehash',functions:[{name:'fee',params:[{name:'x',type:'Int64'}],return_type:'Int64'}]};
 if(project)Object.assign(upload,{kind:'PROJECT',production_paths:['src/a.cj','src/b.cj'],original_tests:[],original_manifest:{'src/a.cj':'a','src/b.cj':'b','cjpm.toml':'c'}});
 const job={id:'rd_a',upload_id:upload.id,call_state:state,binding:{upload_id:upload.id,upload_version:1,source_sha256:'sourcehash',signature:{name:'fee'},allowed_paths:project?['src/a.cj','src/b.cj']:['src/uploaded.cj']},result:state==='SUCCEEDED'?{status:contentStatus,business_verified:false,examples_json:examples,oracle_json:contentStatus==='DRAFT_READY'?oracle:null,reason:contentStatus==='EXAMPLES_READY'?'独立规则校验未通过':null,suggestion:{summary:'模型草案，需业务核对',assumptions:['x的输入域需核对'],questions:contentStatus==='NEEDS_CLARIFICATION'?['需要明确边界']:[]}}:null};
 const defaults=async(path,options={})=>{
  if(path==='/api/uploads/repair')return options.method==='POST'?upload:{uploads:[]};
  if(path.endsWith('/goal'))return {...upload,goal:JSON.parse(options.body).goal};
  if(path.endsWith('/rule-drafts'))return options.method==='POST'?{id:'rd_a',call_state:'CREATED'}:{jobs:[job]};
  if(path.endsWith('/apply-preview')){
   const only=JSON.parse(options.body).examples_only===true;
   return {examples_json:examples,oracle_json:only?null:oracle,rule_draft_ref:{id:'rd_a',binding_hash:'bound',result_sha256:'result',...(only?{examples_only:true}:{})},business_verified:false};
  }
  if(path.endsWith('/confirm'))return {...upload,status:'CONFIRMED'};
  if(path.endsWith('/rd_a'))return job;
  return upload;
 };
 let api=defaults;
 const ctx={$:get,document:{createElement:()=>new Element()},flow:{running:false},starting:false,reviewBusy:false,csrf:'csrf',location:{origin:'http://localhost'},TextDecoder,crypto:require('node:crypto').webcrypto,FormData:class{append(){}},toast(){},selectCase:async id=>({id}),setTimeout:()=>1,clearTimeout(){},
 fetch:async(path,options={})=>{calls.push({path,...options});return{ok:true,json:async()=>api(path,options)};}};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync('nexus/demo/static/upload.js','utf8'),ctx);
 return{get,calls,upload,job,setApi(fn){api=fn;},defaults};
}
async function ready(p){await p.get('upload-open').onclick();p.get('upload-file').files=[{}];p.get('upload-goal').value='原样返回输入';await p.get('upload-prepare').onclick();p.get('upload-function').value='fee';}
async function generate(p){p.get('upload-draft-consent').checked=true;await p.get('upload-draft-generate').onclick();}

test('separate draft transmission consent is required and generation never overwrites user inputs',async()=>{
 const p=page();await ready(p);p.get('upload-examples').value='manual examples';p.get('upload-oracle').value='manual oracle';p.get('upload-consent').checked=true;
 assert.equal(typeof p.get('upload-draft-generate').onclick,'function');const before=p.calls.length;await p.get('upload-draft-generate').onclick();assert.equal(p.calls.length,before);
 await generate(p);
 const sent=p.calls.find(c=>c.path.endsWith('/rule-drafts')&&c.method==='POST');assert.equal(JSON.parse(sent.body).consent,true);
 assert.equal(p.get('upload-examples').value,'manual examples');assert.equal(p.get('upload-oracle').value,'manual oracle');
 assert.equal(p.get('upload-draft-preview').hidden,false);assert.equal(p.get('upload-consent').checked,false);
 assert.match(p.get('upload-draft-status').textContent,/草案|核对/);
});

test('explicit application preserves exact Int64 JSON and still requires repair confirmation',async()=>{
 const p=page();await ready(p);p.get('upload-properties').value='manual properties';p.get('upload-relations').value='manual relations';await generate(p);await p.get('upload-draft-apply').onclick();await p.get('upload-draft-apply').onclick();
 assert.equal(p.get('upload-properties').value,'manual properties');
 assert.equal(p.get('upload-relations').value,'manual relations');
 assert.equal(p.get('upload-examples').value,examples);assert.equal(p.get('upload-oracle').value,oracle);assert.equal(p.get('upload-consent').checked,false);
 p.get('upload-examples').oninput();p.get('upload-consent').checked=true;await p.get('upload-confirm').onclick();
 const body=JSON.parse(p.calls.find(c=>c.path.endsWith('/confirm')).body);assert.equal(body.rule_draft_ref.id,'rd_a');assert.equal(body.examples_json,examples);
});

test('first replacement click preserves editors and requires a second explicit click',async()=>{
 const p=page();await ready(p);await generate(p);const before=p.get('upload-examples').value;await p.get('upload-draft-apply').onclick();
 assert.equal(p.get('upload-examples').value,before);assert.equal(p.calls.some(c=>c.path.endsWith('/apply-preview')),false);
 assert.equal(p.get('upload-draft-apply').textContent,'确认替换并填入');
 await p.get('upload-draft-apply').onclick();assert.equal(p.get('upload-examples').value,examples);
 assert.equal(p.calls.filter(c=>c.path.endsWith('/apply-preview')).length,1);
});

test('unanswered business questions cannot be applied',async()=>{
 const p=page({contentStatus:'NEEDS_CLARIFICATION'});await ready(p);await generate(p);const before=p.calls.length;
 assert.equal(p.get('upload-draft-apply').disabled,true);await p.get('upload-draft-apply').onclick();assert.equal(p.calls.length,before);
 assert.match(p.get('upload-draft-questions').textContent,/明确边界/);
});

test('unknown requests offer read-only lookup rather than regeneration',async()=>{
 const p=page({state:'IN_DOUBT'});await ready(p);await generate(p);
 assert.equal(p.get('upload-draft-generate').disabled,true);const before=p.calls.filter(c=>c.method==='POST').length;
 await p.get('upload-draft-generate').onclick();await p.get('upload-draft-query').onclick();
 assert.equal(p.calls.filter(c=>c.method==='POST').length,before);assert.match(p.get('upload-draft-status').textContent,/核实|未知/);
});

test('draft generation and preview do not survive stale source/function/edit/dialog epochs',async()=>{
 for(const action of ['source','function','edit','close','paths']){
  const p=page({project:action==='paths'});await ready(p);let resolve;
  p.setApi((path,options)=>path.endsWith('/rule-drafts')&&options.method==='POST'?new Promise(r=>resolve=r):p.defaults(path,options));
  p.get('upload-draft-consent').checked=true;const pending=p.get('upload-draft-generate').onclick();await new Promise(r=>setImmediate(r));
  if(action==='source')p.get('upload-file').onchange();
  if(action==='function'){p.get('upload-function').value='other';p.get('upload-function').onchange();}
  if(action==='edit'){p.get('upload-examples').value='manual changed';p.get('upload-examples').oninput();}
  if(action==='close')p.get('upload-dialog').close();
  if(action==='paths'){const input=p.get('upload-project-tree').children.flatMap(row=>row.children).find(node=>node.type==='checkbox');assert.ok(input);input.checked=false;input.onchange();}
  const before=p.get('upload-examples').value;resolve({id:'rd_a',call_state:'CREATED'});await pending;
  assert.equal(p.get('upload-examples').value,before,action);assert.equal(p.get('upload-draft-preview').hidden,true,action);
 }
});

test('a late polling response cannot restore a draft after a manual edit',async()=>{
 const p=page();await ready(p);let resolve;
 p.setApi((path,options)=>path.endsWith('/rd_a')?new Promise(r=>resolve=r):p.defaults(path,options));
 p.get('upload-draft-consent').checked=true;const pending=p.get('upload-draft-generate').onclick();await new Promise(r=>setImmediate(r));
 p.get('upload-examples').value='user newer content';p.get('upload-examples').oninput();resolve(p.job);await pending;
 assert.equal(p.get('upload-examples').value,'user newer content');assert.equal(p.get('upload-draft-preview').hidden,true);
});

test('editing after arming replacement invalidates the pending application',async()=>{
 const p=page();await ready(p);await generate(p);await p.get('upload-draft-apply').onclick();
 p.get('upload-examples').value='new manual input';p.get('upload-examples').oninput();
 await p.get('upload-draft-apply').onclick();
 assert.equal(p.get('upload-examples').value,'new manual input');assert.equal(p.calls.some(c=>c.path.endsWith('/apply-preview')),false);
});


test('valid tests can fill without an independent rule and preserve a manual rule',async()=>{
 const p=page({contentStatus:'EXAMPLES_READY'});await ready(p);p.get('upload-oracle').value='manual rule';await generate(p);
 const button=p.get('upload-draft-apply-examples');
 assert.equal(p.get('upload-draft-apply').hidden,true);assert.equal(button.disabled,false);
 assert.equal(p.get('upload-draft-examples-preview').value,examples);
 assert.match(p.get('upload-draft-status').textContent,/测试用例已生成.*独立规则校验未通过/);
 await button.onclick();await button.onclick();
 assert.equal(p.get('upload-examples').value,examples);
 assert.equal(p.get('upload-oracle').value,'manual rule');
 const body=JSON.parse(p.calls.find(c=>c.path.endsWith('/apply-preview')).body);assert.equal(body.examples_only,true);
});

test('replacement confirmation is specific to the selected action',async()=>{
 const p=page();await ready(p);await generate(p);
 const only=p.get('upload-draft-apply-examples'),both=p.get('upload-draft-apply');
 assert.equal(only.disabled,false);assert.equal(both.disabled,false);
 await only.onclick();await both.onclick();
 assert.equal(p.calls.some(c=>c.path.endsWith('/apply-preview')),false);
 await both.onclick();assert.equal(p.get('upload-oracle').value,oracle);
});


test('model generation binds the newly entered goal before dispatching',async()=>{
 const p=page({goal:''});await ready(p);
 p.get('upload-draft-consent').checked=true;
 const before=p.calls.length;await p.get('upload-draft-generate').onclick();
 assert.equal(p.calls.length,before);
 assert.match(p.get('upload-draft-status').textContent,/填写预期行为/);
 p.get('upload-goal').value='原样返回输入';p.get('upload-goal').oninput();
 await generate(p);
 const requests=p.calls.slice(before).filter(c=>c.method==='POST');
 assert.equal(requests.length,2);
 assert.ok(requests[0].path.endsWith('/goal'));
 assert.equal(JSON.parse(requests[0].body).goal,'原样返回输入');
 assert.ok(requests[1].path.endsWith('/rule-drafts'));
 assert.equal(p.get('upload-goal').disabled,true);
});
