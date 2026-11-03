const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{constructor(){this.children=[];this.textContent='';this.hidden=false;}append(...xs){this.children.push(...xs);}replaceChildren(...xs){this.children=xs;}}
function page(){assert.ok(fs.existsSync('nexus/demo/static/exploration.js'),'independent search UI missing');const ctx={document:{createElement:()=>new Element()}};vm.createContext(ctx);vm.runInContext(fs.readFileSync('nexus/demo/static/exploration.js','utf8')+'\nglobalThis.ui=ExplorationUI;',ctx);return ctx.ui;}
function text(n){return [n.textContent,...n.children.map(text)].join(' ');}
const c={id:'c_one',tree_hash:'a'.repeat(64)};
test('search distinguishes public success, discovered rule failures, budget and shrinking',()=>{
 const ui=page(),box=new Element(),r={candidate_id:c.id,binding:{tree_hash:c.tree_hash,oracle_hash:'b'.repeat(64)},state:'FAIL',public_test_state:'PASS',search_cases:32,shrink_cases:4,regression_cases:1,seed:7,failures:[{args:[3],expected:'3',actual:'0'}]};
 ui.render(box,{events:[{type:'EXPLORATION_FINISHED',candidate_id:c.id,exploration:r}]},c,true);
 assert.match(text(box),/公开测试.*PASS/);assert.match(text(box),/发现反例/);assert.match(text(box),/32/);assert.match(text(box),/缩减/);assert.match(text(box),/输入.*\[3\].*预期.*3.*实际.*0/);assert.match(text(box),/有限/);
});
test('unavailable and stale candidate evidence never appears as passing',()=>{
 const ui=page(),box=new Element();ui.render(box,{events:[]},c,true);assert.match(text(box),/待搜索/);
 ui.render(box,{status:'TESTING',events:[{type:'EXPLORATION_STARTED',candidate_id:c.id}]},c,true);assert.match(text(box),/搜索中/);
 ui.render(box,{events:[{type:'EXPLORATION_FINISHED',candidate_id:c.id,exploration:{candidate_id:c.id,state:'PASS',binding:{tree_hash:'wrong'}}}]},c,true);
 assert.match(text(box),/绑定.*不符/);assert.doesNotMatch(text(box),/搜索通过/);
 ui.render(box,{events:[]},c,false);assert.equal(box.hidden,true);
});

test('public PASS cannot label the round passed while independent search is pending',()=>{
 const ui=page(),candidate={...c,build_state:'PASS',test_state:'PASS'};
 assert.equal(typeof ui.roundState,'function');
 assert.equal(ui.roundState({events:[]},candidate,true),'pending');
 assert.equal(ui.roundState({events:[{type:'EXPLORATION_STARTED',candidate_id:c.id}]},candidate,false),'pending');
 assert.equal(ui.roundState({events:[]},candidate,false),'passed');
});
test('nested object search arguments without canonical text cannot round Int64',()=>{const ui=page(),box=new Element(),o={$type:'S',fields:{n:9223372036854775807,items:[9223372036854775807]}};ui.render(box,{}, {...c,exploration:{candidate_id:c.id,binding:{tree_hash:c.tree_hash},state:'FAIL',failures:[{args:[o],actual:'0',expected:'1'}]}},true);assert.match(text(box),/精确输入待核对/);assert.doesNotMatch(text(box),/9223372036854776000/);});
