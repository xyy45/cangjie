const test=require('node:test');
const assert=require('node:assert/strict');
const {DemoFlow}=require('../nexus/demo/static/flow.js');

test('replay stops for explicit review and never auto-accepts',()=>{
  const f=new DemoFlow().start();
  for(let i=0;i<10;i++)f.tick();
  assert.equal(f.stage,5);assert.equal(f.status,'REVIEW_PENDING');
  assert.equal(f.running,false);f.accept();assert.equal(f.status,'DELIVERED');
});
test('policy denial cannot advance to review or delivery',()=>{
  const f=new DemoFlow().start();for(let i=0;i<9;i++)f.tick(true);
  assert.equal(f.stage,3);assert.equal(f.status,'DENIED');f.accept();assert.equal(f.status,'DENIED');
});
test('pause, resume and reset do not retain acceptance',()=>{
  const f=new DemoFlow().start().tick().pause();f.tick();assert.equal(f.stage,0);
  f.start().tick();assert.equal(f.stage,1);f.reset();assert.equal(f.stage,-1);assert.equal(f.status,'READY');
});
test('rejection is terminal until reset',()=>{
  const f=new DemoFlow().start();for(let i=0;i<6;i++)f.tick();
  f.reject().accept().start().tick();assert.equal(f.status,'REJECTED');
});
