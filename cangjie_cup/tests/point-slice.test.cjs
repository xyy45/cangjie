const test=require('node:test'),assert=require('node:assert/strict');
const core=require('../nexus/demo/static/analysis-core.js');
test('browser no longer exports a local point-slice algorithm',()=>assert.equal(core.pointSlice,undefined));
test('local graph contents cannot create a slice in the absence of MCP rows',()=>{
 const r={point_graph:{status:'VALID',graph:{nodes:[{id:'n',line:2}],edges:[]}}};
 assert.deepEqual([...core.sliceLines(r,'result@main')],[]);
});
