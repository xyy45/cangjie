'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
class Element {
  constructor(){this.children=[];this.dataset={};this.className='';this.textContent='';this.value='1';this.namespaceURI='http://www.w3.org/2000/svg';this.classList={toggle(){}};}
  append(...items){this.children.push(...items);}
  replaceChildren(...items){this.children=[...items];}
  setAttribute(name,value){this[name]=value;}
  querySelector(){return new Element();}
  showModal(){}close(){}
}
function caseData(id='order'){
  return {id,project_id:id==='order'?'order-demo-bug':id,kind:id==='policy'?'probe':'repair',can_replay:true,title:id,category:id,requirement:'original',requirements:['数量边界','单价范围','总额计算'],limitations:[],files:[{path:'src/quantity.cj',before:'quantity >= 0',after:'quantity >= 1'}],metrics:{files:1,tests:11,candidates:1,tokens:0,seconds:null},stages:['a','b','c','d','e','f','g'],logs:[],source_label:'回放',origin:'LIVE_REPLAY',provider:'AI',verdict:id==='policy'?'DENY':'ALLOW'};
}
function setup(){
  const elements={};
  const get=id=>elements[id]??=(new Element());
  const ctx={document:{querySelector:()=>({content:'csrf'}),querySelectorAll:()=>[],getElementById:get,createElement:()=>new Element(),createElementNS:()=>new Element(),createTextNode:text=>({textContent:text})},localStorage:{getItem:()=>null,setItem(){},removeItem(){}},location:{origin:'http://localhost'},crypto:require('node:crypto').webcrypto,setTimeout:()=>1,clearTimeout(){},console};
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(root,'nexus/demo/static/flow.js'),'utf8'),ctx);
  vm.runInContext(fs.readFileSync(path.join(root,'nexus/demo/static/evidence-core.js'),'utf8'),ctx);
  vm.runInContext(fs.readFileSync(path.join(root,'nexus/demo/static/feedback.js'),'utf8'),ctx);
  const source=fs.readFileSync(path.join(root,'nexus/demo/static/demo.js'),'utf8').split("\ndocument.querySelectorAll('[data-view]').forEach(b=>b.onclick")[0];
  vm.runInContext(source+`\nglobalThis.review={startReal,reset,selectCase,setMode,loadRecord,pollReal,render,rejectCandidate,
    setApi(fn){api=fn;},setState(s){if(s.current!==undefined)current=s.current;if(s.mode!==undefined)mode=s.mode;if(s.realTask!==undefined)realTask=s.realTask;if(s.realCandidate!==undefined)realCandidate=s.realCandidate;if(s.realChecks!==undefined)realChecks=s.realChecks;if(s.flow!==undefined)Object.assign(flow,s.flow);},
    state(){return {mode,current,caseId,realTask,flow:{stage:flow.stage,status:flow.status,running:flow.running},downloadUrl,epoch,starting,history};}};`,ctx);
  const api=ctx.review;
  api.setState({current:caseData(),mode:'real'});
  return {api,elements,get};
}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
test('real startup blocks mode, case and reset before a task id exists',async()=>{
  const {api}=setup();let resolveEnvironment;const calls=[];
  api.setApi(async p=>{calls.push(p);if(p==='/demo/environment')return new Promise(r=>resolveEnvironment=r);if(p==='/api/requirements/drafts')return{id:'d',version:1};if(p.endsWith('/confirm'))return{id:'s'};if(p==='/agents/runs')return{id:'t',status:'READY'};if(p==='/api/tasks/t')return{id:'t',status:'REVIEW_PENDING',revision:1,events:[]};throw Error(p);});
  const pending=api.startReal();api.setMode('replay');await api.selectCase('policy');await api.reset();
  assert.equal(api.state().mode,'real');assert.equal(api.state().caseId,'order');
  resolveEnvironment({ready:true});await pending;await flush();
  assert.equal(calls.filter(p=>p==='/agents/runs').length,1);
  assert.equal(api.state().realTask.id,'t');
});
test('successful real cancellation clears running and returns to a reset workspace',async()=>{
  const {api}=setup();api.setState({realTask:{id:'t'},flow:{running:true,status:'RUNNING',stage:2}});
  api.setApi(async p=>p==='/demo/cases/order'?caseData():{id:'t',revision:2,status:p.endsWith('/cancel')?'CANCELLED':'GENERATING',events:[]});
  await api.reset();assert.equal(api.state().flow.running,false);assert.equal(api.state().flow.status,'READY');assert.equal(api.state().realTask,null);
});
test('late history selection cannot restore order delivery over the policy case',async()=>{
  const {api}=setup();api.setState({mode:'replay'});const deferred={};
  api.setApi(p=>new Promise(r=>deferred[p]=r));
  const a=api.loadRecord({caseId:'order',source:'回放',status:'DELIVERED',url:'/demo/download/order'});
  const b=api.loadRecord({caseId:'policy',source:'回放',status:'DENIED',url:''});
  deferred['/demo/cases/policy'](caseData('policy'));await b;
  deferred['/demo/cases/order'](caseData('order'));await a;
  assert.equal(api.state().caseId,'policy');assert.equal(api.state().flow.status,'DENIED');assert.equal(api.state().downloadUrl,'');
});
test('BUILDING does not mark unverified real requirements satisfied',()=>{
  const {api,get}=setup();api.setState({flow:{stage:4,status:'RUNNING',running:true},realTask:{id:'t',events:[]},realChecks:[],realCandidate:{requirement_results:[{id:'REQ-QTY',status:'UNKNOWN'},{id:'REQ-PRICE',status:'UNKNOWN'},{id:'REQ-TOTAL',status:'UNKNOWN'}]}});
  api.render();assert.equal(get('requirement-list').children.some(el=>el.className.split(/\s+/).includes('checked')),false);
});

