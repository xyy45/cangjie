'use strict';
const ImpactUI=(()=>{
 const make=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
 const names={sympas_slice_table:'静态切片表',sympas_slice:'切片',sympas_dep_graph:'DDG',ast_symbol_extractor:'结构线索'};
 const labels={NOT_STARTED:'本地改动预览',READY:'等待分析',RUNNING:'工具分析中',COMPLETE:'工具结果完整',PARTIAL:'部分工具结果',FAILED:'工具分析失败',IN_DOUBT:'中断待核实'};
 let identity=null,taskId=null,version=0,report=null,requestBusy=false,runningRepair=false,pollTimer;
 const active=()=>['READY','RUNNING'].includes(report?.status);
 function render(task,candidate,mode,running){
  runningRepair=running;
  const id=mode==='real'?candidate?.id:null;
  $('impact-open').disabled=!id;
  if(identity!==id||taskId!==task?.id){identity=id;taskId=task?.id;version++;report=null;requestBusy=false;clearTimeout(pollTimer);$('impact-dialog').close();$('impact-identity').textContent='';$('impact-files').replaceChildren();}
  if($('impact-dialog').open)controls();
 }
 function controls(){
  $('impact-generate').disabled=requestBusy||runningRepair||!report||report.status!=='NOT_STARTED';
  $('impact-generate').textContent=active()?'分析中':requestBusy?'请求中':report?.status==='NOT_STARTED'?'生成工具对比':'分析已记录';
  $('impact-status').textContent=labels[report?.status]||'读取中';
  $('impact-download').hidden=!report?.report_ref;
  if(report?.report_ref)$('impact-download').href='/api/demo/candidates/'+identity+'/impact/evidence';
 }
 async function load(generation=false){
  if(!identity||requestBusy||generation&&(runningRepair||report?.status!=='NOT_STARTED'))return;
  const id=identity,stamp=version;requestBusy=true;controls();
  try{
   const result=await api('/api/demo/candidates/'+id+'/impact',generation?{}:undefined);
   if(stamp!==version||id!==identity||!$('impact-dialog').open)return;
   if(result.candidate_id!==id)throw Error('影响报告版本不符');
   report=result;paint();
   clearTimeout(pollTimer);if(active())pollTimer=setTimeout(()=>{if(stamp===version&&$('impact-dialog').open)load();},1000);
  }catch(error){if(stamp===version&&$('impact-dialog').open){$('impact-notice').textContent=error.message||'影响报告读取失败';toast(error.message);}}
  finally{if(stamp===version){requestBusy=false;controls();}}
 }
 async function open(){if(!identity)return;clearTimeout(pollTimer);$('impact-files').replaceChildren();$('impact-notice').textContent='核对候选与源码版本…';$('impact-dialog').showModal();await load();}
 function codeSnippet(code,changed,side){
  const pre=make('div','impact-source'),lines=code.split(/\r\n|\n|\r/),selected=new Set(changed),near=new Set();
  for(const line of changed)for(let n=Math.max(1,line-1);n<=Math.min(lines.length,line+1);n++)near.add(n);
  const display=[...near].sort((a,b)=>a-b).slice(0,80);
  for(const n of display){const row=make('div','impact-code-line'+(selected.has(n)?' changed-'+side:''));row.append(make('span','',String(n)),make('code','',lines[n-1]||' '));pre.append(row);}
  if(!display.length)pre.append(make('p','evidence-note','本侧没有修改行；插入／删除位置见另一侧。'));
  if(near.size>80)pre.append(make('p','evidence-note','相关源码片段超过80行，仅展示前80行。'));
  return pre;
 }
 function svg(tag,attrs={},text){const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));if(text!==undefined)n.textContent=text;return n;}
 function drawGraph(graph,side,emptyMessage){
  const box=make('div','impact-graph');
  if(!graph?.nodes?.length){box.append(make('p','evidence-note',graph?.reason||emptyMessage));return box;}
  const layout=AnalysisCore.layoutGraph(graph),positions=new Map(layout.nodes.map(n=>[n.id,n])),anchors=new Set(graph.anchor_ids);
  const canvas=svg('svg',{viewBox:`0 0 ${layout.width} ${layout.height}`,width:Math.max(340,layout.width*.65),height:Math.max(180,layout.height*.7),role:'img','aria-label':(side==='before'?'修复前相关依赖':'修复后相关依赖')+' · '+(graph.graph_type||'Ddg').toUpperCase()});
  // Presentation attributes lose to the shared 18px icon rule; size charts explicitly.
  canvas.style.width=Math.max(340,layout.width*.65)+'px';canvas.style.height=Math.max(180,layout.height*.7)+'px';
  for(const edge of layout.edges){const from=positions.get(edge.from),to=positions.get(edge.to);canvas.append(svg('path',{class:'analysis-edge',d:`M${from.x+208},${from.y+26} C${from.x+240},${from.y+26} ${to.x-30},${to.y+26} ${to.x},${to.y+26}`}));}
  for(const node of layout.nodes){const group=svg('g',{class:'analysis-node'+(anchors.has(node.id)?' impact-anchor-'+side:''),transform:`translate(${node.x} ${node.y})`});group.append(svg('rect',{width:208,height:52,rx:7}),svg('title',{},node.label),svg('text',{x:10,y:18,class:'analysis-node-meta'},node.line?'L'+node.line:node.id),svg('text',{x:10,y:37},node.label.length>27?node.label.slice(0,26)+'…':node.label));canvas.append(group);}
  box.append(canvas);return box;
 }
 function pendingSide(file,side){
  if(report.status==='NOT_STARTED')return '尚未生成工具对比';
  if(active())return report.status==='RUNNING'&&report.progress===file.path+' · '+(side==='before'?'修复前':'修复后')?'该侧工具分析中…':'等待该侧工具分析';
  if(report.status==='IN_DOUBT')return '该侧分析已中断，尚无可用结果';
  return '该侧未取得分析结果'+(report.error?' · '+report.error:'');
 }
 async function inspect(file,side){
  const id=identity,stamp=version,entry=file[side];
  try{const result=await api('/api/demo/candidates/'+id+'/impact/analysis/'+entry.analysis_id);
   if(stamp!==version||id!==identity||!$('impact-dialog').open)return;
   if(result.source.source_sha256!==entry.source_sha256)throw Error('影响源码版本不符');
   if(AnalysisUI.openBound(result)){$('impact-dialog').close();showView('analysis');}
  }catch(error){if(stamp===version)toast(error.message);}
 }
 function paint(){
  controls();$('impact-identity').textContent=report.candidate_id;
  $('impact-tree').textContent='第 '+report.attempt+' 轮 · '+report.tree_hash;
  $('impact-notice').textContent=report.error||report.progress||'先查看本地改动；生成对比会向课题组 MCP 发送本候选前后的生产源码，不调用模型。';
  $('impact-files').replaceChildren(...report.files.map(file=>{
   const section=make('section','impact-file');section.append(make('h3','',file.path));
   const functions=file.changes.functions.map(f=>(f.side==='before'?'前 ':'后 ')+f.name+' L'+f.start_line+'–'+f.end_line);
   section.append(make('p','evidence-note','函数位置（源码文本定位）：'+(functions.join('；')||'没有定位到函数体内修改')));
   const grid=make('div','impact-grid');
   for(const side of ['before','after']){
    const observation=file[side],graph=observation?.display_graph||observation?.graph,column=make('section','impact-side'),head=make('div','evidence-heading');
    head.append(make('strong','',side==='before'?'修复前 · 基线':'修复后 · 本候选'));
    if(observation){const view=make('button','text-button','原图与切片');view.onclick=()=>inspect(file,side);head.append(view);}
    column.append(head,codeSnippet(file[side+'_code'],file.changes[side+'_lines'],side));
    if(observation){
     column.append(make('code','evidence-hash',observation.source_sha256),make('p','evidence-note',(observation.slice_scope==='VARIABLE_TABLE'?'变量切片表 · 定位 L':'请求 L')+observation.slice_criterion.line+' · '+(observation.reused?'复用同版本同参数证据':'本次分析')+' · '+observation.status));
     const tools=make('div','impact-tools');for(const t of observation.tools)tools.append(make('span','tiny-badge',names[t.tool]+' '+t.status));column.append(tools);
     const g=graph,type=(g.graph_type||'Ddg').toUpperCase();
     column.append(make('p','evidence-note',type+' 原图 '+g.total_nodes+' 节点 / '+g.total_edges+' 边 · 展示 '+g.nodes.length+' 相关节点'+(g.graph_count>1?' · 第 '+(g.graph_index+1)+'/'+g.graph_count+' 张 '+type:'')+(g.truncated?' · 已截断':'')));
    }
    column.append(drawGraph(graph,side,pendingSide(file,side)));grid.append(column);
   }
   section.append(grid);return section;
  }));
 }
 $('impact-open').onclick=open;$('impact-generate').onclick=()=>load(true);
 return{render};
})();
