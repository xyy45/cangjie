// Controlled DOM/network fixtures test the shipped JS; no model/SDK results are fabricated.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../nexus/web/static/workbench.js'), 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));

function page() {
  const elements = new Map();
  function textElement() {
    return {textContent:'',children:[],appendChild(child){this.children.push(child);this.textContent+=child.textContent;},
      addEventListener(name,handler){this[name]=handler;}};
  }
  const element = id => {
    if (!elements.has(id)) elements.set(id, {...textElement(), hidden:true, disabled:false,
      value:id === 'project' ? 'order-demo-bug' : 'fix',
      addEventListener(name, handler) { this[name] = handler; }});
    return elements.get(id);
  };
  const requests = [], timers = new Map();
  let nextTimer = 0;
  const context = vm.createContext({
    document:{getElementById:element, createElement:textElement, querySelector:()=>({content:'csrf'})},
    location:{origin:'http://127.0.0.1:8765'},
    localStorage:{getItem:()=> 'old', setItem() {}},
    crypto:{randomUUID:()=> 'start-key'},
    setTimeout(fn) { timers.set(++nextTimer,fn); return nextTimer; },
    clearTimeout(id) { timers.delete(id); },
    fetch(url, options) {
      if (url==='/api/tasks' && !options.method) return Promise.resolve({ok:true,json:async()=>({tasks:[]})});
      if (url==='/api/environment') return Promise.resolve({ok:true,json:async()=>({ready:true,missing:[]})});
      return new Promise(resolve => requests.push({url,options,resolve}));
    }
  });
  vm.runInContext(source, context);
  function take(url) {
    const index = requests.findIndex(r=>r.url===url);
    assert.notEqual(index,-1,`request missing: ${url}`);
    return requests.splice(index,1)[0];
  }
  async function reply(request, data, ok=true) {
    request.resolve({ok,json:async()=>data});
    await tick();
  }
  return {element,requests,timers,take,reply,refresh:()=>vm.runInContext('refresh()',context),
    prepare:()=>element('repair-form').submit({preventDefault(){}}),
    confirm:()=>element('start').click(),
    start:()=>{
      vm.runInContext("requirementDraft={id:'draft',project_id:'order-demo-bug',allowed_paths:['src/a.cj']}; confirmedSpec={id:'spec'}; environmentReady=true",context);
      return element('start').click();
    }};
}
function task(id,candidate_id=null,status='REVIEW_PENDING') {
  return {id,candidate_id,status,attempt_count:1,events:[],baseline_checks:[],download_url:null};
}
function candidate(id) {
  return {id,diff:'diff '+id,checks:[{kind:'test',state:'PASS',diagnostics:id}],check_set_hash:'hash-'+id};
}

test('late task response cannot overwrite a newly started task',async()=>{
  const p=page(), old=p.take('/api/tasks/old');
  const started=p.start();
  await p.reply(p.take('/agents/runs'),{id:'new'});
  await p.reply(p.take('/api/tasks/new'),task('new','new-candidate'));
  await p.reply(p.take('/api/candidates/new-candidate'),candidate('new-candidate'));
  await started;
  await p.reply(old,task('old',null,'BLOCKED'));
  assert.equal(p.element('phase').textContent,'等待审阅');
  assert.equal(p.element('diff').textContent,'diff new-candidate');
});

test('late candidate details cannot replace newer selection on the same task',async()=>{
  const p=page();
  await p.reply(p.take('/api/tasks/old'),task('old','first'));
  const first=p.take('/api/candidates/first');
  const refreshed=p.refresh();
  await p.reply(p.take('/api/tasks/old'),task('old','second'));
  await p.reply(p.take('/api/candidates/second'),candidate('second'));
  await refreshed;
  await p.reply(first,candidate('first'));
  assert.equal(p.element('diff').textContent,'diff second');
  const accepted=p.element('accept').click();
  const request=p.take('/api/candidates/second/accept');
  assert.deepEqual(JSON.parse(request.options.body),{check_set_hash:'hash-second'});
  await p.reply(request,{id:'accept-second'});
  await p.reply(p.take('/api/candidates/second/export'),{download_url:'/downloads/second'});
  await p.reply(p.take('/api/tasks/old'),{...task('old',null,'DELIVERED'),download_url:'/downloads/second'});
  await accepted;
  assert.equal(p.element('download').href,'/downloads/second');
});

test('late errors do not replace the current task message',async()=>{
  const p=page(), old=p.take('/api/tasks/old');
  const started=p.start();
  await p.reply(p.take('/agents/runs'),{id:'new'});
  await p.reply(p.take('/api/tasks/new'),task('new',null,'BLOCKED'));
  await started;
  await p.reply(old,{error:'stale error'},false);
  assert.equal(p.element('message').textContent,'');
});

