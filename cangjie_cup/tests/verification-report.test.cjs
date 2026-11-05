'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const path='../nexus/demo/static/verification-report.js';
const api=fs.existsSync(require('node:path').join(__dirname,path))?require(path):{};
const candidate={id:'c',tree_hash:'tree',attempt:2};
function context(){return {mode:'real',candidate,current:{},task:{id:'t',events:[]},checks:[
 {id:'b',subject_id:'c',tree_hash:'tree',kind:'build',state:'PASS',exit_code:0,diagnostics:'build ok'},
 {id:'v',subject_id:'c',tree_hash:'tree',kind:'test',state:'FAIL',case_results:{'Target.edge':'FAIL','Regression.normal':'PASS'},suite_results:{target:{state:'FAIL',tests:['Target.edge']},regression:{state:'PASS',tests:['Regression.normal']}},diagnostics:'real failure',log_ref:'records/test.log'}
]};}
const build=x=>api.buildModel(x);
test('failed public test keeps distinct target and regression results, counts and every case',()=>{
 const m=build(context());assert.deepEqual(m.rows.map(r=>r.state),['PASS','FAIL','PASS']);
 assert.equal(m.rows[1].counts.failed,1);assert.equal(m.rows[2].counts.passed,1);
 assert.equal(m.cases.length,2);assert.equal(m.cases[0].id,'Target.edge');assert.equal(m.cases[1].suite,'回归测试');
});
test('missing suite mappings do not copy the aggregate test result',()=>{
 const c=context();c.checks[1].state='PASS';c.checks[1].case_results={'X.one':'PASS'};c.checks[1].suite_results={};
 const m=build(c);assert.deepEqual(m.rows.map(r=>r.state),['PASS','UNKNOWN','UNKNOWN']);assert.equal(m.cases[0].suite,'未分组');
});
test('UNKNOWN validation cannot display stale passing cases or suites',()=>{
 const c=context();c.checks[1].state='UNKNOWN';c.checks[1].case_results['Target.edge']='PASS';c.checks[1].suite_results.target.state='PASS';
 const m=build(c);assert.equal(m.rows[1].state,'UNKNOWN');assert.ok(m.cases.every(r=>r.state==='UNKNOWN'));
});
test('build failure retains diagnostics and shows tests as not run',()=>{
 const c=context();c.checks=c.checks.slice(0,1);c.checks[0].state='FAIL';c.checks[0].diagnostics='compiler syntax failure';
 const m=build(c);assert.deepEqual(m.rows.map(r=>r.state),['FAIL','NOT_RUN','NOT_RUN']);assert.match(m.diagnostics[0].text,/compiler syntax failure/);assert.equal(m.cases.length,0);
});
test('missing mapped cases are explicitly unknown, not counted as passed',()=>{
 const c=context();c.checks[1].suite_results.regression.tests.push('Regression.missing');
 const m=build(c);assert.equal(m.rows[2].state,'UNKNOWN');assert.equal(m.rows[2].counts.unknown,1);assert.equal(m.cases.length,3);
});
test('wrong candidate or tree checks never leak into the selected round',()=>{
 for(const field of ['subject_id','tree_hash']){
  const c=context();c.checks[1][field]='old';
  const m=build(c);assert.equal(m.rows[1].state,'UNKNOWN');assert.equal(m.cases.length,0);assert.ok(!m.diagnostics.some(d=>d.text==='real failure'));
 }
});
test('only feedback bound to the displayed candidate and tree is selected losslessly',()=>{
 const c=context(),feedback={previous_candidate_id:'c',tree_hash:'tree',failure_cases:[{kind:'test',test_id:'Target.edge',input:'f(9007199254740993)',expected:'9007199254740993',actual:'0'}]};
 c.task.events=[{repair_feedback:feedback},{repair_feedback:{...feedback,tree_hash:'other'}},{repair_feedback:{...feedback,previous_candidate_id:'old'}}];
 const before=JSON.stringify(c),m=build(c);assert.equal(m.feedback.failure_cases[0].expected,'9007199254740993');assert.equal(JSON.stringify(c),before);
});
test('loading a new round clears the previous report including feedback and diagnostics',()=>{
 const c=context();c.loading=true;c.task.events=[{repair_feedback:{previous_candidate_id:'c',tree_hash:'tree',failure_cases:[]}}];
 const m=build(c);assert.equal(m.cases.length,0);assert.equal(m.diagnostics.length,0);assert.equal(m.feedback,null);assert.ok(m.rows.every(r=>r.state==='NOT_RUN'));
});
test('advanced verification is separate from compilation and respects candidate binding',()=>{
 const c=context();c.current.independent_properties=true;c.candidate={...candidate,properties:{candidate_id:'c',binding:{tree_hash:'other'},state:'PASS'}};
 const m=build(c);assert.equal(m.advanced.find(r=>r.kind==='properties').state,'UNKNOWN');
});
class Node{constructor(){this.children=[];this.hidden=false;this.textContent='';this.dataset={};}append(...n){this.children.push(...n);}replaceChildren(...n){this.children=n;}setAttribute(){} }
function dom(){const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,new Node());return nodes.get(id);};return {get,document:{createElement:()=>new Node(),createTextNode:t=>Object.assign(new Node(),{textContent:t})}};}
const contents=n=>[n.textContent,...n.children.map(contents)].join(' ');
test('report DOM renders failed cases, real feedback, diagnostics and safely treats strings as text',()=>{
 const c=context();c.task.events=[{repair_feedback:{previous_candidate_id:'c',tree_hash:'tree',failure_cases:[{kind:'test',test_id:'Target.edge',input:'f(1)',expected:'2',actual:'<script>bad</script>'}]}}];
 const d=dom(),ctx={document:d.document};vm.createContext(ctx);
 vm.runInContext(fs.readFileSync('nexus/demo/static/feedback.js','utf8')+'\nglobalThis.F=FeedbackUI;',ctx);
 api.render(build(c),{...d,renderers:{feedback:ctx.F}});
 assert.match(contents(d.get('test-list')),/Target.edge/);assert.match(contents(d.get('test-list')),/失败/);
 assert.match(contents(d.get('report-counterexamples')),/f\(1\)/);assert.match(contents(d.get('report-counterexamples')),/<script>bad<\/script>/);
 assert.match(contents(d.get('report-diagnostics')),/real failure/);
});

