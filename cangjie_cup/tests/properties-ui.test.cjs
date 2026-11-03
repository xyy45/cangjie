const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{constructor(){this.children=[];this.textContent='';this.hidden=false;}append(...xs){this.children.push(...xs);}replaceChildren(...xs){this.children=xs;}}
function page(){assert.ok(fs.existsSync('nexus/demo/static/properties.js'),'property UI missing');const context={document:{createElement:()=>new Element()}};vm.createContext(context);vm.runInContext(fs.readFileSync('nexus/demo/static/properties.js','utf8')+'\nglobalThis.ui=PropertyUI;',context);return context.ui;}
const c={id:'c_one',tree_hash:'a'.repeat(64),build_state:'PASS',test_state:'PASS'};
const report={candidate_id:c.id,binding:{tree_hash:c.tree_hash,properties_hash:'b'.repeat(64)},state:'FAIL',public_test_state:'PASS',search_cases:32,shrink_cases:4,regression_cases:1,seed:7,failure_count:5,distinct_failure_count:3,failures_truncated:false,
 batches:[{result:{per_property:[{id:'PROP-RANGE',generated:32,applicable:30,observed:30,failed:5}]}}],
 failures:[{kind:'business_property',property_id:'PROP-RANGE',property_text:'<img src=x onerror=alert(1)>',args:[1000,900,200],actual_return:1100,assertion_value:false,expected_property:true}]};
function text(n){return[n.textContent,...n.children.map(text)].join(' ');}
function task(r=report){return{events:[{type:'PROPERTY_FINISHED',candidate_id:c.id,properties:r}]};}
test('actual property failures show observed returns and property conclusion without inventing expected values',()=>{
 const ui=page(),box=new Element();ui.render(box,task(),c,true);
 assert.equal(box.hidden,false);assert.match(text(box),/公开测试.*PASS/);assert.match(text(box),/发现.*属性|属性.*违反/);
 assert.match(text(box),/PROP-RANGE/);assert.match(text(box),/适用.*30/);assert.match(text(box),/实际返回.*1100/);
 assert.match(text(box),/断言.*false/);assert.match(text(box),/\[1000,900,200\]/);
 assert.match(text(box),/<img/);assert.ok(!box.children.some(n=>n.tagName==='IMG'));
 assert.doesNotMatch(text(box),/预期返回.*1100/);
});
test('missing stale unknown and interrupted properties never show candidate passed',()=>{
 const ui=page(),box=new Element();ui.render(box,{events:[]},c,false);assert.equal(box.hidden,true);
 assert.equal(ui.roundState({events:[]},c,false),'passed');assert.equal(ui.roundState({events:[]},c,true),'pending');
 ui.render(box,{status:'TESTING',events:[{type:'PROPERTY_STARTED',candidate_id:c.id}]},c,true);assert.match(text(box),/验证中|执行中/);
 const stale={...report,state:'PASS',binding:{tree_hash:'wrong'}};ui.render(box,task(stale),c,true);
 assert.match(text(box),/绑定.*不符/);assert.equal(ui.roundState(task(stale),c,true),'pending');
 assert.equal(ui.roundState(task(),c,true),'failed');assert.equal(ui.roundState(task({...report,state:'UNKNOWN'}),c,true),'pending');
 assert.equal(ui.roundState(task({...report,state:'PASS',failures:[]}),c,true),'pending');
 assert.equal(ui.roundState(task(),{...c,properties:{...report,state:'PASS',failures:[]}},true),'passed');
 ui.render(box,task({...report,state:'UNKNOWN',reason:'SDK observation incomplete'}),c,true);assert.match(text(box),/SDK observation incomplete/);
});
test('canonical property primitive text preserves distinct Int64 values above JavaScript precision',()=>{
 const ui=page(),box=new Element(),r=JSON.parse('{"candidate_id":"c_one","binding":{"tree_hash":"'+c.tree_hash+'"},"state":"FAIL","failures":[{"property_id":"PROP-SAME","property_text":"保持原值","args":[9223372036854775806],"actual_return":9223372036854775807,"args_text":"[9223372036854775806]","actual_return_text":"9223372036854775807","assertion_value":false,"expected_property":true}]}');
 ui.render(box,{}, {...c,properties:r},true);
 assert.match(text(box),/9223372036854775806/);assert.match(text(box),/9223372036854775807/);assert.doesNotMatch(text(box),/9223372036854776000/);
});
test('minimal invalidated evidence shows unknown without undefined statistics',()=>{
 const ui=page(),box=new Element();ui.render(box,{}, {...c,properties:{candidate_id:c.id,binding:{tree_hash:c.tree_hash},state:'UNKNOWN',reason:'证据已变化'}},true);
 assert.match(text(box),/验证未完成/);assert.match(text(box),/证据已变化/);assert.doesNotMatch(text(box),/undefined/);
});
test('page wires both required validators into round state and property panel',()=>{
 const html=fs.readFileSync('nexus/demo/templates/demo.html','utf8'),js=fs.readFileSync('nexus/demo/static/demo.js','utf8');
 assert.match(html,/id="cegis-properties"/);assert.match(html,/filename='properties.js'/);
 assert.match(js,/PropertyUI\.render/);assert.match(js,/PropertyUI\.roundState/);assert.match(js,/independent_properties/);
});
test('nested object property values without canonical text cannot round Int64',()=>{const ui=page(),box=new Element(),o={$type:'S',fields:{n:9223372036854775807,items:[9223372036854775807]}};ui.render(box,{}, {...c,properties:{...report,failures:[{...report.failures[0],args:[o],actual_return:o}]}},true);assert.match(text(box),/精确输入待核对/);assert.match(text(box),/精确返回值待核对/);assert.doesNotMatch(text(box),/9223372036854776000/);});
