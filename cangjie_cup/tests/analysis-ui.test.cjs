'use strict';
const test=require('node:test');const assert=require('node:assert/strict');
const {layoutGraph,sliceLines,AnalysisSession}=require('../nexus/demo/static/analysis-core.js');
const core=require('../nexus/demo/static/analysis-core.js');
const graph={nodes:[{id:'a',label:'[L2]: result = a + b',line:2},{id:'b',label:'[L3]: return result',line:3},{id:'c',label:'(formal-in)%a',line:null}],edges:[{from:'c',to:'a'},{from:'a',to:'b'}]};

test('diagram layout preserves every original node and dependency edge',()=>{
 const layout=layoutGraph(graph);assert.deepEqual(new Set(layout.nodes.map(n=>n.id)),new Set(['a','b','c']));assert.deepEqual(layout.edges,graph.edges);
 assert.equal(layout.nodes.find(n=>n.id==='c').line,null);assert.equal(new Set(layout.nodes.map(n=>n.x+','+n.y)).size,3);
});
test('cycles and self loops still produce finite visible positions without invented edges',()=>{
 const cyclic={nodes:graph.nodes,edges:[{from:'a',to:'b'},{from:'b',to:'a'},{from:'c',to:'c'}]};const layout=layoutGraph(cyclic);
 assert.equal(layout.nodes.length,3);assert.deepEqual(layout.edges,cyclic.edges);assert.ok(layout.nodes.every(n=>Number.isFinite(n.x)&&Number.isFinite(n.y)));
});
test('source highlights come only from the selected valid tool slice',()=>{
 const result={observations:[{tool:'sympas_slice',status:'VALID',data:{slices:{'result@add':[2,3]}}}]};
 assert.deepEqual([...sliceLines(result,'result@add')],[2,3]);assert.deepEqual([...sliceLines(result,'missing')],[]);
 result.observations[0].status='FAILED';assert.deepEqual([...sliceLines(result,'result@add')],[]);
});
test('legacy log recovery no longer supplies slice highlights',()=>{
 const report={source:{source_sha256:'source'},observations:[{tool:'sympas_slice',status:'FAILED',raw_sha256:'raw'}],
  derived_slice:{status:'RECOVERED',origin:'TOOL_LOG',parser_version:'sympas-text-v1',source_sha256:'source',raw_sha256:'raw',slices:{'a@f':[2,4]}}};
 assert.deepEqual([...sliceLines(report,'a@f')],[]);assert.equal(report.observations[0].status,'FAILED');
 assert.equal(core.sliceView(report).recovered,false);
 report.derived_slice.source_sha256='other-source';assert.deepEqual([...sliceLines(report,'a@f')],[]);
});
test('native JSON remains preferred over a log recovery, and rejected recovery has no highlighter',()=>{
 const report={source:{source_sha256:'s'},observations:[{tool:'sympas_slice',status:'VALID',data:{slices:{v:[1]}}}],
  derived_slice:{status:'RECOVERED',origin:'TOOL_LOG',source_sha256:'s',slices:{v:[3]}}};
 assert.deepEqual([...sliceLines(report,'v')],[1]);assert.equal(core.sliceView(report).recovered,false);
 report.observations[0].status='FAILED';report.derived_slice.status='REJECTED';assert.deepEqual([...sliceLines(report,'v')],[]);
});
test('late sample or upload response cannot overwrite a newer source selection',()=>{
 const session=new AnalysisSession();const a=session.select();const b=session.select();assert.equal(session.apply(a,{id:'old'}),false);assert.equal(session.apply(b,{id:'new'}),true);assert.equal(session.report.id,'new');
});
test('startup and running states prevent changing source under an in-flight request',()=>{
 const session=new AnalysisSession();const token=session.select();assert.equal(session.start(),token);assert.equal(session.start(),null);assert.equal(session.select(),null);
 session.apply(token,{id:'job',status:'RUNNING'});assert.equal(session.select(),null);session.apply(token,{id:'job',status:'PARTIAL'});assert.notEqual(session.select(),null);
});
test('a fresh upload clears every old slice and graph before its request starts',()=>{
 const session=new AnalysisSession();const a=session.select();session.apply(a,{id:'sample',status:'COMPLETE',observations:[{tool:'sympas_dep_graph'}]});session.select();assert.equal(session.report,null);
});

test('native sympas_slice takes precedence over a legacy table, and its failure does not fall back',()=>{
 const report={source:{source_sha256:'s'},observations:[{tool:'sympas_slice_table',status:'VALID',data:{scope:'VARIABLE_TABLE',slices:{v:[2,3]}}},{tool:'sympas_slice',status:'VALID',data:{slices:{v:[1]}}}]};
 assert.deepEqual([...sliceLines(report,'v')],[1]);
 report.observations[1].status='INVALID';
 assert.deepEqual([...sliceLines(report,'v')],[]);
});

function uiReport(depStatus='INVALID'){
 return {status:'PARTIAL',observations:[
  {tool:'sympas_slice',status:'VALID',data:{slices:{x:[2,3]}}},
  {tool:'sympas_dep_graph',status:depStatus,reason:'依赖边端点不存在',data:{}},
  {tool:'ast_symbol_extractor',status:'VALID',data:{symbols:[{symbol:'x'}]}}
 ]};
}
test('display status ignores DDG-only validation when every displayed result is available without rewriting evidence',()=>{
 const report=uiReport(),before=JSON.stringify(report);
 assert.equal(core.analysisDisplayStatus(report,{graphsReady:true}),'COMPLETE');
 assert.equal(JSON.stringify(report),before);
 assert.equal(core.analysisDisplayStatus(uiReport('EMPTY'),{graphsReady:true}),'COMPLETE');
});
test('missing original graphs, invalid PDG or failed slices and symbols retain a partial result',()=>{
 assert.equal(core.analysisDisplayStatus(uiReport(),{graphsReady:false}),'PARTIAL');
 for(const tool of ['sympas_slice','ast_symbol_extractor']){
  const report=uiReport();report.observations.find(o=>o.tool===tool).status='FAILED';
  assert.equal(core.analysisDisplayStatus(report,{graphsReady:true}),'PARTIAL');
 }
 const report=uiReport();report.point_graph={status:'INVALID',reason:'bad PDG'};
 assert.equal(core.analysisDisplayStatus(report,{graphsReady:true}),'PARTIAL');
});
test('tool execution errors, incomplete observations and terminal failures cannot be promoted',()=>{
 for(const state of ['FAILED','IN_DOUBT','RUNNING','READY']){
  const report=uiReport();report.status=state;
  assert.equal(core.analysisDisplayStatus(report,{graphsReady:true}),state);
 }
 for(const state of ['FAILED','UNAVAILABLE'])assert.equal(core.analysisDisplayStatus(uiReport(state),{graphsReady:true}),'PARTIAL');
 const report=uiReport();report.error='分析未完整结束';assert.equal(core.analysisDisplayStatus(report,{graphsReady:true}),'PARTIAL');
 delete report.error;report.observations.pop();assert.equal(core.analysisDisplayStatus(report,{graphsReady:true}),'PARTIAL');
});
