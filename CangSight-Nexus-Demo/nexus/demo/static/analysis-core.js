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
 const observed=result?.observations?.find(o=>o.tool==='sympas_slice');
 if(observed?.status==='VALID')return {slices:observed.data.slices,recovered:false};
 const derived=result?.derived_slice;
 if(observed&&derived?.status==='RECOVERED'&&derived.origin==='TOOL_LOG'&&derived.parser_version==='sympas-text-v1'&&
    derived.source_sha256===result?.source?.source_sha256&&typeof derived.source_sha256==='string'&&
    derived.raw_sha256===observed.raw_sha256&&typeof derived.raw_sha256==='string')return {slices:derived.slices,recovered:true};
 return {slices:{},recovered:false};
}
function sliceLines(result,symbol){return new Set(sliceView(result).slices?.[symbol]||[]);}
class AnalysisSession{
  constructor(){this.epoch=0;this.report=null;this.busy=false;}
  select(){if(this.busy)return null;this.epoch++;this.report=null;return this.epoch;}
  start(){if(this.busy)return null;this.busy=true;this.report=null;return this.epoch;}
  apply(token,report){if(token!==this.epoch)return false;this.report=report;this.busy=['READY','RUNNING'].includes(report.status);return true;}
  fail(token){if(token===this.epoch)this.busy=false;}
}
return {layoutGraph,sliceLines,sliceView,AnalysisSession};
});