test('start invalidates pending refresh immediately, before POST resolves',async()=>{
  const p=page(), old=p.take('/api/tasks/old');
  const started=p.start();
  await p.reply(old,task('old',null,'DELIVERED'));
  assert.equal(p.element('start').disabled,true);
  assert.equal(p.element('accept').disabled,true);
  await p.reply(p.take('/agents/runs'),{id:'new'});
  await p.reply(p.take('/api/tasks/new'),task('new',null,'GENERATING'));
  await started;
  assert.equal(p.element('phase').textContent,'生成候选');
  assert.equal(p.timers.size,1);
});

test('late acceptance cannot export a candidate from a previous task',async()=>{
  const p=page();
  await p.reply(p.take('/api/tasks/old'),task('old','first'));
  await p.reply(p.take('/api/candidates/first'),candidate('first'));
  const accepted=p.element('accept').click(), pending=p.take('/api/candidates/first/accept');
  const started=p.start();
  await p.reply(p.take('/agents/runs'),{id:'new'});
  await p.reply(p.take('/api/tasks/new'),task('new',null,'GENERATING'));
  await started;
  await p.reply(pending,{id:'old-acceptance'});
  await accepted;
  assert.equal(p.requests.some(r=>r.url.endsWith('/export')),false);
  assert.equal(p.element('phase').textContent,'生成候选');
});

test('late export cannot restore a previous task download link',async()=>{
  const p=page();
  await p.reply(p.take('/api/tasks/old'),task('old','first'));
  await p.reply(p.take('/api/candidates/first'),candidate('first'));
  const accepted=p.element('accept').click();
  await p.reply(p.take('/api/candidates/first/accept'),{id:'old-acceptance'});
  const pending=p.take('/api/candidates/first/export');
  const started=p.start();
  await p.reply(p.take('/agents/runs'),{id:'new'});
  await p.reply(p.take('/api/tasks/new'),task('new',null,'GENERATING'));
  await started;
  await p.reply(pending,{download_url:'/downloads/stale'});
  // A vulnerable handler starts a refresh after the stale export.
  const refresh=p.requests.find(r=>r.url==='/api/tasks/new');
  if (refresh) await p.reply(p.take('/api/tasks/new'),task('new',null,'GENERATING'));
  await accepted;
  assert.equal(p.element('download').hidden,true);
});


test('draft is displayed before explicit confirmation and task creation',async()=>{
  const p=page();
  const prepared=p.prepare();
  const request=p.take('/api/requirements/drafts');
  const draft={id:'draft-real-flow',version:1,project_id:'order-demo-bug',allowed_paths:['src/a.cj'],
    requirements:[{id:'REQ-QTY',text:'quantity',observable_behavior:'zero rejected',preserves:['price'],uncovered:['other systems']}]};
  await p.reply(request,draft);
  await prepared;
  assert.equal(p.element('requirement-card').hidden,false);
  assert.match(p.element('requirements').textContent,/zero rejected/);
  assert.equal(p.requests.some(r=>r.url==='/agents/runs'),false);
  const started=p.confirm();
  const confirmation=p.take('/api/requirements/drafts/draft-real-flow/confirm');
  assert.equal(JSON.parse(confirmation.options.body).expected_version,1);
  await p.reply(confirmation,{id:'confirmed-spec'});
  const start=p.take('/agents/runs');
  const gatewayBody=JSON.parse(start.options.body);
  assert.equal(gatewayBody.schema_version,1);
  assert.equal(gatewayBody.team_profile,'cangjie-repair');
  assert.equal(gatewayBody.payload.spec_id,'confirmed-spec');
  assert.equal(Object.hasOwn(gatewayBody.payload,'goal'),false);
  await p.reply(start,{id:'new'});
  await p.reply(p.take('/api/tasks/new'),task('new',null,'GENERATING'));
  await started;
});

test('reject is bound to current revision and late details cannot restore acceptance',async()=>{
  const p=page();
  await p.reply(p.take('/api/tasks/old'),{...task('old','first'),revision:4});
  await p.reply(p.take('/api/candidates/first'),{...candidate('first'),task_schema_version:2,task_revision:4});
  assert.equal(p.element('reject').disabled,false);
  const refreshed=p.refresh();
  await p.reply(p.take('/api/tasks/old'),{...task('old','first'),revision:4});
  const late=p.take('/api/candidates/first');
  p.element('reject-reason').value='Please revise';
  const rejected=p.element('reject').click();
  const request=p.take('/api/candidates/first/reject');
  assert.deepEqual(JSON.parse(request.options.body),{task_revision:4,reason:'Please revise'});
  await p.reply(request,{decision:'REJECT'});
  await p.reply(p.take('/api/tasks/old'),{...task('old','first','REJECTED'),revision:5});
  await p.reply(p.take('/api/candidates/first'),candidate('first'));
  await rejected;
  await p.reply(late,candidate('first'));
  await refreshed;
  assert.equal(p.element('phase').textContent,'已拒绝');
  assert.equal(p.element('accept').disabled,true);
  assert.equal(p.element('reject').disabled,true);
  assert.equal(p.requests.filter(r=>r.url==='/api/tasks').length,0);
});

