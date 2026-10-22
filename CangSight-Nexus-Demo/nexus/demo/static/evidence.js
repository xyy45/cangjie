'use strict';
const EvidenceUI=(()=>{
 const make=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
 const names={sympas_slice_table:'静态切片表',sympas_slice:'静态切片',sympas_dep_graph:'数据依赖',ast_symbol_extractor:'结构线索'};
 let task=null,advice=null,currentMode='real',probeBusy=false,viewEpoch=0;
 function update(value,suggestion,mode,caseId){
  if(task?.id!==value?.id||currentMode!==mode)viewEpoch++;
  task=value;advice=suggestion;currentMode=mode;
  const report=(task?.events||[]).find(e=>e.type==='ANALYSIS_CONTEXT')?.analysis_context;
  $('repair-analysis-strip').hidden=mode!=='real'||!(['order','order-price','order-discount','multifile','cross-discount','cross-stock'].includes(caseId)||caseId?.startsWith('upload_'));
  $('repair-analysis-status').textContent=report?report.status==='COMPLETE'?'分析已送入上下文':report.status==='PARTIAL'?'部分分析可用':'分析不可用':'修复前分析';
  $('repair-analysis-summary').textContent=report?report.files.length+' 文件 · '+report.files.flatMap(f=>f.tools).filter(t=>t.included).length+' 项有效依据 · 模型引用 '+(advice?.analysis_refs?.length||0)+' 项':'允许修改的生产源码 · 同版本绑定';
  $('repair-analysis-open').disabled=!report;
  $('approval-probe').disabled=probeBusy||mode!=='real'||task?.status!=='REVIEW_PENDING';
 }
 function details(box,items){const dl=make('dl','evidence-facts');for(const [key,value] of items)dl.append(make('dt','',key),make('dd','',value??'—'));box.append(dl);}
 async function showAnalysis(){
  if(!task||currentMode!=='real')return;const identity=task.id,version=viewEpoch;
  const box=$('repair-analysis-content');box.replaceChildren(make('p','evidence-note','核对原始证据…'));$('repair-analysis-dialog').showModal();
  try{
   const report=(await api('/api/demo/tasks/'+identity+'/analysis')).analysis;
   if(version!==viewEpoch||!$('repair-analysis-dialog').open)return;
   box.replaceChildren();
   details(box,[['基线',report.baseline_id],['树摘要',report.baseline_hash]]);
   const citations=new Set(advice?.analysis_refs||[]);
   for(const file of report.files){
    const section=make('section','evidence-section'),heading=make('div','evidence-heading');
    const open=make('button','button secondary','查看图与切片');
    open.onclick=async()=>{open.disabled=true;try{const result=await api('/api/demo/tasks/'+identity+'/analysis/'+file.analysis_id);if(version!==viewEpoch)return;
      if(AnalysisUI.openBound(result)){$('repair-analysis-dialog').close();showView('analysis');}}
      catch(error){toast(error.message);}finally{open.disabled=false;}};
    heading.append(make('strong','',file.path),open);section.append(heading,make('code','evidence-hash',file.source_sha256));
    for(const tool of file.tools){const row=make('div','evidence-tool-row');row.append(make('span','',names[tool.tool]),
      make('span',tool.included?'green':'evidence-note',tool.included?'已纳入上下文':tool.status),
      make('span','tiny-badge',citations.has(tool.evidence_id)?'模型引用':'未引用'));section.append(row);if(!tool.included)section.append(make('p','evidence-note',tool.reason));}
    box.append(section);
   }
   if(advice)box.append(make('p','evidence-note','模型解释：'+advice.summary));
  }catch(error){if(version===viewEpoch)box.replaceChildren(make('p','red','证据核对失败，请检查记录。'));}
 }
 function showPolicy(){
  const box=$('policy-detail-content'),rows=currentMode==='real'?policyRecords(task?.events||[]):[];
  box.replaceChildren();
  if(!rows.length)box.append(make('p','evidence-note','尚未取得本次原生策略记录。'));
  for(const row of rows.toReversed()){
   const section=make('section','evidence-section'),head=make('div','evidence-heading');
   head.append(make('strong','',row.request.action),make('span','tiny-badge',row.native?row.decision.decision:'无原生响应'));section.append(head);
   details(section,[['来源',!row.native?'控制层拒绝，未取得原生响应':row.probe?'真实原生探测':'实际工具门禁'],['原因',row.decision.reason],['路径',row.request.paths?.join('、')||'无文件写入路径'],
    ['执行',row.outcome?(row.outcome.action_executed?'已进入工具，返回 '+row.outcome.operation_status:'动作未执行'):'无完成记录，结果未知'],
    ['请求',row.request.request_id],['输入树',row.request.input_tree_hash],['策略版本',row.decision.policy_version],
    ['策略组件',row.decision.policy_component_hash||'缺失'],['源码摘要',row.decision.policy_source_hash||'缺失']]);
   const raw=make('details','evidence-raw');raw.append(make('summary','','原始请求与响应'),make('pre','',JSON.stringify(row,null,2)));section.append(raw);box.append(section);
  }
  $('policy-detail-dialog').showModal();
 }
 async function probe(){
  if(probeBusy||currentMode!=='real'||task?.status!=='REVIEW_PENDING')return;
  const id=task.id,version=viewEpoch;probeBusy=true;reviewBusy=true;$('approval-probe').disabled=true;
  try{await api('/api/demo/tasks/'+id+'/approval-probe',{});if(version!==viewEpoch)return;await pollReal(epoch);showPolicy();}
  catch(error){toast(error.message);}finally{probeBusy=false;reviewBusy=false;render();}
 }
 $('repair-analysis-open').onclick=showAnalysis;$('policy-detail-open').onclick=showPolicy;$('approval-probe').onclick=probe;
 return {render:update};
})();