test('revalidated candidate displays newest reports instead of obsolete unknown checks',()=>{
 const {api,get}=setup();
 api.setState({flow:{stage:5,status:'REVIEW_PENDING',running:false},realTask:{id:'t',candidate_id:'c',events:[]},
  realCandidate:{id:'c',is_current_review:true,check_set_hash:'hash',requirement_results:[]},
  realChecks:[{kind:'build',state:'UNKNOWN'},{kind:'test',state:'UNKNOWN',counts:{passed:0}},
   {kind:'build',state:'PASS'},{kind:'test',state:'PASS',counts:{passed:6},case_results:{'UploadedTests.case0':'PASS'}}]});
 api.render();
 assert.deepEqual(get('checks').children.map(row=>row.children[1].textContent),['通过','通过','通过']);
 assert.equal(get('test-list').children.length,1);
 assert.equal(get('metric-tests').children[0].textContent,'6');
});

test('new unknown or failed checks cannot inherit verified metrics from older passes',()=>{
 for(const state of ['UNKNOWN','FAIL']){
  const {api,get}=setup();api.setState({flow:{stage:5,status:'REVIEW_PENDING',running:false},realTask:{id:'t',events:[]},
   realCandidate:{id:'c',requirement_results:[]},realChecks:[{kind:'build',state:'PASS'},{kind:'test',state:'PASS',counts:{passed:6}},
    {kind:'build',state:'PASS'},{kind:'test',state,counts:{passed:5},case_results:{'UploadedTests.case0':'PASS'}}]});
  api.render();assert.equal(get('metric-tests').children[0].textContent,'—');assert.equal(get('test-list').children.length,0);
 }
});

test('real pending-review task is indexed so it survives workspace switches',async()=>{
  const {api}=setup();api.setState({realTask:{id:'pending-task'},flow:{running:true,status:'RUNNING',stage:4}});
  api.setApi(async()=>({id:'pending-task',status:'REVIEW_PENDING',revision:3,events:[]}));
  await api.pollReal(api.state().epoch);
  assert.equal(api.state().history[0].id,'pending-task');
  assert.equal(api.state().history[0].status,'REVIEW_PENDING');
});
test('an unexecuted or denied native policy does not appear allowed',()=>{
  const {api,get}=setup();api.setState({flow:{stage:3,status:'RUNNING',running:true},realTask:{id:'t',events:[]}});
  api.render();assert.equal(get('policy-verdict').children[1].textContent,'待检查');
  api.setState({realTask:{id:'t',events:[{policy:{request:{request_id:'denied',action:'candidate.apply'},decision:{decision:'Deny',policy_component_hash:'a'.repeat(64),policy_source_hash:'b'.repeat(64)}}}]},flow:{stage:3,status:'BLOCKED',running:false}});
  api.render();assert.equal(get('policy-verdict').children[1].textContent,'拒绝执行');
});

test('NeedApproval is amber approval state, never an Allow badge',()=>{
  const {api,get}=setup();api.setState({realTask:{id:'t',events:[{policy:{request:{request_id:'approval',action:'candidate.export'},decision:{decision:'NeedApproval',reason:'ACCEPTANCE_REQUIRED',policy_component_hash:'a'.repeat(64),policy_source_hash:'b'.repeat(64)}}}]},flow:{stage:5,status:'REVIEW_PENDING'}});
  api.render();assert.equal(get('policy-verdict').children[1].textContent,'需要审批');
  assert.equal(get('policy-verdict').className.includes('allowed'),false);
});

