'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{constructor(){this.children=[];this.textContent='';this.hidden=false;}append(...xs){this.children.push(...xs);}replaceChildren(...xs){this.children=xs;}}
function page(){assert.ok(fs.existsSync('nexus/demo/static/sequences.js'),'sequence UI missing');const ctx={document:{createElement:()=>new Element()}};vm.createContext(ctx);vm.runInContext(fs.readFileSync('nexus/demo/static/sequences.js','utf8')+'\nglobalThis.ui=SequenceUI;',ctx);vm.runInContext(fs.readFileSync('nexus/demo/static/feedback.js','utf8')+'\nglobalThis.feedback=FeedbackUI;',ctx);ctx.ui.feedback=ctx.feedback;return ctx.ui;}
const text=n=>[n.textContent,...n.children.map(text)].join(' ');
const c={id:'c',tree_hash:'a'.repeat(64),build_state:'PASS',test_state:'PASS'};
const source={log_ref:'records/sequence.log',coordinate:'ANSI_STRIPPED_FULL_LOG',start_char:10,end_char:20};
const failure={sequence_id:'SEQUENCE-one',test_id:'Observed.case0',kind:'business_sequence',initial_state:0,context:[10],observed_steps:2,planned_steps:3,unexecuted_steps:1,stop_reason:'MODEL_MISMATCH',end_source:source,failure_ids:['MODEL-OP-REFUND','INV-BOUND'],steps:[{step_index:0,operation_id:'OP-REFUND',operation_text:'退款 <img onerror=alert(1)>',args:[0,7,10],before_state:0,actual_return:7,expected_state:7,test_id:'Observed.case0',source},{step_index:1,operation_id:'OP-REFUND',operation_text:'退款',args:[7,7,10],before_state:7,actual_return:14,expected_state:10,test_id:'Observed.case0',source}]};
const report={candidate_id:'c',binding:{tree_hash:c.tree_hash,sequences_hash:'b'.repeat(64)},state:'FAIL',public_test_state:'PASS',search_traces:16,shrink_traces:8,regression_traces:2,search_planned_calls:48,shrink_planned_calls:16,observed_calls:60,distinct_failure_count:12,failures_truncated:true,per_operation:[{id:'OP-REFUND',planned:64,observed:60,model_mismatches:2}],per_invariant:[{id:'INV-BOUND',planned_applicable:64,observed:60,violations:2}],failures:[failure],batches:[{label:'search',result:{observed_calls:60,unexecuted_calls:4,observations:[failure]}}]};
const task=r=>({events:[{type:'SEQUENCE_FINISHED',candidate_id:'c',sequences:r}]});
test('full actual prefix displays state transitions real case step coordinates and unexecuted tail',()=>{
 const ui=page(),box=new Element();ui.render(box,task(report),{...c,sequences:report},true);const visible=text(box);
 assert.equal(box.hidden,false);assert.match(visible,/序列.*违反|状态.*偏离/);assert.match(visible,/初始.*0/);assert.match(visible,/上下文.*\[10\]/);
 assert.match(visible,/\[0,7,10\]/);assert.match(visible,/\[7,7,10\]/);assert.match(visible,/实际.*14/);assert.match(visible,/参考.*10/);
 assert.match(visible,/Observed.case0/);assert.match(visible,/step0/);assert.match(visible,/step1/);assert.match(visible,/records\/sequence.log/);
 assert.match(visible,/未执行.*1/);assert.match(visible,/累计回归.*2/);assert.match(visible,/8.*12/);assert.match(visible,/<img/);
 assert.doesNotMatch(visible,/undefined/);assert.ok(!box.children.some(n=>n.innerHTML!==undefined));
});
test('PASS displays all actual observed trajectories; UNKNOWN and historical event PASS do not imply verified success',()=>{
 const ui=page(),box=new Element();ui.render(box,{events:[]},c,false);assert.equal(box.hidden,true);assert.equal(ui.roundState({},c,false),'passed');
 const pass={...report,state:'PASS',failures:[],failures_truncated:false};ui.render(box,{}, {...c,sequences:pass},true);assert.match(text(box),/Observed.case0/);
 assert.equal(ui.roundState(task(pass),c,true),'pending');assert.equal(ui.roundState({}, {...c,sequences:pass},true),'passed');
 const unknown={candidate_id:'c',binding:{tree_hash:c.tree_hash},state:'UNKNOWN',reason:'原件变化'};ui.render(box,task(pass),{...c,sequences:unknown},true);
 assert.match(text(box),/原件变化/);assert.doesNotMatch(text(box),/undefined|序列通过/);assert.equal(ui.roundState({}, {...c,sequences:unknown},true),'pending');
 assert.equal(ui.roundState({}, {...c,sequences:{...pass,binding:{tree_hash:'other'}}},true),'pending');
});
test('exact Int64 state and argument display uses server canonical text',()=>{
 const ui=page(),box=new Element(),path={...failure,initial_state:9223372036854775806,initial_state_text:'9223372036854775806',context:[9223372036854775807],context_text:'[9223372036854775807]',steps:[{...failure.steps[1],before_state:9223372036854775806,before_state_text:'9223372036854775806',actual_return:9223372036854775807,actual_return_text:'9223372036854775807',expected_state:9223372036854775806,expected_state_text:'9223372036854775806',args:[9223372036854775806],args_text:'[9223372036854775806]'}]};
 ui.render(box,{}, {...c,sequences:{...report,failures:[path]}},true);assert.match(text(box),/9223372036854775806/);assert.match(text(box),/9223372036854775807/);assert.doesNotMatch(text(box),/9223372036854776000/);
});

test('repair feedback retains each actual step and exact expected state',()=>{
 const ui=page(),box=new Element();ui.feedback.render(box,{previous_candidate_id:'c',tree_hash:c.tree_hash,failure_cases:[failure]},c);
 const visible=text(box);assert.match(visible,/step0/);assert.match(visible,/step1/);assert.match(visible,/\[0,7,10\]/);assert.match(visible,/\[7,7,10\]/);assert.match(visible,/实际返回.*14/);assert.match(visible,/参考状态.*10/);assert.doesNotMatch(visible,/undefined/);
});
test('nested object states context and steps without canonical text cannot round Int64',()=>{const ui=page(),box=new Element(),o={$type:'S',fields:{n:9223372036854775807,items:[9223372036854775807]}};ui.renderPaths(box,[{...failure,initial_state:o,context:[o],steps:[{...failure.steps[0],args:[o],before_state:o,actual_return:o,expected_state:o}]}]);assert.match(text(box),/精确值待核对/);assert.match(text(box),/精确输入待核对/);assert.doesNotMatch(text(box),/9223372036854776000/);});
