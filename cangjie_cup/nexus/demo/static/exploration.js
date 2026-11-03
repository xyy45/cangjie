'use strict';
const ExplorationUI=(()=>{
 const make=(tag,cls,text)=>{const n=document.createElement(tag);n.className=cls;if(text!==undefined)n.textContent=text;return n;};
 const unsafe=value=>value!==null&&typeof value==='object'?Object.values(value).some(unsafe):typeof value==='number'&&!Number.isSafeInteger(value);
 function render(box,task,candidate,enabled){
  box.replaceChildren();box.hidden=true;if(!candidate?.id)return;
  const events=(task?.events||[]).filter(e=>e.candidate_id===candidate.id&&['EXPLORATION_STARTED','EXPLORATION_FINISHED'].includes(e.type));
  if(!enabled&&!events.length&&!candidate.exploration)return;
  box.hidden=false;box.append(make('h3','counterexample-title','独立规则 · 边界搜索'));
  const last=events.at(-1),report=candidate.exploration||last?.exploration;
  if(!report){box.append(make('p','evidence-note',last?.type==='EXPLORATION_STARTED'?(task?.status==='TESTING'?'搜索中 · 公开测试已通过，正在独立执行边界输入':'验证中断或结果待核实，不能据此接受候选'):'待搜索 · 公开测试通过后执行'));return;}
  if(report.candidate_id!==candidate.id||report.binding?.tree_hash!==candidate.tree_hash){box.append(make('p','evidence-note','验证绑定与当前候选不符，请刷新核查'));return;}
  const label=report.state==='PASS'&&!candidate.exploration?'搜索结果待核对':{PASS:'搜索通过',FAIL:'发现反例',UNKNOWN:'验证未完成'}[report.state]||'验证未完成';
  box.append(make('p','evidence-note','公开测试 '+(report.public_test_state??'待核对')+' · '+label+' · 搜索 '+(report.search_cases??'—')+' 项 · 缩减 '+(report.shrink_cases??'—')+' 项 · 累积回归 '+(report.regression_cases??'—')+' 项 · 种子 '+(report.seed??'—')));
  if(report.binding.oracle_hash)box.append(make('code','evidence-hash','规则 SHA-256 '+report.binding.oracle_hash));
  if(report.reason)box.append(make('p','evidence-note',report.reason));
  const list=make('div','counterexample-list');
  for(const failure of report.failures||[]){const card=make('article','counterexample-card');card.append(make('strong','counterexample-case','已执行反例'));
   const facts=make('dl','counterexample-facts');for(const [label,value] of [['输入',failure.args_text??(unsafe(failure.args)?'精确输入待核对':JSON.stringify(failure.args))],['预期',failure.expected],['实际',failure.actual]])facts.append(make('dt','',label),make('dd','',value));card.append(facts);list.append(card);}
  box.append(list,make('p','evidence-note','依据已确认规则进行有限输入搜索；缩减有预算限制，不保证全局最小。'));
 }
 function roundState(task,candidate,required){
  if(candidate.build_state==='FAIL'||candidate.test_state==='FAIL')return 'failed';
  const events=(task?.events||[]).filter(e=>e.candidate_id===candidate.id&&['EXPLORATION_STARTED','EXPLORATION_FINISHED'].includes(e.type));
  const last=events.at(-1),report=candidate.exploration||last?.exploration;
  if(required||events.length||report){
   if(!report||report.candidate_id!==candidate.id||report.binding?.tree_hash!==candidate.tree_hash)return 'pending';
   if(report.state==='FAIL')return 'failed';
   if(report.state!=='PASS'||!candidate.exploration)return 'pending';
  }
  return candidate.build_state==='PASS'&&candidate.test_state==='PASS'?'passed':'pending';
 }
 return {render,roundState};
})();