test('newest mismatched check cannot reveal an older matching pass',()=>{
 const c=context();c.checks.push({...c.checks[1],tree_hash:'old',state:'UNKNOWN'});
 const m=build(c);assert.equal(m.rows[1].state,'UNKNOWN');assert.equal(m.cases.length,0);
});

test('terminal control sequences are cleaned for display without changing stored diagnostics',()=>{
 const c=context(),raw='\x1b[31mcompiler failed\x1b[0m\x1b7';c.checks[0].diagnostics=raw;
 const d=dom();api.render(build(c),d);assert.match(contents(d.get('report-diagnostics')),/compiler failed/);
 assert.doesNotMatch(contents(d.get('report-diagnostics')),/\x1b/);assert.equal(c.checks[0].diagnostics,raw);
});

test('switching from advanced evidence to a loading round clears old sections',()=>{
 const d=dom(),ctx={document:d.document};vm.createContext(ctx);
 vm.runInContext(fs.readFileSync('nexus/demo/static/properties.js','utf8')+'\nglobalThis.P=PropertyUI;',ctx);
 const c=context();c.current.independent_properties=true;c.candidate={...candidate,properties:{candidate_id:'c',binding:{tree_hash:'tree'},state:'PASS',search_cases:18}};
 api.render(build(c),{...d,renderers:{properties:ctx.P}});assert.equal(d.get('report-advanced').hidden,false);assert.match(contents(d.get('report-properties')),/18/);
 c.loading=true;api.render(build(c),{...d,renderers:{properties:ctx.P}});assert.equal(d.get('report-advanced').hidden,true);assert.equal(contents(d.get('report-properties')).trim(),'');
});
