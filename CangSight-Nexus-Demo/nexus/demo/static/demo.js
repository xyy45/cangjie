'use strict';
const $=id=>document.getElementById(id);
const csrf=document.querySelector('meta[name="csrf-token"]').content;
const icons={order:'code',multifile:'file',policy:'shield'};
const states={READY:'就绪',RUNNING:'运行中',PAUSED:'已暂停',REVIEW_PENDING:'待审阅',DELIVERED:'已交付',DENIED:'已拦截',REJECTED:'已拒绝',BLOCKED:'运行受阻',IN_DOUBT:'待核实',UNREPAIRED:'未修复',CANCELLED:'已取消'};
let flow=new DemoFlow(),current,caseId='order',mode='real',timer,epoch=0,fileIndex=0,realTask=null,realCandidate=null,downloadUrl='',toastTimer,revision,realChecks=[],catalog=[],reviewBusy=false,starting=false;
let selectedRound=null,roundEpoch=0,roundLoading=false;
let history=[];try{history=JSON.parse(localStorage.getItem('cangsight-demo-history')||'[]');if(!Array.isArray(history))history=[];}catch{history=[];}
const icon=name=>{const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');const use=document.createElementNS(svg.namespaceURI,'use');use.setAttribute('href','#i-'+name);svg.append(use);return svg;};
function toast(text){clearTimeout(toastTimer);$('toast').textContent=text;$('toast').hidden=false;toastTimer=setTimeout(()=>$('toast').hidden=true,3000);}
async function api(path,body){
  const response=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','Origin':location.origin,'X-CSRF-Token':csrf},body:JSON.stringify(body)});
  const data=await response.json();
  if(!response.ok){const labels={ANALYSIS_BUSY:'已有分析正在运行，请稍后',ENVIRONMENT_NOT_READY:'环境未就绪',CHECKS_NOT_PASS:'检查未通过',APPROVAL_INVALID:'批准已失效',EXPORT_BLOCKED:'导出受阻',RESULT_IN_DOUBT:'结果待核实',OWNER_UNCONFIRMED:'实例被占用'};const error=new Error(labels[data.code]||'操作失败');error.code=data.code;throw error;}return data;
}
function showView(view){document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===view));for(const name of ['workspace','analysis','history','deliveries'])$(name+'-view').hidden=name!==view;$('execution-modes').hidden=view==='analysis';document.body?.classList.toggle('analysis-active',view==='analysis');if(view==='analysis'&&typeof AnalysisUI!=='undefined')AnalysisUI.show();else if(current)render();renderHistory();}
function tab(name){document.querySelectorAll('[data-tab]').forEach(b=>{b.classList.toggle('active',b.dataset.tab===name);b.setAttribute('aria-selected',String(b.dataset.tab===name));});for(const key of ['code','report','logs'])$(key+'-tab').hidden=key!==name;}
function invalidate(){clearTimeout(timer);epoch++;}
async function selectCase(id,showWorkspace=true){
  if(starting){toast('正在启动');return;}if(reviewBusy){toast('正在交付');return;}if(realTask&&flow.running){toast('请先取消');return;}
  invalidate();const version=epoch;try{const data=await api('/demo/cases/'+id);if(version!==epoch)return;current=data;current.replay_files=data.files;caseId=id;fileIndex=0;flow.reset();realTask=null;realCandidate=null;realChecks=[];selectedRound=null;roundEpoch++;roundLoading=false;downloadUrl='';
    document.querySelectorAll('.case-button').forEach(b=>b.classList.toggle('selected',b.dataset.case===id));
    $('case-title').textContent=data.title;$('case-category').textContent=data.category;$('requirement-text').textContent=data.requirement;
    if(!data.can_replay)mode='real';syncMode();render();if(showWorkspace)showView('workspace');return {epoch,id:caseId};
  }catch(error){toast(error.message);return null;}
}
function setMode(value){
  if(starting){toast('正在启动');return;}if(reviewBusy){toast('正在交付');return;}if(realTask&&flow.running){toast('请先取消');return;}
  if(value==='replay'&&!current.can_replay){toast('此案例请生成');return;}
  invalidate();mode=value;flow.reset();realTask=null;realCandidate=null;downloadUrl='';realChecks=[];selectedRound=null;roundEpoch++;roundLoading=false;
  syncMode();render();
}
function syncMode(){
  for(const v of ['replay','real']){$('mode-'+v).classList.toggle('selected',mode===v);$('mode-'+v).setAttribute('aria-pressed',String(mode===v));}
  $('mode-replay').disabled=!current.can_replay;$('speed').disabled=mode==='real';
  current.files=mode==='real'?(current.real_files||current.files):(current.replay_files||current.files);fileIndex=0;
  $('files').replaceChildren(...current.files.map((f,i)=>{const b=document.createElement('button');b.className='file-button';b.append(icon('file'),document.createTextNode(f.path.split('/').pop()));b.onclick=()=>{fileIndex=i;renderCode();};return b;}));
}
function realSource(){return current?.kind==='probe'?'原生':(realTask?.events||[]).some(e=>e.type==='RULE_PROPOSAL')?'规则':'DeepSeek';}
function realTokens(){return (realTask?.model_calls||[]).filter(c=>c.status!=='STARTED').reduce((sum,c)=>sum+(Number(c.usage?.total_tokens)||0),0);}
function latestCheck(kind){return realChecks.findLast(c=>c.kind===kind);}

