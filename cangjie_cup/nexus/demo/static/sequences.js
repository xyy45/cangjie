'use strict';
const SequenceUI=(()=>{
 const make=(tag,cls,text)=>{const n=document.createElement(tag);n.className=cls;if(text!==undefined)n.textContent=text;return n;};
 const unsafe=value=>value!==null&&typeof value==='object'?Object.values(value).some(unsafe):typeof value==='number'&&!Number.isSafeInteger(value);
 const exact=(value,canonical)=>canonical??(unsafe(value)?Array.isArray(value)?'精确输入待核对':'精确值待核对':JSON.stringify(value))??'未提供';
 const facts=(box,items)=>{const dl=make('dl','counterexample-facts');for(const [name,value] of items)dl.append(make('dt','',name),make('dd','',value??'未提供'));box.append(dl);};
 const original=(box,source,label)=>{if(source?.log_ref)box.append(make('code','counterexample-source',label+' '+source.log_ref+' · '+(source.coordinate||'原件')+' 字符 '+(source.start_char??'—')+'–'+(source.end_char??'—')));};
 function renderPaths(box,paths){
  for(const path of paths){
   const card=make('article','counterexample-card');card.append(make('strong','counterexample-case',path.sequence_id||'状态轨迹'));
   facts(card,[['初始状态',exact(path.initial_state,path.initial_state_text)],['固定上下文',exact(path.context,path.context_text)],['SDK case',path.test_id],
    ['执行步骤','计划 '+(path.planned_steps??'—')+' · 观测 '+(path.observed_steps??path.steps?.length??'—')+' · 未执行尾部 '+(path.unexecuted_steps??'—')],
    ['结束原因',{COMPLETE:'完整执行',MODEL_MISMATCH:'首次模型偏离，停止后续调用'}[path.stop_reason]||path.stop_reason||'待核对']]);
   for(const step of path.steps||[]){
    const item=make('section','evidence-section');item.append(make('h4','',('step'+(step.step_index??'—'))+' · '+(step.operation_id||'操作')+' · '+(step.operation_text||'')));
    facts(item,[['完整输入',exact(step.args,step.args_text)],['前态',exact(step.before_state,step.before_state_text)],['实际返回',exact(step.actual_return,step.actual_return_text)],
     ['参考状态',exact(step.expected_state,step.expected_state_text)],['实际调用',(step.test_id||path.test_id||'待核对')+' · step'+(step.step_index??'—')]]);
    if(step.violations?.length)item.append(make('p','evidence-note','违反 '+step.violations.map(v=>v.failure_id).join('、')));
    original(item,step.source,'步骤原件');card.append(item);
   }
   if(path.failure_ids?.length)card.append(make('p','evidence-note','失败标识 '+path.failure_ids.join('、')));
   original(card,path.end_source,'结束原件');box.append(card);
  }
 }
 function current(task,candidate){
  const events=(task?.events||[]).filter(e=>e.candidate_id===candidate?.id&&['SEQUENCE_STARTED','SEQUENCE_FINISHED'].includes(e.type));
  return{events,last:events.at(-1),report:candidate?.sequences||events.at(-1)?.sequences,verified:!!candidate?.sequences};
 }
 const bound=(r,c)=>r?.candidate_id===c?.id&&r?.binding?.tree_hash===c?.tree_hash;
 function render(box,task,candidate,required){
  box.replaceChildren();box.hidden=true;if(!candidate?.id)return;
  const {events,last,report,verified}=current(task,candidate);if(!required&&!events.length&&!report)return;
  box.hidden=false;box.append(make('h3','counterexample-title','状态序列 · 连续操作验证'));
  if(!report){box.append(make('p','evidence-note',last?.type==='SEQUENCE_STARTED'?(task?.status==='TESTING'?'序列验证中':'序列执行中断或结果待核实'):'待执行 · 前置检查通过后验证'));return;}
  if(!bound(report,candidate)){box.append(make('p','evidence-note','序列结果与当前候选绑定不符，请刷新核查'));return;}
  const state=report.state==='PASS'&&!verified?'序列结果待核对':{PASS:'序列通过',FAIL:'发现序列违反',UNKNOWN:'验证未完成'}[report.state]||'验证未完成';
  box.append(make('p','evidence-note','公开测试 '+(report.public_test_state??'待核对')+' · '+state+' · 搜索 '+(report.search_traces??'—')+' 条 · 缩减 '+(report.shrink_traces??'—')+' 条 · 累计回归 '+(report.regression_traces??'—')+' 条'));
  box.append(make('p','evidence-note','搜索计划调用 '+(report.search_planned_calls??'—')+' 次 · 缩减计划调用 '+(report.shrink_planned_calls??'—')+' 次 · 实际观测 '+(report.observed_calls??'—')+' 次'));
  if(report.binding.sequences_hash)box.append(make('code','evidence-hash','状态模型 SHA-256 '+report.binding.sequences_hash));
  if(report.reason)box.append(make('p','evidence-note',report.reason));
  for(const operation of report.per_operation||[])box.append(make('p','evidence-note',operation.id+' · 计划 '+(operation.planned??'—')+' · 观测 '+(operation.observed??'—')+' · 模型偏离 '+(operation.model_mismatches??'—')));
  for(const invariant of report.per_invariant||[])box.append(make('p','evidence-note',invariant.id+' · 适用 '+(invariant.planned_applicable??'—')+' · 观测 '+(invariant.observed??'—')+' · 违反 '+(invariant.violations??'—')));
  const list=make('div','counterexample-list');
  const paths=report.failures?.length?report.failures:(report.batches||[]).flatMap(batch=>batch.result?.observations||[]);renderPaths(list,paths);box.append(list);
  if(report.failures_truncated)box.append(make('p','evidence-note','保留前8条不同失败前缀；共 '+(report.distinct_failure_count??'—')+' 条，完整批次保留于原件。'));
 }
 function roundState(task,candidate,required){
  if(candidate?.build_state==='FAIL'||candidate?.test_state==='FAIL')return 'failed';
  const {events,report,verified}=current(task,candidate);
  if(required||events.length||report){if(!bound(report,candidate))return 'pending';if(report.state==='FAIL')return 'failed';if(report.state!=='PASS'||!verified)return 'pending';}
  return candidate?.build_state==='PASS'&&candidate?.test_state==='PASS'?'passed':'pending';
 }
 return{render,renderPaths,roundState};
})();
