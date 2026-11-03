'use strict';
const LocalizationUI=(()=>{
 const $=id=>document.getElementById(id);
 const make=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
 let chosen=null,key='',epoch=0;
 function render(task,candidate,mode){
  const round=candidate?.attempt||1;
  const events=(mode==='real'?task?.events||[]:[]).filter(e=>e.type==='LOCALIZATION_CONTEXT'&&e.localization?.binding?.task_id===task?.id&&e.localization.binding.baseline_id===task?.baseline_id);
  const event=events.find(e=>e.localization.binding.for_round===round),binding=event?.localization.binding;
  const previous=round===1?null:(task?.candidates||[]).find(c=>c.attempt===round-1);
  const valid=event&&(round===1?binding.subject_id===task.baseline_id:binding.subject_id===previous?.id&&binding.subject_tree_hash===previous?.tree_hash);
  const nextKey=valid?task.id+':'+round+':'+event.context_hash:'';
  if(key!==nextKey){epoch++;$('focus-content').replaceChildren();if($('focus-dialog').open)$('focus-dialog').close();}
  key=nextKey;chosen=valid?{taskId:task.id,baselineId:task.baseline_id,specHash:task.spec_hash,round,hash:event.context_hash,subjectId:binding.subject_id,tree:binding.subject_tree_hash}:null;
  $('repair-focus').hidden=!events.length;$('focus-open').disabled=!chosen;
  $('focus-summary').textContent=chosen?'第 '+round+' 轮依据 · 查看用例、函数与基线切片':'该轮尚无可核对的定位依据';
 }
 function facts(box,items){const dl=make('dl','evidence-facts');for(const [label,value] of items)dl.append(make('dt','',label),make('dd','',value??'—'));box.append(dl);}
 async function open(){
  if(!chosen)return;const selected={...chosen},version=epoch,box=$('focus-content');box.replaceChildren(make('p','evidence-note','正在核对测试、源码和图原件…'));$('focus-dialog').showModal();
  try{
   const data=await api('/api/demo/tasks/'+selected.taskId+'/localization?round='+selected.round);
   if(version!==epoch||!$('focus-dialog').open)return;
   const report=data.report,b=report?.binding;
   if(data.task_id!==selected.taskId||data.round!==selected.round||data.context_hash!==selected.hash||!b||b.task_id!==selected.taskId||b.for_round!==selected.round||b.baseline_id!==selected.baselineId||b.subject_id!==selected.subjectId||b.subject_tree_hash!==selected.tree||selected.specHash&&b.spec_hash!==selected.specHash)throw Error('定位版本不符');
   box.replaceChildren();facts(box,[['坐标版本','冻结基线 '+b.baseline_id],['基线树',b.baseline_hash],['失败版本',b.subject_id],['失败树',b.subject_tree_hash],['报告',report.status]]);
   if(!report.targets.length)box.append(make('p','evidence-note','暂无可可靠映射的失败用例。'));
   for(const target of report.targets){
    const section=make('section','evidence-section');section.append(make('h3','',target.test_id+' → '+(target.function||'未映射函数')));
    const actual=target.actual_return_text??(typeof target.actual_return==='number'&&!Number.isSafeInteger(target.actual_return)?'精确返回值待核对':JSON.stringify(target.actual_return));
    const canonical=(key)=>target[key+'_text']??((typeof target[key]==='number'&&!Number.isSafeInteger(target[key])||Array.isArray(target[key])&&target[key].some(v=>typeof v==='number'&&!Number.isSafeInteger(v)))?'精确值待核对':JSON.stringify(target[key]))??'未提供';
    const values=target.call_id?[["状态轨迹",target.sequence_id],['步骤',target.call_id+' · '+target.sequence_role],['操作',target.operation_id+' · '+target.operation_text],['初态',canonical('initial_state')],['固定上下文',canonical('context')],['前态',canonical('before_state')],['实际返回',actual],['参考状态',canonical('expected_state')],['失败标识',(target.failure_ids||[]).join('、')]]:target.relation_id?[['关系',target.relation_id+' · '+target.relation_text],['调用侧',target.relation_role==='left'?'左侧':'右侧'],['输入对',target.pair_id],['实际返回',actual],['断言结果',String(target.assertion_value)],['应满足关系',String(target.expected_relation)]]:
     target.property_id?[['属性',target.property_id+' · '+target.property_text],['实际返回',actual],['断言结果',String(target.assertion_value)],['应满足属性',String(target.expected_property)]]:[['实际',target.actual??'未提取'],['预期',target.expected??'未提取']];
    facts(section,[['输入',target.args_text??JSON.stringify(target.args)],...values,['需求',target.requirement_refs.join('、')||'未映射'],['映射',target.mapping==='CONFIRMED_CASE'?'确认用例':'未可靠映射到源码']]);
    for(const location of target.locations){
     const part=make('div','focus-location');part.append(make('strong','',location.path+' · '+location.function),make('p','evidence-note','基线 L'+location.start_line+'–'+location.end_line+' · '+(location.call_origin==='LOCAL_SOURCE_INDEX'?'本地源码调用线索':'确认用例入口')));
     part.append(make('pre','focus-source',(location.source_lines||[]).map(s=>s.line+'  '+s.text+(s.text_truncated?'…':'')).join('\n')));
     for(const anchor of location.anchors){
      const point=anchor.slice;part.append(make('p','evidence-note','基线 L'+anchor.line+' · '+(anchor.basis==='RETURN_STATEMENT'?'返回语句':'结果表达式')+' · '+(point.status==='VALID'?'PDG静态依赖 '+point.lines.join(', '):point.reason||point.status)));
      if(point.status==='VALID'&&point.analysis_id){
       const button=make('button','button secondary','查看 L'+anchor.line+' 依赖图');
       button.onclick=async()=>{
        button.disabled=true;
        try{
         const result=await api('/api/demo/tasks/'+selected.taskId+'/analysis/'+point.analysis_id);
         if(version!==epoch||!$('focus-dialog').open)return;
         if(result.source?.source_sha256!==location.source_sha256||result.point_graph?.status!=='VALID')throw Error('图版本变化');
         if(AnalysisUI.openBound(result,{line:anchor.line})){$('focus-dialog').close();showView('analysis');}
        }catch(error){if(version===epoch)toast('依赖图核对失败');}finally{button.disabled=false;}
       };part.append(button);
      }
     }
     section.append(part);
    }
    box.append(section);
   }
   if(report.truncated)box.append(make('p','evidence-note','定位展示有预算截断，完整图和源文件保留在原件。'));
   for(const note of report.limitations)box.append(make('p','evidence-note',note));
  }catch(error){if(version===epoch)box.replaceChildren(make('p','red','定位证据核对失败，请检查原始记录。'));}
 }
 $('focus-open').onclick=open;$('focus-dialog').onclose=()=>{epoch++;};
 return{render};
})();