function num(id,value,suffix=''){const node=$(id);node.replaceChildren();node.append(document.createTextNode(value===null||value===undefined?'—':String(value)));if(suffix&&value!==null&&value!==undefined){const s=document.createElement('span');s.className='unit';s.textContent=suffix;node.append(s);}}
function render(){
  if(!current)return;
  const real=mode==='real',stage=flow.stage,verified=real?latestCheck('build')?.state==='PASS'&&latestCheck('test')?.state==='PASS':stage>=4&&flow.status!=='DENIED';
  const source=real?realSource():current.source_label;
  if($('analysis-view').hidden!==false){$('source-badge').textContent=source;$('source-badge').dataset.origin=real?(current.kind==='probe'?'REAL_NATIVE':source==='规则'?'REAL_RULE':'REAL_AI'):current.origin;}
  $('editor-origin').textContent=source;$('provider-badge').textContent=real?source:current.provider;
  const running=flow.running,status=states[flow.status]||flow.status;
  $('run-status').textContent=status;$('run-status').className='status '+(flow.status==='DELIVERED'?'good':flow.status==='DENIED'||flow.status==='REJECTED'?'bad':flow.status==='REVIEW_PENDING'?'pending':'neutral');
  $('review-status').textContent=flow.status==='READY'?'待运行':status;
  $('review-dot').className='review-dot '+(flow.status==='REVIEW_PENDING'?'ready':flow.status==='DELIVERED'?'finished':'');
  $('start').disabled=['REVIEW_PENDING','DELIVERED','DENIED','REJECTED','BLOCKED','IN_DOUBT','UNREPAIRED','CANCELLED'].includes(flow.status);
  $('start').querySelector('span').textContent=real&&running?'运行中':running?'暂停':flow.status==='PAUSED'?'继续':'开始';
  if(real&&running)$('start').disabled=true;
  $('reset').textContent=real&&running?'取消':'重置';
  $('accept').disabled=reviewBusy||flow.status!=='REVIEW_PENDING'||(real&&(!currentReview()||!realCandidate?.check_set_hash));$('reject').disabled=reviewBusy||flow.status!=='REVIEW_PENDING'||(real&&!currentReview());
  $('download').hidden=flow.status!=='DELIVERED'||!downloadUrl;if(downloadUrl)$('download').href=downloadUrl;
  $('accept').hidden=flow.status==='DELIVERED';$('reject').hidden=flow.status==='DELIVERED';
  const m=current.metrics;num('metric-files',stage>=2?real?(current.kind==='probe'?0:realCandidate?.edits?.length??null):m.files:null);
  num('metric-tests',verified?real?latestCheck('test')?.counts?.passed:m.tests:null);
  num('metric-candidates',stage>=2?real?(realTask?.attempt_count??0):m.candidates:null);
  num('metric-time',real?realDuration():(verified&&m.seconds!==null?m.seconds.toFixed(2):null),'s');
  num('metric-tokens',stage>=2?(real?realTokens():m.tokens):null);
  $('pipeline').replaceChildren(...current.stages.map((label,i)=>{const li=document.createElement('li');const done=i<stage||flow.status==='DELIVERED';li.className=(done?'done':i===stage?'current':'')+(flow.status==='DENIED'&&i===3?' failed':'');const circle=document.createElement('span');circle.className='step-number';circle.textContent=done?'✓':flow.status==='DENIED'&&i===3?'×':String(i+1).padStart(2,'0');const text=document.createElement('span');text.className='step-label';text.textContent=label;li.append(circle,text);return li;}));
  const native=real?policyRecords(realTask?.events||[]).at(-1):null,decision=native?.native?native.decision.decision:null;
  const verdict={Allow:'允许执行',Deny:'拒绝执行',NeedApproval:'需要审批'};
  $('policy-verdict').className='verdict '+(decision==='Allow'?'allowed':decision==='Deny'?'denied':decision==='NeedApproval'?'approval':'');
  $('policy-verdict').replaceChildren(icon('shield'),Object.assign(document.createElement('strong'),{textContent:real?(verdict[decision]||'待检查'):'历史回放'}));
  const policyRows=[['动作',native?.request?.action||'—'],['原因',native?.decision?.reason||'尚未取得决策'],['执行',native?.outcome?(native.outcome.action_executed?'工具返回 '+native.outcome.operation_status:'未执行动作'):'尚无执行记录']];
  $('policy-rules').replaceChildren(...policyRows.map(([label,value])=>{const d=document.createElement('div');d.className='rule-item';d.append(Object.assign(document.createElement('span'),{textContent:label}),Object.assign(document.createElement('span'),{textContent:value}));return d;}));
  $('approval-probe').disabled=mode!=='real'||flow.status!=='REVIEW_PENDING'||reviewBusy;
  $('requirement-list').replaceChildren(...current.requirements.map((label,i)=>{const supported=real?(current.kind==='probe'&&flow.status==='DENIED'||(realCandidate?.requirement_results||[]).find(r=>r.id===current.requirement_ids?.[i])?.status==='SATISFIED_BY_TESTS'):verified;const d=document.createElement('div');d.className='requirement-item '+(supported?'checked':'');d.append(document.createTextNode(label),icon('check'));return d;}));
  const rows=['工程构建','目标行为','回归测试'].map((name,i)=>{const check=real?latestCheck(i===0?'build':'test'):null;const pass=real?check?.state==='PASS':verified&&current.verdict!=='DENY';return {name,pass,state:real?(check?.state||'NOT_RUN'):(pass?'PASS':'NOT_RUN')};});
  $('checks').replaceChildren(...rows.map(r=>{const d=document.createElement('div');d.className='check-item '+(r.pass?'passed':'');const left=document.createElement('span');left.className='check-icon';left.append(icon('check'),document.createTextNode(r.name));const value=document.createElement('span');value.textContent=r.pass?'通过':r.state==='FAIL'?'失败':r.state==='UNKNOWN'?'未知':'—';d.append(left,value);return d;}));
  $('report-checks').replaceChildren(...rows.map(r=>{const d=document.createElement('div');d.className='report-check';const state=document.createElement('span');state.className=r.pass?'green':'';state.textContent=r.pass?'通过':r.state==='FAIL'?'失败':'—';d.append(document.createTextNode(r.name),state);return d;}));
  let tests=verified?(real?Object.entries(latestCheck('test')?.case_results||{}).map(([name,state])=>({name:name.split('.').pop(),state})):current.tests):[];
  $('test-list').replaceChildren(...tests.map(t=>{const d=document.createElement('div');d.className='test-item';d.append(icon('check'),document.createTextNode(t.name),Object.assign(document.createElement('span'),{className:'test-state',textContent:t.state.endsWith('PASS')?'通过':t.state}));return d;}));
  const logs=real?(realTask?.events||[]).map(e=>e.stop_reason||e.type+(e.status?' · '+e.status:'')):current.logs.slice(0,stage<0?0:Math.min(current.logs.length,stage+2));
  $('event-log').replaceChildren(...logs.map((l,i)=>{const d=document.createElement('div');d.className='log-line';d.append(Object.assign(document.createElement('span'),{textContent:String(i+1).padStart(2,'0')}),Object.assign(document.createElement('span'),{textContent:l}));return d;}));
  renderRounds();$('identity').textContent=real?(realCandidate?.tree_hash?.slice(0,12)||'—'):(stage>=2?(current.identity?.slice(0,12)||source):'—');renderCode();
  if(typeof EvidenceUI!=='undefined')EvidenceUI.render(realTask,realCandidate?.advice,mode,caseId);
  if(typeof ImpactUI!=='undefined')ImpactUI.render(realTask,realCandidate,mode,flow.running);
  if(typeof UploadUI!=='undefined')UploadUI.render();
}
function currentReview(){return !roundLoading&&realCandidate?.is_current_review===true&&realCandidate.id===realTask?.candidate_id;}
function renderRounds(){
  const panel=$('cegis-panel');panel.hidden=mode!=='real'||current.kind==='probe';
  if(panel.hidden)return;
  const candidates=realTask?.candidates||[],events=realTask?.events||[],calls=realTask?.model_calls||[];
  const latest=candidates.at(-1),shown=selectedRound||realTask?.candidate_id;
  const generating=realTask?.status==='GENERATING';
  $('cegis-status').textContent=!realTask?'最多 3 轮':generating?'第 '+((realTask.attempt_count||0)+1)+' 轮生成中':flow.running?'MCP 验证中':states[realTask.status]||realTask.status;
  $('cegis-summary').textContent=!realTask?'MCP 分析 → DeepSeek 修复 → 应用候选 → 工程验证 → 失败反馈':
    '已应用 '+candidates.length+' 个候选 · '+(selectedRound?'查看历史轮次':'跟随最新候选')+(roundLoading?' · 加载中':'');
  $('cegis-latest').disabled=reviewBusy||!selectedRound;
  $('cegis-rounds').replaceChildren(...candidates.map(c=>{
    const b=document.createElement('button'),advice=events.find(e=>e.type==='MODEL_SUGGESTION'&&e.model_call_id===c.model_call_id);
    const call=calls.find(r=>r.id===c.model_call_id),pass=c.build_state==='PASS'&&c.test_state==='PASS',fail=c.build_state==='FAIL'||c.test_state==='FAIL';
    b.className='cegis-round '+(c.id===shown?'selected ':'')+(pass?'passed':fail?'failed':'');
    b.setAttribute('aria-pressed',String(c.id===shown));b.disabled=reviewBusy;
    b.append(Object.assign(document.createElement('strong'),{textContent:'第 '+c.attempt+' 轮'}),
      Object.assign(document.createElement('span'),{textContent:pass?'验证通过':fail?'验证失败':'待验证'}),
      Object.assign(document.createElement('small'),{textContent:advice?.summary||'候选 '+c.tree_hash?.slice(0,8)}),
      Object.assign(document.createElement('small'),{textContent:'构建 '+(c.build_state||'NOT_RUN')+' · 测试 '+(c.test_state||'NOT_RUN')+(call?.usage?.total_tokens?' · '+call.usage.total_tokens+' tokens':'')}));
    b.onclick=()=>selectRound(c.id);return b;
  }));
  const feedback=events.find(e=>e.repair_feedback?.previous_candidate_id===realCandidate?.id)?.repair_feedback;
  if(typeof FeedbackUI!=='undefined')FeedbackUI.render($('cegis-counterexamples'),feedback,realCandidate);
  const snippets=(feedback?.diagnostic_snippets||[]).filter(s=>s.visibility==='PUBLIC').map(s=>s.text).filter(Boolean);
  const checks=(realChecks||[]).filter(c=>c.state==='FAIL').map(c=>c.diagnostics).filter(Boolean);
  const stop=events.filter(e=>e.stop_reason).at(-1)?.stop_reason;
  $('cegis-feedback').textContent=snippets.length?'MCP 失败反馈'+(latest?.id!==realCandidate?.id?'（已用于后续修复）':'')+'\n'+snippets.join('\n'):
    checks.length?'MCP 验证诊断\n'+checks.join('\n'):stop?'停止原因：'+stop:
    currentReview()?'当前候选已通过工程验证，等待人工审阅。':selectedRound?'历史候选仅供查看。':'失败后将自动反馈给 DeepSeek；通过后停止并等待审阅。';
}
async function fetchRound(id,version,selection){
  const [candidate,sources]=await Promise.all([api('/api/candidates/'+id),api('/api/demo/candidates/'+id)]);
  if(version!==epoch||selection!==roundEpoch)return false;
  realCandidate={...candidate,...sources};realChecks=realCandidate.checks||[];roundLoading=false;return true;
}
async function selectRound(id){
  if(reviewBusy||!realTask)return;
  if(id!==null&&!(realTask.candidates||[]).some(c=>c.id===id))return;
  selectedRound=id;const target=id||realTask.candidate_id,selection=++roundEpoch,version=epoch;
  roundLoading=true;realCandidate=null;realChecks=[];render();
  try{if(target&&await fetchRound(target,version,selection))render();}
  catch(error){if(version===epoch&&selection===roundEpoch){roundLoading=false;render();toast('候选加载失败');}}
}
function realDuration(){return executionDuration(realTask?.events||[]);}
function highlightCode(node,text){
  const pattern=/\b(public|func|package|return|if|else|let|var|true|false|Bool|Int64)\b|\b\d+\b/g;
  let start=0;
  for(const match of text.matchAll(pattern)){
    node.append(document.createTextNode(text.slice(start,match.index)));
    const token=document.createElement('span');token.className=/^\d/.test(match[0])?'num':/^(Bool|Int64)$/.test(match[0])?'type':'kw';token.textContent=match[0];node.append(token);start=match.index+match[0].length;
  }
  node.append(document.createTextNode(text.slice(start)));
}
function codeSide(content,other,kind,highlight){const side=document.createElement('div');side.className='code-side';const lines=content.split('\n'),others=other.split('\n');lines.forEach((text,i)=>{const row=document.createElement('div');row.className='code-line '+(highlight&&text!==others[i]?kind:'');const number=document.createElement('span');number.className='line-number';number.textContent=String(i+1);const code=document.createElement('span');highlightCode(code,text||' ');row.append(number,code);side.append(row);});return side;}
function renderCode(){if(!current)return;const f=current.files[fileIndex]||current.files[0];const live=mode==='real'&&realCandidate?.edits?.find(e=>e.path===f.path);const actualBefore=realCandidate?.source_files?.find(e=>e.path===f.path)?.before;const changed=mode==='real'?!!realCandidate:flow.stage>=2;const before=(mode==='real'?actualBefore:undefined)??(f.before||'// 受保护测试');const after=mode==='real'?(live?.content||(realCandidate?before:'')):(changed?f.after||'// 禁止修改':before);
  $('active-file').textContent=f.path.split('/').pop();$('code-diff').replaceChildren(codeSide(before,after,'removal',changed),codeSide(after,before,'addition',changed));
  let plus=0,minus=0;const a=before.split('\n'),b=after.split('\n');for(let i=0;i<Math.max(a.length,b.length);i++)if(a[i]!==b[i]){if(a[i]!==undefined)minus++;if(b[i]!==undefined)plus++;}
  if(mode==='real'&&!realCandidate){plus=0;minus=0;}$('added').textContent='+'+plus;$('removed').textContent='−'+minus;document.querySelectorAll('.file-button').forEach((b,i)=>b.classList.toggle('active',i===fileIndex));}
