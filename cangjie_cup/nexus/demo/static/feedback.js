'use strict';
const FeedbackUI=(()=>{
 const make=(tag,cls,text)=>{const n=document.createElement(tag);n.className=cls;if(text!==undefined)n.textContent=text;return n;};
 const unsafe=value=>value!==null&&typeof value==='object'?Object.values(value).some(unsafe):typeof value==='number'&&!Number.isSafeInteger(value);
 const exact=(value,canonical)=>canonical??(unsafe(value)?Array.isArray(value)?'精确输入待核对':'精确返回值待核对':JSON.stringify(value));
 function render(box,feedback,candidate){
  box.replaceChildren();box.hidden=true;
  if(!candidate?.id||!feedback||feedback.previous_candidate_id!==candidate.id||feedback.tree_hash!==candidate.tree_hash)return;
  const cases=feedback.failure_cases||[];if(!cases.length)return;
  box.hidden=false;
  box.append(make('h3','counterexample-title','验证反例 · '+cases.length+' 项'),
   make('p','evidence-note',cases.some(c=>c.kind==='public_field')?'来自当前候选的公开字段断言。':cases.some(c=>c.kind==='business_sequence')?'来自当前候选从初态开始的连续实际调用与状态模型。':cases.some(c=>c.kind==='business_relation')?'来自当前候选的两个实际调用与已确认关系。':cases.some(c=>c.kind==='business_property')?'来自当前候选的实际返回观测与已确认属性。':cases.some(c=>c.kind==='independent_rule'&&'actual_return' in c)?'来自当前候选的真实返回观测与已确认独立规则。':'来自当前候选的真实测试诊断；每项显示首条可识别的相等断言。未提供的数据不会补写。'));
  const list=make('div','counterexample-list');
  for(const item of cases){
   const card=make('article','counterexample-card');
   if(item.kind==='business_sequence'&&typeof SequenceUI!=='undefined'){SequenceUI.renderPaths(card,[item]);if(item.requirement_refs?.length)card.append(make('p','evidence-note','关联需求（用户确认状态模型）：'+item.requirement_refs.join('、')));list.append(card);continue;}
   const relation=item.kind==='business_relation';
   card.append(make('strong','counterexample-case',relation?item.pair_id:item.test_id));
   const facts=make('dl','counterexample-facts');
   const property=item.kind==='business_property',field=item.kind==='public_field';
   if(property)card.append(make('p','evidence-note',item.property_id+' · '+item.property_text));
   if(relation)card.append(make('p','evidence-note',item.relation_id+' · '+item.relation_text));
   const input=item.args_text??(unsafe(item.args)?'精确输入待核对':JSON.stringify(item.args));
   const actual=item.actual_return_text??(unsafe(item.actual_return)?'精确返回值待核对':JSON.stringify(item.actual_return));
   const fieldPath=(item.field_path||[]).map((part,index)=>typeof part==='number'?'['+part+']':(index?'.':'')+(part==='$size'?'size':part)).join('')||'返回值';
   const values=field?[['字段',fieldPath],['字段类型',item.value_type],['输入',input],['预期字段值',exact(item.expected_value,item.expected_value_text)],item.value_state==='TEXT_ONLY'?['SDK差异',item.actual_text]:['实际字段值',exact(item.actual_value,item.actual_value_text)]]:relation?[...['left','right'].flatMap(side=>{const label=side==='left'?'左侧':'右侧';return [[label+'输入',exact(item[side+'_args'],item[side+'_args_text'])],[label+'实际返回',exact(item[side+'_actual_return'],item[side+'_actual_return_text'])],[label+'调用',item[side+'_test_id']]];}),['断言结果',String(item.assertion_value)],['应满足关系',String(item.expected_relation)]]:
    property?[['输入',input],['实际返回',actual],['断言结果',String(item.assertion_value)],['应满足属性',String(item.expected_property)]]:[['输入',item.kind==='independent_rule'&&Array.isArray(item.args)?input:item.input],['预期结果',item.expected],['实际结果',item.actual]];
   for(const [label,value] of values)
    facts.append(make('dt','',label),make('dd',['实际结果','实际字段值','SDK差异'].includes(label)?'counterexample-actual':'',value??'未提供'));
   card.append(facts);
   if(item.expression&&!item.input)card.append(make('p','evidence-note','测试表达式：'+item.expression));
   card.append(make('p','evidence-note',item.requirement_refs?.length?
    '关联需求（'+(field?'冻结字段断言':relation?'用户确认关系':property?'用户确认属性':'测试套件映射')+'）：'+item.requirement_refs.join('、'):'关联需求：尚无测试映射'));
   if(item.source?.log_ref)card.append(make('code','counterexample-source',item.source.log_ref+' · 去除终端颜色后的诊断字符 '+item.source.start_char+'–'+item.source.end_char));
   if(relation)for(const side of ['left','right']){const source=item[side+'_source'];if(source?.log_ref)card.append(make('code','counterexample-source',(side==='left'?'左侧':'右侧')+'原件 '+source.log_ref+' · 字符 '+source.start_char+'–'+source.end_char));}
   list.append(card);
  }
  box.append(list);
 }
 return {render};
})();
