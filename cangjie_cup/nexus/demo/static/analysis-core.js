(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.AnalysisCore=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
'use strict';
function layoutGraph(graph){
  const edges=graph.edges.map(e=>({...e})),ids=new Set(graph.nodes.map(n=>n.id));
  const next=new Map([...ids].map(id=>[id,[]])),degree=new Map([...ids].map(id=>[id,0])),rank=new Map([...ids].map(id=>[id,0]));
  for(const edge of edges){if(!ids.has(edge.from)||!ids.has(edge.to))throw Error('Unbound dependency');next.get(edge.from).push(edge.to);degree.set(edge.to,degree.get(edge.to)+1);}
  const queue=[...ids].filter(id=>degree.get(id)===0);let cursor=0;
  while(cursor<queue.length){const id=queue[cursor++];for(const to of next.get(id)){rank.set(to,Math.max(rank.get(to),rank.get(id)+1));degree.set(to,degree.get(to)-1);if(degree.get(to)===0)queue.push(to);}}
  // Cyclic nodes use a separate visual column. Edges remain exactly as returned.
  const seen=new Set(queue),cycleRank=Math.max(0,...rank.values())+1;
  for(const id of ids)if(!seen.has(id))rank.set(id,cycleRank);
  const columns=new Map();for(const node of graph.nodes){const level=rank.get(node.id);if(!columns.has(level))columns.set(level,[]);columns.get(level).push(node);}
  const nodes=[];let rows=1;
  for(const [level,items] of columns){items.sort((a,b)=>(a.line??9999)-(b.line??9999)||a.id.localeCompare(b.id));rows=Math.max(rows,items.length);items.forEach((node,i)=>nodes.push({...node,x:36+level*240,y:36+i*86,width:208,height:52}));}
  return {nodes,edges,width:Math.max(320,84+(Math.max(0,...rank.values())+1)*240),height:Math.max(260,rows*86+72)};
}
function sliceView(result){
 const table=result?.observations?.find(o=>o.tool==='sympas_slice_table');
 if(table)return {slices:table.status==='VALID'&&table.data?.scope==='VARIABLE_TABLE'?table.data.slices:{},recovered:false};
 const observed=result?.observations?.find(o=>o.tool==='sympas_slice');
 if(observed?.status==='VALID')return {slices:observed.data.slices,recovered:false};
 const derived=result?.derived_slice;
 if(observed&&derived?.status==='RECOVERED'&&derived.origin==='TOOL_LOG'&&derived.parser_version==='sympas-text-v1'&&
    derived.source_sha256===result?.source?.source_sha256&&typeof derived.source_sha256==='string'&&
    derived.raw_sha256===observed.raw_sha256&&typeof derived.raw_sha256==='string')return {slices:derived.slices,recovered:true};
 return {slices:{},recovered:false};
}
function sliceLines(result,symbol){return new Set(sliceView(result).slices?.[symbol]||[]);}
function pointSlice(report,line){
 const source=report?.source,pg=report?.point_graph||{};
 const base={schema_version:1,algorithm:'pdg-backward-v1',origin:'LOCAL_PDG_BACKWARD',scope:'STATEMENT',analysis_id:report?.id,
  source_sha256:source?.source_sha256,filename:source?.filename,line,direction:'Bwd',status:'UNAVAILABLE',reason:pg.reason||'此记录没有有效PDG，请重新分析获取',
  seed_nodes:[],node_ids:[],lines:[],edges:[],raw_ref:pg.raw_ref,raw_sha256:pg.raw_sha256,graph_sha256:pg.graph_sha256};
 if(!Number.isInteger(line)||line<1||line>(source?.line_count||0))return {...base,status:'INVALID',reason:'切片目标行超出源码范围'};
 if(['READY','RUNNING','IN_DOUBT'].includes(report?.status)||pg.status!=='VALID'||pg.source_sha256!==source?.source_sha256)return base;
 const graph=pg.graph;if(!Array.isArray(graph?.nodes)||!graph.nodes.length||graph.nodes.length>500||!Array.isArray(graph.edges)||graph.edges.length>3000)return {...base,status:'INVALID',reason:'PDG结构无效'};
 const ids=new Set(graph.nodes.map(n=>n.id));
 if(ids.size!==graph.nodes.length||graph.nodes.some(n=>typeof n.id!=='string'||!n.id||n.line!=null&&(!Number.isInteger(n.line)||n.line<1||n.line>source.line_count))||graph.edges.some(e=>!ids.has(e.from)||!ids.has(e.to)))return {...base,status:'INVALID',reason:'PDG结构无效'};
 const seeds=graph.nodes.filter(n=>n.line===line).map(n=>n.id);
 if(!seeds.length)return {...base,status:'EMPTY',reason:'该行没有PDG语句节点，请选择可执行语句'};
 const previous=new Map(graph.nodes.map(n=>[n.id,[]]));for(const e of graph.edges)previous.get(e.to).push(e.from);
 const seen=new Set(seeds),todo=[...seeds];while(todo.length)for(const id of previous.get(todo.pop()))if(!seen.has(id)){seen.add(id);todo.push(id);}
 return {...base,status:'VALID',reason:'从目标语句沿PDG数据及控制依赖反向遍历',seed_nodes:[...seeds].sort(),node_ids:[...seen].sort(),
  lines:[...new Set(graph.nodes.filter(n=>seen.has(n.id)&&n.line!=null).map(n=>n.line))].sort((a,b)=>a-b),edges:graph.edges.filter(e=>seen.has(e.from)&&seen.has(e.to))};
}
class AnalysisSession{
  constructor(){this.epoch=0;this.report=null;this.busy=false;}
  select(){if(this.busy)return null;this.epoch++;this.report=null;return this.epoch;}
  start(){if(this.busy)return null;this.busy=true;this.report=null;return this.epoch;}
  apply(token,report){if(token!==this.epoch)return false;this.report=report;this.busy=['READY','RUNNING'].includes(report.status);return true;}
  fail(token){if(token===this.epoch)this.busy=false;}
}
return {layoutGraph,sliceLines,sliceView,pointSlice,AnalysisSession};
});