test('real rejection locks mode switching until its response is settled',async()=>{
  const {api}=setup();api.setState({realTask:{id:'t',candidate_id:'c'},realCandidate:{id:'c',is_current_review:true},flow:{running:false,status:'REVIEW_PENDING',stage:5}});
  let resolve;api.setApi(()=>new Promise(r=>resolve=r));
  const pending=api.rejectCandidate();api.setMode('replay');await api.selectCase('policy');
  assert.equal(api.state().mode,'real');assert.equal(api.state().caseId,'order');
  resolve({decision:'REJECT'});await pending;
  assert.equal(api.state().flow.status,'REJECTED');
});

test('new cases route generation to their registered project instead of the order fixture',async()=>{
  const {api}=setup();const sample=caseData('cross-stock');sample.can_replay=false;sample.project_id='cross-stock';api.setState({current:sample});const calls=[];
  api.setApi(async(p,body)=>{calls.push([p,body]);if(p==='/demo/environment')return {ready:true};if(p==='/api/requirements/drafts')return{id:'d',version:1};if(p.endsWith('/confirm'))return{id:'s'};if(p==='/agents/runs')return{id:'t'};return{id:'t',status:'REVIEW_PENDING',events:[]};});
  await api.startReal();await flush();assert.equal(calls.find(([p])=>p==='/api/requirements/drafts')[1].project,'cross-stock');assert.equal(calls.find(([p])=>p==='/agents/runs')[1].payload.project,'cross-stock');
});
test('policy probes never call the model repair run endpoint',async()=>{
  const {api}=setup();api.setState({current:caseData('policy')});const calls=[];
  api.setApi(async p=>{calls.push(p);if(p==='/demo/environment')return{ready:false,policy_ready:true};if(p.startsWith('/api/demo/probes/'))return{task_id:'p'};return{id:'p',status:'REJECTED',events:[{type:'NATIVE_PROBE',policy:{decision:{reason:'PROTECTED_PATH'}},mcp_status:'ERROR',baseline_unchanged:true,candidate_writes:0}]};});
  await api.startReal();await flush();assert.equal(api.state().flow.status,'DENIED');assert.equal(calls.includes('/agents/runs'),false);
});

test('historical failed round cannot be accepted or rejected',()=>{
  const {api,get}=setup();api.setState({realTask:{id:'t',candidate_id:'new',events:[],candidates:[{id:'old',attempt:1},{id:'new',attempt:2}]},realCandidate:{id:'old',check_set_hash:'old-hash',is_current_review:false},flow:{running:false,status:'REVIEW_PENDING',stage:5}});
  api.render();assert.equal(get('accept').disabled,true);assert.equal(get('reject').disabled,true);
});

test('late round selection cannot replace a newer selected round',async()=>{
  const {api,get}=setup();api.setState({realTask:{id:'t',candidate_id:'new',events:[],candidates:[{id:'old',attempt:1,build_state:'PASS',test_state:'FAIL'},{id:'new',attempt:2,build_state:'PASS',test_state:'PASS'}]},flow:{running:false,status:'REVIEW_PENDING',stage:5}});
  const deferred={};api.setApi(p=>new Promise(r=>deferred[p]=r));
  api.render();const first=get('cegis-rounds').children[0].onclick();
  const second=get('cegis-rounds').children[1].onclick();
  deferred['/api/candidates/new']({id:'new',checks:[],is_current_review:true,check_set_hash:'new-hash'});
  deferred['/api/demo/candidates/new']({edits:[]});await second;
  deferred['/api/candidates/old']({id:'old',checks:[],is_current_review:false});
  deferred['/api/demo/candidates/old']({edits:[]});await first;
  assert.equal(get('accept').disabled,false);
  assert.equal(get('cegis-rounds').children[1].getAttribute?.('aria-pressed')??get('cegis-rounds').children[1]['aria-pressed'],'true');
});


test('a fresh browser starts generation directly without pairing',async()=>{
  const {api}=setup();const calls=[];
  api.setApi(async p=>{calls.push(p);if(p==='/demo/environment')return {ready:true};if(p==='/api/requirements/drafts')return{id:'d',version:1};if(p.endsWith('/confirm'))return{id:'s'};if(p==='/agents/runs')return{id:'direct-task'};return{id:'direct-task',status:'REVIEW_PENDING',events:[]};});
  await api.startReal();await flush();
  assert.equal(api.state().realTask?.id,'direct-task');
  assert.equal(calls.includes('/api/operator/authorize'),false);
});
