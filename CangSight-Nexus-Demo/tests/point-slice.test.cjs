'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const core=require('../nexus/demo/static/analysis-core.js');
const report={status:'COMPLETE',source:{source_sha256:'source',line_count:7},point_graph:{status:'VALID',source_sha256:'source',raw_sha256:'raw',graph:{nodes:[{id:'a',line:2},{id:'first',line:3},{id:'b',line:4},{id:'second',line:5}],edges:[{from:'a',to:'first'},{from:'b',to:'second'}]}}};
test('point slicing recomputes reverse reachability for each target without selecting a variable row',()=>{
 assert.deepEqual(core.pointSlice(report,3).lines,[2,3]);assert.deepEqual(core.pointSlice(report,5).lines,[4,5]);
 assert.deepEqual(core.pointSlice(report,7).lines,[]);
});
test('point slicing follows cyclic predecessor edges, preserves later loop nodes, and rejects source mismatch',()=>{
 const r=structuredClone(report);r.point_graph.graph.edges.push({from:'second',to:'b'});
 assert.deepEqual(core.pointSlice(r,4).lines,[4,5]);
 r.point_graph.source_sha256='other';assert.deepEqual(core.pointSlice(r,4).lines,[]);
 r.point_graph.status='INVALID';assert.notEqual(core.pointSlice(r,4).status,'VALID');
});