function saveRecord(){
  if(!current)return;const record={id:realTask?.id||crypto.randomUUID(),caseId,title:current.title,source:mode==='real'?realSource():current.source_label,origin:mode==='real'?(current.kind==='probe'?'REAL_NATIVE':'REAL_AI'):current.origin,status:flow.status,time:Date.now(),url:downloadUrl};
  history=[record,...history.filter(h=>h.id!==record.id)].slice(0,20);try{localStorage.setItem('cangsight-demo-history',JSON.stringify(history));}catch{}renderHistory();
}
function renderHistory(){ $('history-count').textContent=String(history.length);for(const type of ['history','delivery']){const list=$(type+'-list');const records=type==='delivery'?history.filter(r=>r.status==='DELIVERED'&&r.url):history;list.replaceChildren();if(!records.length){const empty=document.createElement('div');empty.className='record-empty';empty.textContent='暂无记录';list.append(empty);continue;}for(const h of records){const row=document.createElement('div');row.className='record-row';row.append(icon(type==='delivery'?'box':'clock'),Object.assign(document.createElement('strong'),{textContent:h.title}),Object.assign(document.createElement('span'),{className:'tiny-badge',textContent:h.source}),Object.assign(document.createElement('span'),{className:'status '+(h.status==='DELIVERED'?'good':'neutral'),textContent:states[h.status]||h.status}),Object.assign(document.createElement('time'),{textContent:new Date(h.time).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'})}));
      if(type==='delivery'){const a=document.createElement('a');a.className='button secondary';a.textContent='下载';if(h.origin?.startsWith('REAL_')||h.source==='实测'){a.href=h.url;}else a.href='/demo/download/'+h.caseId;row.append(a);}else{const b=document.createElement('button');b.className='button secondary';b.textContent='查看';b.onclick=()=>loadRecord(h);row.append(b);}list.append(row);}}
}
function schedule(){clearTimeout(timer);if(!flow.running)return;const version=epoch;timer=setTimeout(()=>{if(version!==epoch)return;flow.tick(current.verdict==='DENY');render();if(flow.status==='DENIED'){saveRecord();toast('越权已拦截');}schedule();},1100/Number($('speed').value));}
async function startReal(){
  if(starting||reviewBusy||flow.running)return;
  invalidate();const version=epoch;starting=true;flow.start();render();try{
    const env=await api('/demo/environment');
    if(!(current.kind==='probe'?env.policy_ready:env.ready))throw new Error((env.missing||[]).some(m=>m.code==='MODEL_NOT_CONFIGURED')?'DeepSeek 未配置':'SDK 未就绪');
    let task;
    if(current.kind==='probe'){
      const result=await api('/api/demo/probes/'+caseId,{});task={id:result.task_id};
    }else{
      const project=current.project_id;
      const draft=await api('/api/requirements/drafts',{project,goal:current.requirement});
      const spec=await api('/api/requirements/drafts/'+draft.id+'/confirm',{schema_version:1,expected_version:draft.version,requirements:draft.requirements,allowed_paths:draft.allowed_paths});
      task=await api('/agents/runs',{schema_version:1,team_profile:'cangjie-repair',payload:{project,spec_id:spec.id,idempotency_key:crypto.randomUUID()}});
    }
    if(version!==epoch)return;realTask=task;starting=false;saveRecord();pollReal(version);
  }catch(error){if(version!==epoch)return;starting=false;flow.status='BLOCKED';flow.running=false;render();toast(error.message);}
}
async function pollReal(version){if(version!==epoch||!realTask)return;try{
  const t=await api('/api/tasks/'+realTask.id);if(version!==epoch)return;realTask=t;revision=t.revision;
  const stage={READY:0,DIAGNOSING:1,GENERATING:2,APPLYING:3,BUILDING:4,TESTING:4,REVIEW_PENDING:5,EXPORTING:6,DELIVERED:6};flow.stage=stage[t.status]??Math.max(flow.stage,0);
  const terminal=['REVIEW_PENDING','DELIVERED','BLOCKED','IN_DOUBT','UNREPAIRED','REJECTED','CANCELLED'];flow.running=!terminal.includes(t.status);flow.status=flow.running?'RUNNING':t.status;
  const probe=(t.events||[]).find(e=>e.type==='NATIVE_PROBE');if(probe){flow.stage=3;flow.running=false;flow.status=t.status==='REJECTED'&&probe.policy?.decision?.reason==='PROTECTED_PATH'&&probe.mcp_status==='ERROR'&&probe.baseline_unchanged&&probe.candidate_writes===0?'DENIED':'IN_DOUBT';}
  const target=selectedRound||t.candidate_id,selection=roundEpoch;
  if(target)await fetchRound(target,version,selection);if(version!==epoch)return;
  if(t.download_url)downloadUrl=t.download_url;render();saveRecord();if(flow.running)timer=setTimeout(()=>pollReal(version),550);
}catch(error){if(version!==epoch)return;flow.running=false;flow.status='IN_DOUBT';render();saveRecord();toast('连接待核实');}}
async function loadRecord(record){
  if(starting||reviewBusy||(realTask&&flow.running)){toast('请先结束');return;}
  const selected=await selectCase(record.caseId);if(!selected||selected.epoch!==epoch||selected.id!==caseId)return;
  if(record.origin?.startsWith('REAL_')||record.source==='实测'){setMode('real');realTask={id:record.id};await pollReal(epoch);}
  else{setMode('replay');flow.status=record.status;flow.stage=record.status==='DELIVERED'?6:record.status==='DENIED'?3:5;downloadUrl=record.url;render();}
}
async function accept(){if(flow.status!=='REVIEW_PENDING'||(mode==='real'&&!currentReview()))return;if(mode==='replay'){flow.accept();downloadUrl='/demo/download/'+caseId;render();saveRecord();return;}
  if(reviewBusy)return;reviewBusy=true;
  $('accept').disabled=true;$('reject').disabled=true;
  const version=epoch,subject=realCandidate.id,checkHash=realCandidate.check_set_hash,currentRevision=revision;
  try{
    const a=await api('/api/candidates/'+subject+'/accept',{check_set_hash:checkHash,task_revision:currentRevision});
    if(version!==epoch)return;
    const out=await api('/api/candidates/'+subject+'/export',{acceptance_id:a.id});
    if(version!==epoch)return;
    downloadUrl=out.download_url;flow.accept();render();saveRecord();
  }catch(error){if(version===epoch){flow.status='IN_DOUBT';render();toast(error.message);}}
  finally{reviewBusy=false;}
}
async function rejectCandidate(){
  if(flow.status!=='REVIEW_PENDING'||reviewBusy||(mode==='real'&&!currentReview()))return;
  reviewBusy=true;const version=epoch;
  $('accept').disabled=true;$('reject').disabled=true;
  try{
    if(mode==='real'){
      const subject=realCandidate.id,currentRevision=revision;
      await api('/api/candidates/'+subject+'/reject',{task_revision:currentRevision,reason:''});
      if(version!==epoch)return;
    }
    flow.reject();render();saveRecord();
  }catch(error){if(version===epoch){if(mode==='real'){flow.status='IN_DOUBT';saveRecord();}toast(error.message);}}
  finally{reviewBusy=false;if(version===epoch)render();}
}
async function reset(){
  if(starting){toast('正在启动');return;}if(reviewBusy){toast('正在交付');return;}
  if(mode==='real'&&realTask&&flow.running){
    invalidate();
    try{const t=await api('/api/tasks/'+realTask.id);await api('/api/tasks/'+t.id+'/cancel',{task_revision:t.revision});}
    catch(error){toast(error.message);pollReal(epoch);return;}
    flow.running=false;flow.status='CANCELLED';saveRecord();
  }
  invalidate();await selectCase(caseId);
}

function showAdvice(){
  const advice=realCandidate?.advice;const box=$('advice-content');box.replaceChildren();
  if(mode!=='real'||!advice){box.textContent=mode==='replay'?'历史回放':current.kind==='probe'?'策略探测无需模型':'待生成';}
  else{box.append(Object.assign(document.createElement('p'),{textContent:advice.summary}));for(const item of advice.suggestions||[]){const section=document.createElement('section');section.append(Object.assign(document.createElement('strong'),{textContent:item.path}),Object.assign(document.createElement('p'),{textContent:item.reason}));box.append(section);}}
  $('advice-dialog').showModal();
}

document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>showView(b.dataset.view));document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>tab(b.dataset.tab));
$('mode-replay').onclick=()=>setMode('replay');$('mode-real').onclick=()=>setMode('real');$('start').onclick=()=>{if(mode==='real'){startReal();return;}if(flow.running){flow.pause();invalidate();}else{flow.start();schedule();}render();};
$('cegis-latest').onclick=()=>selectRound(null);$('advice-open').onclick=showAdvice;$('reset').onclick=reset;$('accept').onclick=accept;$('reject').onclick=rejectCandidate;
$('speed').onchange=()=>{if(flow.running)schedule();};$('requirement-open').onclick=()=>$('requirement-dialog').showModal();$('report-open').onclick=()=>tab('report');
$('project-toggle').onclick=()=>{const expanded=$('files').hidden;$('files').hidden=!expanded;$('project-toggle').setAttribute('aria-expanded',String(expanded));};
document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>$(b.dataset.close).close());
$('clear-history').onclick=()=>{history=[];try{localStorage.removeItem('cangsight-demo-history');}catch{}renderHistory();};
(async()=>{try{catalog=(await api('/demo/cases')).cases;const list=$('case-list');list.replaceChildren();for(const [group,label] of [['order','订单'],['cross','跨文件'],['policy','策略']]){const heading=document.createElement('div');heading.className='case-group';heading.textContent=label;list.append(heading);for(const c of catalog.filter(c=>c.group===group)){const b=document.createElement('button');b.className='case-button';b.dataset.case=c.id;b.append(icon(group==='policy'?'shield':group==='cross'?'file':'code'),document.createTextNode(c.title.replace('协同','').replace('操作','')));b.onclick=()=>selectCase(c.id);list.append(b);}}await selectCase('order',false);}catch(error){toast(error.message);}})();
