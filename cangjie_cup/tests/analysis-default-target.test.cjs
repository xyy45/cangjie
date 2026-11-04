const test=require('node:test'),assert=require('node:assert/strict');
const core=require('../nexus/demo/static/analysis-core.js');
const source={filename:'sum3.cj',code:'/* return fake;\n let fake = 2; */\npublic func add(a: Int64, b: Int64): Int64 {\n    return a + b\n}\n\nmain() {\n    let result = add(5, 6)\n    println(result)\n}\n',line_count:10,source_sha256:'sum'};
test('initial target uses a statement candidate rather than comments, declarations or braces',()=>{
 assert.equal(core.defaultTargetLine(source),4);
 assert.equal(core.defaultTargetLine(source,null,8),8);
 assert.equal(core.defaultTargetLine(source,null,5),4);
});
test('verified source-bound PDG statement locations take priority over source guesses',()=>{
 const report={point_graph:{status:'VALID',source_sha256:'sum',graph:{nodes:[{line:8},{line:9},{line:null}]}}};
 assert.equal(core.defaultTargetLine(source,report,4),8);
 assert.equal(core.defaultTargetLine(source,report,9),9);
 assert.equal(core.defaultTargetLine(source,{point_graph:{...report.point_graph,source_sha256:'other'}},9),9);
});
test('explicit preferred target is never treated as a node without source-bound evidence',()=>{
 const braces={code:'// no executable statement\n}\n',line_count:2,source_sha256:'empty'};
 assert.equal(core.defaultTargetLine(braces),1);
 assert.equal(core.defaultTargetLine({code:'public func f(): Int64 { return 1 }\n',line_count:1}),1);
});
