'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{constructor(){this.children=[];this.textContent='';this.hidden=false;}append(...xs){this.children.push(...xs);}replaceChildren(...xs){this.children=xs;}}
function page(){assert.ok(fs.existsSync('nexus/demo/static/relations.js'),'relation UI missing');const ctx={document:{createElement:()=>new Element()}};vm.createContext(ctx);vm.runInContext(fs.readFileSync('nexus/demo/static/relations.js','utf8')+'\nglobalThis.ui=RelationUI;',ctx);return ctx.ui;}
const text=n=>[n.textContent,...n.children.map(text)].join(' ');
const c={id:'c',tree_hash:'a'.repeat(64),build_state:'PASS',test_state:'PASS'};
const failure={pair_id:'PAIR-one',relation_id:'REL-MONOTONE',relation_text:'<img onerror=alert(1)>',left_args:[9,100,false],right_args:[10,100,false],left_actual_return:900,right_actual_return:0,assertion_value:false,expected_relation:true,left_test_id:'Observed.case0',right_test_id:'Observed.case1'};
const report={candidate_id:'c',binding:{tree_hash:c.tree_hash,relations_hash:'b'.repeat(64)},state:'FAIL',public_test_state:'PASS',search_pairs:32,shrink_pairs:8,regression_pairs:1,observed_calls:80,distinct_failure_count:20,failures_truncated:true,per_relation:[{id:'REL-MONOTONE',generated:40,applicable:40,observed:40,failed:20}],failures:[failure]};
const task=r=>({events:[{type:'RELATION_FINISHED',candidate_id:'c',relations:r}]});
test('pair results show both actual calls, relation coverage, and truncation without numeric expected answers',()=>{
 const ui=page(),box=new Element();ui.render(box,task(report),c,true);const visible=text(box);
 assert.equal(box.hidden,false);assert.match(visible,/发现.*关系|关系.*违反/);assert.match(visible,/左.*\[9,100,false\]/);assert.match(visible,/右.*\[10,100,false\]/);
 assert.match(visible,/左.*实际返回.*900/);assert.match(visible,/右.*实际返回.*0/);assert.match(visible,/观测.*80/);assert.match(visible,/REL-MONOTONE/);
 assert.match(visible,/适用.*40/);assert.match(visible,/false/);assert.match(visible,/16.*20/);assert.match(visible,/Observed.case0/);assert.match(visible,/Observed.case1/);
 assert.match(visible,/<img/);assert.ok(!box.children.some(n=>n.innerHTML!==undefined));assert.doesNotMatch(visible,/预期返回/);
});
test('no configuration, stale report, raw historical PASS, and minimal UNKNOWN never manufacture passed state',()=>{
 const ui=page(),box=new Element();ui.render(box,{events:[]},c,false);assert.equal(box.hidden,true);assert.equal(ui.roundState({},c,false),'passed');assert.equal(ui.roundState({},c,true),'pending');
 const pass={...report,state:'PASS',failures:[]};assert.equal(ui.roundState(task(pass),c,true),'pending');assert.equal(ui.roundState({}, {...c,relations:pass},true),'passed');
 const unknown={candidate_id:'c',binding:{tree_hash:c.tree_hash},state:'UNKNOWN',reason:'证据已变化'};
 assert.equal(ui.roundState(task(pass),{...c,relations:unknown},true),'pending');ui.render(box,task(pass),{...c,relations:unknown},true);
 assert.match(text(box),/验证未完成/);assert.match(text(box),/证据已变化/);assert.doesNotMatch(text(box),/undefined|关系通过/);
 assert.equal(ui.roundState({}, {...c,relations:{...pass,binding:{tree_hash:'wrong'}}},true),'pending');
 assert.equal(ui.roundState(task(report),c,true),'failed');
 ui.render(box,{status:'TESTING',events:[{type:'RELATION_STARTED',candidate_id:'c'}]},c,true);assert.match(text(box),/验证中|执行中/);
});
test('canonical paired Int64 text remains distinct above JavaScript numeric precision',()=>{
 const ui=page(),box=new Element(),r={...report,failures:[{...failure,left_args:[9223372036854775806],right_args:[9223372036854775807],left_actual_return:9223372036854775806,right_actual_return:9223372036854775807,left_args_text:'[9223372036854775806]',right_args_text:'[9223372036854775807]',left_actual_return_text:'9223372036854775806',right_actual_return_text:'9223372036854775807'}]};
 ui.render(box,{}, {...c,relations:r},true);assert.match(text(box),/9223372036854775806/);assert.match(text(box),/9223372036854775807/);assert.doesNotMatch(text(box),/9223372036854776000/);
});
test('nested object arguments and returns without canonical text are held for exact display',()=>{const ui=page(),box=new Element(),o={$type:'S',fields:{n:9223372036854775807,items:[9223372036854775807]}};ui.render(box,{}, {...c,relations:{...report,failures:[{...failure,left_args:[o],right_args:[o],left_actual_return:o,right_actual_return:o}]}},true);assert.match(text(box),/精确输入待核对/);assert.match(text(box),/精确返回值待核对/);assert.doesNotMatch(text(box),/9223372036854776000/);});
