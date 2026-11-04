(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.AnalysisCore=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
'use strict';
// A source-only choice is a navigation hint; verified PDG nodes are authoritative.
function defaultTargetLine(source,report=null,preferred=report?.slice_criterion?.line){
 const graph=report?.point_graph;
 let lines=[];
 if(graph?.status==='VALID'&&typeof source?.source_sha256==='string'&&graph.source_sha256===source.source_sha256&&Array.isArray(graph.graph?.nodes)){
  lines=[...new Set(graph.graph.nodes.map(n=>n.line).filter(n=>Number.isInteger(n)&&n>=1&&n<=source.line_count))].sort((a,b)=>a-b);
 }else{
  const code=(source?.code||'').replace(/"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\/\*[\s\S]*?\*\/|\/\/[^\r\n]*/g,
   token=>token.startsWith('/')?token.replace(/[^\r\n]/g,' '):token);
  lines=code.split(/\r\n|\n|\r/).flatMap((text,index)=>{
   const line=text.trim();
   if(/^(?:if|else|for|while|do|switch|try|catch|finally|main)\b/.test(line))return [];
   return /^(?:(?:let|var|return|throw|break|continue)\b|(?:[A-Za-z_]\w*\.)*[A-Za-z_]\w*\s*(?:\(|[+\-*/%]?=(?!=)))/.test(line)?[index+1]:[];
  });
 }
 return lines.includes(preferred)?preferred:lines[0]||1;
}
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
 const native=result?.observations?.find(o=>o.tool==='sympas_slice');
 if(native)return {slices:native.status==='VALID'?native.data.slices:{},recovered:false};
 const table=result?.observations?.find(o=>o.tool==='sympas_slice_table');
 return {slices:table?.status==='VALID'&&table.data?.scope==='VARIABLE_TABLE'?table.data.slices:{},recovered:false};
}
function sliceLines(result,symbol){return new Set(sliceView(result).slices?.[symbol]||[]);}
// Presentation excludes the retired DDG JSON only when all visible outputs exist.
// Never mutate the stored report or promote missing/failed analysis tools.
function analysisDisplayStatus(report,{graphsReady=false}={}){
 if(report?.status!=='PARTIAL'||report.error||!graphsReady||report.point_graph?.status==='INVALID')return report?.status;
 const observations=report.observations||[];
 if(observations.length!==3)return report.status;
 const byTool=new Map(observations.map(o=>[o.tool,o]));
 const slice=byTool.get('sympas_slice')||byTool.get('sympas_slice_table');
 const ddg=byTool.get('sympas_dep_graph'),symbols=byTool.get('ast_symbol_extractor');
 return byTool.size===3&&slice?.status==='VALID'&&symbols?.status==='VALID'&&['INVALID','EMPTY'].includes(ddg?.status)?'COMPLETE':report.status;
}
class AnalysisSession{
  constructor(){this.epoch=0;this.report=null;this.busy=false;}
  select(){if(this.busy)return null;this.epoch++;this.report=null;return this.epoch;}
  start(){if(this.busy)return null;this.busy=true;this.report=null;return this.epoch;}
  apply(token,report){if(token!==this.epoch)return false;this.report=report;this.busy=['READY','RUNNING'].includes(report.status);return true;}
  fail(token){if(token===this.epoch)this.busy=false;}
}
return {defaultTargetLine,layoutGraph,sliceLines,sliceView,analysisDisplayStatus,AnalysisSession};
});
