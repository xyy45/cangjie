(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.VerificationReportUI=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
'use strict';
const LABELS={PASS:'通过',FAIL:'失败',UNKNOWN:'待核实',NOT_RUN:'未执行'};
const state=s=>Object.hasOwn(LABELS,s)?s:'UNKNOWN';
const count=items=>({total:items.length,passed:items.filter(s=>s==='PASS').length,failed:items.filter(s=>s==='FAIL').length,unknown:items.filter(s=>s==='UNKNOWN').length,skipped:items.filter(s=>s==='NOT_RUN').length});
const kinds=[['exploration','独立规则','independent_rule'],['properties','业务属性','independent_properties'],['relations','双输入关系','independent_relations'],['sequences','连续操作序列','independent_sequences']];
function buildModel({mode='real',candidate=null,checks=[],task=null,current={},verified=false,loading=false}={}){
 const model={mode,candidate:loading?null:candidate,task:loading?null:task,current,loading,rows:[],cases:[],diagnostics:[],feedback:null,advanced:[]};
 if(mode!=='real'){
  const status=verified?'PASS':'NOT_RUN';model.rows=['工程构建','目标行为','回归测试'].map(name=>({name,state:status,counts:null}));
  model.cases=verified?(current.tests||[]).map(t=>({id:t.name,state:state(t.state),suite:'历史回放'})):[];
  model.total=count(model.cases.map(c=>c.state));return model;
 }
 const bound=c=>!loading&&candidate?.id&&candidate.tree_hash&&c.subject_id===candidate.id&&c.tree_hash===candidate.tree_hash;
 const latest=kind=>{const check=checks.findLast(c=>c.kind===kind);return check&&bound(check)?check:undefined;};
 const build=latest('build'),test=latest('test');
 const absent=kind=>!loading&&candidate?.id&&checks.some(c=>c.kind===kind)?'UNKNOWN':'NOT_RUN';
 model.rows.push({name:'工程构建',state:build?state(build.state):absent('build'),counts:null});
 const suiteNames={target:'目标行为',regression:'回归测试'},membership=new Map(),ids=new Set(Object.keys(test?.case_results||{}));
 for(const [key,label] of Object.entries(suiteNames))for(const id of Array.isArray(test?.suite_results?.[key]?.tests)?test.suite_results[key].tests:[]){
  if(typeof id!=='string')continue;ids.add(id);if(!membership.has(id))membership.set(id,[]);membership.get(id).push(label);
 }
 const caseState=id=>test?.state==='UNKNOWN'?'UNKNOWN':test?.state==='NOT_RUN'?'NOT_RUN':state(test?.case_results?.[id]);
 for(const [key,name] of Object.entries(suiteNames)){
  const suite=test?.suite_results?.[key],names=Array.isArray(suite?.tests)?suite.tests.filter(id=>typeof id==='string'):[];
  const states=names.map(caseState),counts=count(states);let result=test?'UNKNOWN':absent('test');
  if(test?.state==='NOT_RUN')result='NOT_RUN';
  else if(test?.state!=='UNKNOWN'&&names.length){
   if(suite.state==='PASS'&&states.every(s=>s==='PASS'))result='PASS';
   else if(suite.state==='FAIL'&&states.includes('FAIL'))result='FAIL';
   else if(suite.state==='NOT_RUN'&&states.every(s=>s==='NOT_RUN'))result='NOT_RUN';
  }
  model.rows.push({name,state:result,counts:counts.total?counts:null,note:test&&!names.length?'此记录未提供分组映射':''});
 }
 model.cases=[...ids].map(id=>({id,state:caseState(id),suite:membership.get(id)?.join(' / ')||'未分组'}));
 const priority={FAIL:0,UNKNOWN:1,NOT_RUN:2,PASS:3};model.cases.sort((a,b)=>priority[a.state]-priority[b.state]||a.id.localeCompare(b.id,undefined,{numeric:true}));
 model.total=count(model.cases.map(c=>c.state));
 for(const check of [build,test].filter(Boolean))model.diagnostics.push({kind:check.kind,state:state(check.state),exit_code:check.exit_code,duration_ms:check.duration_ms,log_ref:check.log_ref,text:check.diagnostics||'此记录未提供诊断文本'});
 if(!loading&&candidate?.id){
  model.feedback=(task?.events||[]).findLast(e=>e.repair_feedback?.previous_candidate_id===candidate.id&&e.repair_feedback?.tree_hash===candidate.tree_hash)?.repair_feedback||null;
  for(const [kind,name,flag] of kinds){
   const report=candidate[kind],events=(task?.events||[]).filter(e=>e.candidate_id===candidate.id&&[({exploration:'EXPLORATION_STARTED',properties:'PROPERTY_STARTED',relations:'RELATION_STARTED',sequences:'SEQUENCE_STARTED'}[kind]),({exploration:'EXPLORATION_FINISHED',properties:'PROPERTY_FINISHED',relations:'RELATION_FINISHED',sequences:'SEQUENCE_FINISHED'}[kind])].includes(e.type));
   if(!current[flag]&&!report&&!events.length)continue;
   const boundReport=report?.candidate_id===candidate.id&&report?.binding?.tree_hash===candidate.tree_hash;
   model.advanced.push({kind,name,enabled:!!current[flag],state:report?(boundReport?state(report.state):'UNKNOWN'):events.length?'UNKNOWN':'NOT_RUN',reason:report&&!boundReport?'结果与当前候选不匹配':report?.reason||''});
  }
 }
 return model;
}
function render(model,{document:doc=globalThis.document,get=id=>doc.getElementById(id),renderers={}}={}){
 const make=(tag,cls,text)=>{const n=doc.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=String(text);return n;};
 get('report-checks').replaceChildren(...model.rows.map(row=>{
  const card=make('div','report-check');card.append(doc.createTextNode(row.name),make('strong','verification-state state-'+row.state.toLowerCase(),LABELS[row.state]));
  if(row.counts)card.append(make('small','','通过 '+row.counts.passed+' / '+row.counts.total+' · 失败 '+row.counts.failed+' · 待核实 '+row.counts.unknown+' · 未执行 '+row.counts.skipped));
  else if(row.note)card.append(make('small','',row.note));return card;
 }));
 const summary=get('report-summary');summary.replaceChildren();
 const identity=model.loading?'正在加载所选轮次':model.mode!=='real'?'历史回放记录':model.candidate?.id?'第 '+(model.candidate.attempt??'?')+' 轮 · '+model.candidate.id:'候选生成后展示验证报告';
 summary.append(make('h3','verification-heading',identity),make('p','verification-summary-text','用例 '+model.total.total+' 项 · 通过 '+model.total.passed+' · 失败 '+model.total.failed+' · 待核实 '+model.total.unknown+' · 未执行 '+model.total.skipped));
 const list=get('test-list');list.replaceChildren();
 if(!model.cases.length)list.append(make('p','verification-empty',model.loading?'正在加载用例结果…':model.rows[0].state==='FAIL'?'构建失败，尚未执行测试；请查看下方构建诊断。':'此轮尚未返回逐项测试结果。'));
 for(const item of model.cases){
  const row=make('article','verification-case');row.dataset.state=item.state;
  row.append(make('code','verification-case-name',item.id),make('span','verification-suite',item.suite),make('span','verification-state state-'+item.state.toLowerCase(),LABELS[item.state]));list.append(row);
 }
 const counterexamples=get('report-counterexamples');
 counterexamples.replaceChildren();counterexamples.hidden=true;
 renderers.feedback?.render(counterexamples,model.feedback,model.candidate);
 const diagnostics=get('report-diagnostics');diagnostics.replaceChildren();
 if(!model.diagnostics.length)diagnostics.append(make('p','verification-empty',model.loading?'正在加载执行诊断…':'此轮尚未提供构建或测试诊断。'));
 for(const item of model.diagnostics){
  const details=make('details','verification-diagnostic');details.open=item.state==='FAIL'||item.state==='UNKNOWN';
  const label=(item.kind==='build'?'构建':'测试')+'诊断 · '+LABELS[item.state]+(item.exit_code!==null&&item.exit_code!==undefined?' · 退出码 '+item.exit_code:'')+(Number.isFinite(item.duration_ms)?' · '+(item.duration_ms/1000).toFixed(2)+'s':'');
  details.append(make('summary','',label),make('pre','verification-log',item.text.replace(/\x1b(?:\[[0-?]*[ -/]*[@-~]|[78])/g,'').replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g,'')));if(item.log_ref)details.append(make('code','verification-log-ref',item.log_ref));diagnostics.append(details);
 }
 const advanced=get('report-advanced'),cards=get('report-advanced-summary');cards.replaceChildren();advanced.hidden=!model.advanced.length;
 for(const item of model.advanced){const card=make('div','verification-advanced-state');card.append(make('span','',item.name),make('span','verification-state state-'+item.state.toLowerCase(),LABELS[item.state]));cards.append(card);}
 for(const [kind,,flag] of kinds){
  const box=get('report-'+kind);box.replaceChildren();box.hidden=true;
  renderers[kind]?.render(box,model.task,model.candidate,model.current[flag]===true);
 }
}
return {buildModel,render,LABELS};
});
