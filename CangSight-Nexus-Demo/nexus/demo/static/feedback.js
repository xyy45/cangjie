'use strict';
const FeedbackUI=(()=>{
 const make=(tag,cls,text)=>{const n=document.createElement(tag);n.className=cls;if(text!==undefined)n.textContent=text;return n;};
 function render(box,feedback,candidate){
  box.replaceChildren();box.hidden=true;
  if(!candidate?.id||!feedback||feedback.previous_candidate_id!==candidate.id||feedback.tree_hash!==candidate.tree_hash)return;
  const cases=feedback.failure_cases||[];if(!cases.length)return;
  box.hidden=false;
  box.append(make('h3','counterexample-title','验证反例 · '+cases.length+' 项'),
   make('p','evidence-note','来自当前候选的真实测试诊断；每项显示首条可识别的相等断言。未提供的数据不会补写。'));
  const list=make('div','counterexample-list');
  for(const item of cases){
   const card=make('article','counterexample-card');
   card.append(make('strong','counterexample-case',item.test_id));
   const facts=make('dl','counterexample-facts');
   for(const [label,value] of [['输入',item.input],['预期结果',item.expected],['实际结果',item.actual]])
    facts.append(make('dt','',label),make('dd',label==='实际结果'?'counterexample-actual':'',value??'未提供'));
   card.append(facts);
   if(item.expression&&!item.input)card.append(make('p','evidence-note','测试表达式：'+item.expression));
   card.append(make('p','evidence-note',item.requirement_refs?.length?
    '关联需求（测试套件映射）：'+item.requirement_refs.join('、'):'关联需求：尚无测试映射'));
   if(item.source?.log_ref)card.append(make('code','counterexample-source',item.source.log_ref+' · 去除终端颜色后的诊断字符 '+item.source.start_char+'–'+item.source.end_char));
   list.append(card);
  }
  box.append(list);
 }
 return {render};
})();
