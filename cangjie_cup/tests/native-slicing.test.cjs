const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const core=require('../nexus/demo/static/analysis-core.js'),graphs=require('../nexus/demo/static/native-graphs.js');
const full=[1,2,5,6,9,10,11,14,15,16];
const native={source:{source_sha256:'s'},slice_scope:'MCP_NATIVE',observations:[{tool:'sympas_slice',status:'VALID',data:{slices:{'result@main':full}}},{tool:'sympas_slice_table',status:'VALID',data:{scope:'VARIABLE_TABLE',slices:{'result@main':[11,14,15]}}}]};
test('native MCP rows win over old table and are not shortened to a local requested position',()=>{
 assert.deepEqual([...core.sliceLines({...native,slice_criterion:{line:2}},'result@main')],full);
});
test('failed native rows never fall back to a table, recovered log or local PDG',()=>{
 const report=structuredClone(native);report.observations[0].status='FAILED';
 report.derived_slice={status:'RECOVERED',origin:'TOOL_LOG',parser_version:'sympas-text-v1',source_sha256:'s',raw_sha256:'raw',slices:{'result@main':full}};
 report.observations[0].raw_sha256='raw';
 assert.deepEqual([...core.sliceLines(report,'result@main')],[]);
 assert.equal(core.sliceView(report).recovered,false);
});
test('local point traversal and its user controls are retired',()=>{
 assert.equal(core.pointSlice,undefined);
 const html=fs.readFileSync('nexus/demo/templates/demo.html','utf8');
 assert.doesNotMatch(html,/id="analysis-slice-mode"|id="analysis-point-download"/);
});
test('only DDG is removed and the six other native graph choices remain',()=>{
 assert.deepEqual(graphs.TYPES,['Sdg','Pdg','Cfg','Cg','Cdg','Dfg']);
 const report={status:'COMPLETE',source:{source_sha256:'s'},native_graphs:{schema_version:1,graphs:{Ddg:{status:'SAVED',graph_type:'Ddg',source_sha256:'s',view_url:'/api/analysis/x/graphs/Ddg.svg',download_url:'/api/analysis/x/graphs/Ddg.svg?download=1'}}}};
 assert.equal(graphs.asset(report,'Ddg').ready,false);
});
