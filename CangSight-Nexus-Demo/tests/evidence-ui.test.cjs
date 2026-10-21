'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {policyRecords}=require('../nexus/demo/static/evidence-core.js');
const core=require('../nexus/demo/static/evidence-core.js');
test('later review probes do not inflate repair execution duration',()=>{
 assert.equal(core.executionDuration([{occurred_at:10,type:'TASK_STATE_CHANGED',status:'DIAGNOSING'},
  {occurred_at:40,type:'TASK_STATE_CHANGED',status:'REVIEW_PENDING'},
  {occurred_at:100,type:'POLICY_PROBE',status:'REVIEW_PENDING'}]),'30.00');
});
test('missing records cannot turn task progress into an allowed native decision',()=>{
 assert.deepEqual(policyRecords([{type:'TASK_STATE_CHANGED',status:'DELIVERED'}]),[]);
});
test('controller fallback denial is distinguished from a native process response',()=>{
 const rows=policyRecords([{policy:{request:{request_id:'offline'},decision:{decision:'Deny',reason:'POLICY_UNAVAILABLE'}}}]);
 assert.equal(rows[0].native,false);
});
test('NeedApproval and execution outcome remain distinct, joined by request id',()=>{
 const events=[{policy:{request:{request_id:'one',action:'candidate.export'},decision:{decision:'NeedApproval',reason:'ACCEPTANCE_REQUIRED'}}},
 {policy:{policy_outcome:{request_id:'two',action_executed:true,operation_status:'OK'}}},
 {policy:{policy_outcome:{request_id:'one',action_executed:false,operation_status:'ERROR'}}}];
 const rows=policyRecords(events);assert.equal(rows.length,1);assert.equal(rows[0].decision.decision,'NeedApproval');assert.equal(rows[0].outcome.action_executed,false);
});
test('an Allow response without a completion record has unknown execution outcome',()=>{
 const rows=policyRecords([{policy:{request:{request_id:'allow'},decision:{decision:'Allow'}}}]);
 assert.equal(rows[0].outcome,null);
});

test('approval probe refresh keeps the selected task and restores review controls',async()=>{
 const fs=require('node:fs'),vm=require('node:vm');const nodes=new Map();let workbenchRenders=0;
 const get=id=>{if(!nodes.has(id))nodes.set(id,{hidden:false,disabled:false,textContent:'',onclick:null});return nodes.get(id);};
 const task={id:'task',status:'REVIEW_PENDING',events:[]};
 const ctx={document:{createElement(){return {}}},$:get,api:async()=>({}),epoch:1,reviewBusy:false,
  pollReal:async()=>{},render(){workbenchRenders++;},toast(){},policyRecords};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync('nexus/demo/static/evidence.js','utf8')+'\nEvidenceUI.render('+JSON.stringify(task)+',null,"real","multifile");',ctx);
 await get('approval-probe').onclick();assert.equal(workbenchRenders,1);assert.equal(ctx.reviewBusy,false);
});

test('analysis entry is visible for every real repair case and absent for policy probes',()=>{
 const fs=require('node:fs'),vm=require('node:vm'),nodes=new Map();
 const get=id=>{if(!nodes.has(id))nodes.set(id,{});return nodes.get(id);};
 const ctx={$:get,document:{createElement(){return {}}}};vm.createContext(ctx);
 vm.runInContext(fs.readFileSync('nexus/demo/static/evidence.js','utf8')+'\nglobalThis.ui=EvidenceUI;',ctx);
 for(const id of ['order','order-price','order-discount','multifile','cross-discount','cross-stock']){
  ctx.ui.render(null,null,'real',id);assert.equal(get('repair-analysis-strip').hidden,false,id);
 }
 for(const id of ['policy','policy-config','policy-path']){
  ctx.ui.render(null,null,'real',id);assert.equal(get('repair-analysis-strip').hidden,true,id);
 }
 ctx.ui.render(null,null,'replay','order');assert.equal(get('repair-analysis-strip').hidden,true);
});
