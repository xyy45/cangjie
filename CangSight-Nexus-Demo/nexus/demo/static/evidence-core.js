'use strict';
function policyRecords(events){
 const rows=new Map(),outcomes=new Map(),probes=new Set(events.filter(e=>e.type==='POLICY_PROBE').map(e=>e.request_id));
 for(const event of events){
  const policy=event.policy;if(!policy)continue;
  if(policy.request?.request_id&&policy.decision){
   const id=policy.request.request_id;
   const native=[policy.decision.policy_component_hash,policy.decision.policy_source_hash].every(h=>typeof h==='string'&&/^[0-9a-f]{64}$/.test(h));
   rows.set(id,{request:policy.request,decision:policy.decision,native,outcome:null,probe:probes.has(id)||event.type==='NATIVE_PROBE',time:event.occurred_at});
   if(event.type==='NATIVE_PROBE')outcomes.set(id,{request_id:id,action_executed:false,operation_status:'NOT_RUN',
    baseline_unchanged:event.baseline_unchanged,candidate_writes:event.candidate_writes,mcp_status:event.mcp_status});
  }
  if(policy.policy_outcome)outcomes.set(policy.policy_outcome.request_id,policy.policy_outcome);
 }
 for(const [id,row] of rows)row.outcome=outcomes.get(id)||null;
 return [...rows.values()];
}
function executionDuration(events){
 const times=[];
 for(const event of events){
  if(Number.isFinite(event.occurred_at))times.push(event.occurred_at);
  if(event.type==='TASK_STATE_CHANGED'&&['REVIEW_PENDING','BLOCKED','IN_DOUBT','UNREPAIRED','CANCELLED','REJECTED','DELIVERED'].includes(event.status))break;
 }
 return times.length>1?(Math.max(...times)-Math.min(...times)).toFixed(2):null;
}
if(typeof module!=='undefined')module.exports={policyRecords,executionDuration};
