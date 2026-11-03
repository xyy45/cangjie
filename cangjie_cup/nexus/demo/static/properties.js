'use strict';
const PropertyUI=(()=>{
 const make=(tag,cls,text)=>{const n=document.createElement(tag);n.className=cls;if(text!==undefined)n.textContent=text;return n;};
 const unsafe=value=>value!==null&&typeof value==='object'?Object.values(value).some(unsafe):typeof value==='number'&&!Number.isSafeInteger(value);
 function current(task,candidate){
  const events=(task?.events||[]).filter(e=>e.candidate_id===candidate?.id&&['PROPERTY_STARTED','PROPERTY_FINISHED'].includes(e.type));
  return {events,last:events.at(-1),report:candidate?.properties||events.at(-1)?.properties,verified:!!candidate?.properties};
 }
 const bound=(r,c)=>r?.candidate_id===c?.id&&r?.binding?.tree_hash===c?.tree_hash;
 function render(box,task,candidate,required){
  box.replaceChildren();box.hidden=true;if(!candidate?.id)return;
  const {events,last,report,verified}=current(task,candidate);if(!required&&!events.length&&!report)return;
  box.hidden=false;box.append(make('h3','counterexample-title','业务属性 · 实际返回验证'));
  if(!report){box.append(make('p','evidence-note',last?.type==='PROPERTY_STARTED'?(task?.status==='TESTING'?'属性验证中':'属性执行中断或结果待核实'):'待执行 · 公开测试及独立规则通过后验证'));return;}
  if(!bound(report,candidate)){box.append(make('p','evidence-note','属性结果绑定与当前候选不符，请刷新核查'));return;}
  const state=report.state==='PASS'&&!verified?'属性结果待核对':{PASS:'属性通过',FAIL:'发现属性违反',UNKNOWN:'验证未完成'}[report.state]||'验证未完成';
  box.append(make('p','evidence-note','公开测试 '+(report.public_test_state??'待核对')+' · '+state+' · 搜索 '+(report.search_cases??'—')+' 项 · 缩减 '+(report.shrink_cases??'—')+' 项 · 累计回归 '+(report.regression_cases??'—')+' 项'));
  if(report.binding.properties_hash)box.append(make('code','evidence-hash','属性 SHA-256 '+report.binding.properties_hash));
  if(report.reason)box.append(make('p','evidence-note',report.reason));
  for(const p of report.batches?.[0]?.result?.per_property||[])box.append(make('p','evidence-note',p.id+' · 生成 '+p.generated+' · 适用 '+p.applicable+' · 观测 '+p.observed+' · 违反 '+p.failed));
  const list=make('div','counterexample-list');
  for(const f of report.failures||[]){
   const card=make('article','counterexample-card');card.append(make('strong','counterexample-case',f.property_id+' · '+f.property_text));
   const facts=make('dl','counterexample-facts');
   const input=f.args_text??(unsafe(f.args)?'精确输入待核对':JSON.stringify(f.args));
   const actual=f.actual_return_text??(unsafe(f.actual_return)?'精确返回值待核对':JSON.stringify(f.actual_return));
   for(const [label,value] of [['输入',input],['实际返回',actual],['断言结果',String(f.assertion_value)],['应满足属性',String(f.expected_property)]])facts.append(make('dt','',label),make('dd','',value));
   card.append(facts);list.append(card);
  }
  box.append(list);
  if(report.failures_truncated)box.append(make('p','evidence-note','展示前16条不同属性反例；共 '+report.distinct_failure_count+' 条。'));
 }
 function roundState(task,candidate,required){
  if(candidate.build_state==='FAIL'||candidate.test_state==='FAIL')return 'failed';
  const {events,report,verified}=current(task,candidate);
  if(required||events.length||report){
   if(!bound(report,candidate))return 'pending';
   if(report.state==='FAIL')return 'failed';
   if(report.state!=='PASS'||!verified)return 'pending';
  }
  return candidate.build_state==='PASS'&&candidate.test_state==='PASS'?'passed':'pending';
 }
 return{render,roundState};
})();