test('cancel keeps the selected task and revision without starting a new task',async()=>{
  const p=page();
  await p.reply(p.take('/api/tasks/old'),{...task('old',null,'GENERATING'),revision:7});
  const cancelled=p.element('cancel').click();
  const request=p.take('/api/tasks/old/cancel');
  assert.deepEqual(JSON.parse(request.options.body),{task_revision:7});
  await p.reply(request,{status:'CANCELLED',in_flight_unknown:true});
  await p.reply(p.take('/api/tasks/old'),{...task('old',null,'CANCELLED'),revision:8});
  await cancelled;
  assert.equal(p.element('phase').textContent,'已取消');
  assert.equal(p.element('accept').disabled,true);
  assert.equal(p.element('cancel').disabled,true);
  assert.equal(p.requests.filter(r=>r.url==='/api/tasks').length,0);
});

test('V1.1 acceptance sends frozen candidate revision',async()=>{
  const p=page();
  await p.reply(p.take('/api/tasks/old'),{...task('old','first'),revision:9});
  await p.reply(p.take('/api/candidates/first'),{...candidate('first'),task_schema_version:2,task_revision:9});
  const accepted=p.element('accept').click();
  const request=p.take('/api/candidates/first/accept');
  assert.deepEqual(JSON.parse(request.options.body),{check_set_hash:'hash-first',task_revision:9});
  await p.reply(request,{id:'approved'});
  await p.reply(p.take('/api/candidates/first/export'),{download_url:'/downloads/approved'});
  await p.reply(p.take('/api/tasks/old'),task('old',null,'DELIVERED'));
  await accepted;
});

test('browsing an older candidate cannot accept it or restore stale details',async()=>{
  const p=page();
  const state={...task('old','second'),revision:5,candidates:[{id:'first',attempt:1},{id:'second',attempt:2}]};
  await p.reply(p.take('/api/tasks/old'),state);
  const stale=p.take('/api/candidates/second');
  p.element('candidate-history').value='first';
  p.element('candidate-history').change();
  await p.reply(p.take('/api/tasks/old'),state);
  await p.reply(p.take('/api/candidates/first'),{...candidate('first'),is_current_review:false});
  await p.reply(stale,{...candidate('second'),is_current_review:true});
  assert.equal(p.element('diff').textContent,'diff first');
  assert.equal(p.element('accept').disabled,true);
  assert.equal(p.element('reject').disabled,true);
  assert.equal(p.requests.filter(r=>r.url==='/api/tasks').length,0);
});

test('history task switch invalidates old task response without creating a run',async()=>{
  const p=page(),stale=p.take('/api/tasks/old');
  p.element('task-history').value='other';
  p.element('task-history').change();
  await p.reply(p.take('/api/tasks/other'),task('other',null,'CANCELLED'));
  await p.reply(stale,task('old','first'));
  assert.equal(p.element('phase').textContent,'已取消');
  assert.equal(p.requests.filter(r=>r.url==='/api/tasks').length,0);
  assert.equal(p.element('accept').disabled,true);
});


test('user can narrow source scope before confirming and cannot edit pending approval',async()=>{
  const p=page();
  const prepared=p.prepare();
  await p.reply(p.take('/api/requirements/drafts'),{id:'scope-draft',version:1,project_id:'order-demo-bug',
    allowed_paths:['src/quantity.cj','src/fee.cj'],requirements:[]});
  await prepared;
  const inputs=p.element('allowed-paths').children.map(label=>label.children[0]);
  assert.equal(inputs.length,2);
  inputs[1].checked=false;inputs[1].change();
  inputs[0].checked=false;inputs[0].change();
  assert.equal(p.element('start').disabled,true);
  await p.confirm();
  assert.equal(p.requests.some(r=>r.url.endsWith('/confirm')),false);
  inputs[0].checked=true;inputs[0].change();
  assert.equal(p.element('start').disabled,false);
  const started=p.confirm();
  const confirmation=p.take('/api/requirements/drafts/scope-draft/confirm');
  assert.deepEqual(JSON.parse(confirmation.options.body).allowed_paths,['src/quantity.cj']);
  assert.equal(p.element('scope-card').disabled,true);
  inputs[1].checked=true;inputs[1].change();
  await p.reply(confirmation,{id:'scope-spec'});
  await p.reply(p.take('/agents/runs'),{id:'new'});
  await p.reply(p.take('/api/tasks/new'),task('new',null,'GENERATING'));
  await started;
  assert.equal(p.element('scope-card').disabled,true);
});
