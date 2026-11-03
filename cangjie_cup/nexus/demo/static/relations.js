'use strict';
const RelationUI=(()=>{
 const make=(tag,cls,text)=>{const n=document.createElement(tag);n.className=cls;if(text!==undefined)n.textContent=text;return n;};
 const unsafe=value=>value!==null&&typeof value==='object'?Object.values(value).some(unsafe):typeof value==='number'&&!Number.isSafeInteger(value);
 const exact=(value,canonical)=>canonical??(unsafe(value)?Array.isArray(value)?'精确输入待核对':'精确返回值待核对':JSON.stringify(value));
 function current(task,candidate){
  const events=(task?.events||[]).filter(e=>e.candidate_id===candidate?.id&&['RELATION_STARTED','RELATION_FINISHED'].includes(e.type));
  return {events,last:events.at(-1),report:candidate?.relations||events.at(-1)?.relations,verified:!!candidate?.relations};
 }
 const bound=(r,c)=>r?.candidate_id===c?.id&&r?.binding?.tree_hash===c?.tree_hash;
 function render(box,task,candidate,required){
  box.replaceChildren();box.hidden=true;if(!candidate?.id)return;
  const {events,last,report,verified}=current(task,candidate);if(!required&&!events.length&&!report)return;
  box.hidden=false;box.append(make('h3','counterexample-title','业务关系 · 双侧实际调用验证'));
  if(!report){box.append(make('p','evidence-note',last?.type==='RELATION_STARTED'?(task?.status==='TESTING'?'关系验证中':'关系执行中断或结果待核实'):'待执行 · 前置测试与属性通过后验证'));return;}
  if(!bound(report,candidate)){box.append(make('p','evidence-note','关系结果绑定与当前候选不符，请刷新核查'));return;}
  const state=report.state==='PASS'&&!verified?'关系结果待核对':{PASS:'关系通过',FAIL:'发现关系违反',UNKNOWN:'验证未完成'}[report.state]||'验证未完成';
  box.append(make('p','evidence-note','公开测试 '+(report.public_test_state??'待核对')+' · '+state+' · 搜索 '+(report.search_pairs??'—')+' 对 · 缩减 '+(report.shrink_pairs??'—')+' 对 · 累计回归 '+(report.regression_pairs??'—')+' 对 · 实际观测 '+(report.observed_calls??'—')+' 次'));
  if(report.binding.relations_hash)box.append(make('code','evidence-hash','关系 SHA-256 '+report.binding.relations_hash));
  if(report.reason)box.append(make('p','evidence-note',report.reason));
  for(const r of report.per_relation||[])box.append(make('p','evidence-note',r.id+' · 生成 '+r.generated+' 对 · 适用 '+r.applicable+' 对 · 双侧观测 '+r.observed+' 对 · 违反 '+r.failed+' 对'));
  const list=make('div','counterexample-list');
  for(const f of report.failures||[]){
   const card=make('article','counterexample-card');card.append(make('strong','counterexample-case',f.relation_id+' · '+f.relation_text));
   const facts=make('dl','counterexample-facts');
   for(const [side,label] of [['left','左侧'],['right','右侧']]){
    for(const [name,value] of [[label+'输入',exact(f[side+'_args'],f[side+'_args_text'])],[label+'实际返回',exact(f[side+'_actual_return'],f[side+'_actual_return_text'])],[label+'调用',f[side+'_test_id']]])facts.append(make('dt','',name),make('dd','',value??'未提供'));
   }
   for(const [label,value] of [['断言结果',String(f.assertion_value)],['应满足关系',String(f.expected_relation)]])facts.append(make('dt','',label),make('dd','',value));
   card.append(facts);list.append(card);
  }
  box.append(list);
  if(report.failures_truncated)box.append(make('p','evidence-note','保留前16条不同关系反例组合；共 '+report.distinct_failure_count+' 条，累计回归使用该保留集合。'));
 }
 function roundState(task,candidate,required){
  if(candidate?.build_state==='FAIL'||candidate?.test_state==='FAIL')return 'failed';
  const {events,report,verified}=current(task,candidate);
  if(required||events.length||report){
   if(!bound(report,candidate))return 'pending';
   if(report.state==='FAIL')return 'failed';
   if(report.state!=='PASS'||!verified)return 'pending';
  }
  return candidate?.build_state==='PASS'&&candidate?.test_state==='PASS'?'passed':'pending';
 }
 return{render,roundState};
})();
