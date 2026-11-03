const $ = id => document.getElementById(id);
const csrf = document.querySelector('meta[name="csrf-token"]').content;
const labels = {READY:'准备就绪',DIAGNOSING:'诊断基线',GENERATING:'生成候选',APPLYING:'物化候选',BUILDING:'构建工程',TESTING:'运行测试',REVIEW_PENDING:'等待审阅',EXPORTING:'导出工程',DELIVERED:'交付完成',BLOCKED:'运行受阻',IN_DOUBT:'执行结果待核实',UNREPAIRED:'预算内未修复',CANCELLED:'已取消',REJECTED:'已拒绝'};
const active = new Set(['READY','DIAGNOSING','GENERATING','APPLYING','BUILDING','TESTING','EXPORTING']);
let taskId = localStorage.getItem('cangsight-task'), candidate, timer, startKey, refreshGeneration = 0;
let requirementDraft, confirmedSpec, environmentReady = false, running = false;
let taskRevision;
let viewedCandidateId, historyGeneration=0;
async function api(path, body) {
  const response = await fetch(path,body ? {method:'POST',headers:{'Content-Type':'application/json','Origin':location.origin,'X-CSRF-Token':csrf},body:JSON.stringify(body)} : {});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || '操作未完成，请查看记录。');
  return data;
}
function isCurrent(generation, requestedTask) {
  return generation === refreshGeneration && requestedTask === taskId;
}
async function refresh() {
  clearTimeout(timer);
  const generation = ++refreshGeneration, requestedTask = taskId;
  try {
    const task = await api('/api/tasks/'+requestedTask);
    if (!isCurrent(generation, requestedTask)) return;
    $('phase').textContent = labels[task.status] || task.status;
    $('attempt').textContent = `候选 ${task.attempt_count} / 3`;
    running = active.has(task.status);
    $('scope-card').disabled=running || !!confirmedSpec;
    taskRevision = task.revision;
    $('cancel').disabled = !running && task.status !== 'REVIEW_PENDING';
    $('reject').disabled = true;
    $('start').disabled = running || !requirementDraft || !environmentReady;
    $('prepare').disabled = running;
    $('goal').disabled = running;
    $('project').disabled = running;
    $('download').hidden=!task.download_url;
    if (task.download_url) {
      $('download').href=task.download_url;
      $('download').hidden=false;
    }
    $('accept').disabled = true;
    const options=task.candidates || (task.candidate_id ? [{id:task.candidate_id,attempt:task.attempt_count}] : []);
    if (!options.some(item=>item.id===viewedCandidateId)) viewedCandidateId=undefined;
    const displayedCandidate=viewedCandidateId || task.candidate_id;
    $('candidate-history').textContent='';
    for (const item of options) {
      const option=document.createElement('option');
      option.value=item.id;option.textContent=`候选 ${item.attempt} · ${item.id.slice(-8)}`;
      $('candidate-history').appendChild(option);
    }
    $('candidate-history').value=displayedCandidate || '';
    $('candidate-history').disabled=options.length<2;
    $('logs').textContent = [...task.events,...(task.baseline_checks || [])].map(event=>event.stop_reason || JSON.stringify(event)).join('\n') || '正在记录工具执行。';
    $('message').textContent = [task.review_notice,...task.events.filter(e=>e.stop_reason).map(e=>e.stop_reason === 'DeepSeek configuration unavailable' ? '尚未配置 DeepSeek。请在本机配置后开始新任务。' : e.stop_reason)].filter(Boolean).join('\n');
    if (!task.candidate_id && task.baseline_checks?.length) {
      $('checks').textContent = task.baseline_checks.map(c=>`基线 ${checkSummary(c)}`).join('\n\n');
      $('checks').className = '';
    }
    if (displayedCandidate) {
      const details = await api('/api/candidates/'+displayedCandidate);
      if (!isCurrent(generation, requestedTask)) return;
      candidate = details;
      $('diff').textContent = candidate.diff;
      $('diff').className = '';
      $('checks').textContent = candidate.checks.map(checkSummary).join('\n\n');
      $('logs').textContent += '\n'+candidate.checks.map(c=>c.diagnostics).join('\n');
      const requirementLabels={SATISFIED_BY_TESTS:'冻结测试支持',FAILED:'检查不通过',UNKNOWN:'无法判定',UNMAPPED:'未映射验收'};
      $('requirement-results').textContent=(candidate.requirement_results || []).map(r=>`${r.text}：${requirementLabels[r.status] || r.status}`).join('\n');
      $('limitations').textContent=(candidate.limitations || []).join('\n');
      $('checks').className = '';
      const reviewable=task.status==='REVIEW_PENDING' && displayedCandidate===task.candidate_id && candidate.is_current_review!==false;
      $('accept').disabled = !(reviewable && candidate.check_set_hash);
      $('reject').disabled = !reviewable;
    }
    if (active.has(task.status)) timer = setTimeout(refresh,1200);
  } catch (error) {
    if (isCurrent(generation, requestedTask)) $('message').textContent = error.message;
  }
}
async function refreshEnvironment() {
  try {
    const environment = await api('/api/environment');
    environmentReady = environment.ready;
    $('environment').textContent = environment.ready ? '本机配置已就绪；模型连接未主动探测。' :
      environment.missing.map(item=>item.message).join('\n');
    $('start').disabled = running || !requirementDraft || !environmentReady;
  } catch(error) { $('environment').textContent = '无法检查环境，请刷新后重试。'; }
}
function invalidateDraft() {
  requirementDraft = undefined;
  confirmedSpec = undefined;
  startKey = undefined;
  $('requirement-card').hidden = true;
  $('scope-card').disabled = true;
  $('start').disabled = true;
}
$('goal').addEventListener('input',invalidateDraft);
$('project').addEventListener('change',invalidateDraft);
$('repair-form').addEventListener('submit',async event=>{
  event.preventDefault();
  const project = $('project').value, goal = $('goal').value;
  $('prepare').disabled = true;
  invalidateDraft();
  try {
    const draft = await api('/api/requirements/drafts',{project,goal});
    if (project !== $('project').value || goal !== $('goal').value) return;
    requirementDraft = draft;
    $('requirements').textContent = '';
    for (const item of draft.requirements) {
      const card = document.createElement('pre');
      card.textContent = `${item.id} · ${item.text}\n\n验收行为：${item.observable_behavior}\n\n保持：${item.preserves.join('；')}\n\n不覆盖：${item.uncovered.join('；')}`;
      $('requirements').appendChild(card);
    }
    $('allowed-paths').textContent='';
    const sourcePaths=[...draft.allowed_paths];
    for (const path of sourcePaths) {
      const label=document.createElement('label'), input=document.createElement('input'), text=document.createElement('span');
      input.type='checkbox';input.checked=true;text.textContent=path;
      input.addEventListener('change',()=>{
        if (running || confirmedSpec || requirementDraft!==draft) return;
        const selected=new Set(draft.allowed_paths);
        if (input.checked) selected.add(path); else selected.delete(path);
        draft.allowed_paths=sourcePaths.filter(item=>selected.has(item));
        $('start').disabled=!environmentReady || !draft.allowed_paths.length;
      });
      label.appendChild(input);label.appendChild(text);$('allowed-paths').appendChild(label);
    }
    $('scope-card').disabled=running;
    $('requirement-card').hidden = false;
    $('start').disabled = running || !environmentReady;
    $('message').textContent = '请检查验收约定。确认后才会启动真实修复。';
  } catch(error) { $('message').textContent=error.message; }
  finally { $('prepare').disabled = running; }
});
$('start').addEventListener('click',async()=>{
  if (!requirementDraft || !requirementDraft.allowed_paths.length || !environmentReady) return;
  const draft = requirementDraft, requestedTask = taskId, generation = ++refreshGeneration;
  running = true;
  $('scope-card').disabled=true;
  candidate = undefined;
  $('accept').disabled = true;
  $('start').disabled = true;
  $('prepare').disabled = true;
  $('goal').disabled = true;
  $('project').disabled = true;
  $('message').textContent = '';
  $('download').hidden = true;
  clearTimeout(timer);
  startKey ||= crypto.randomUUID();
  try {
    if (!confirmedSpec) {
      const spec = await api('/api/requirements/drafts/'+draft.id+'/confirm',{
        schema_version:1,expected_version:draft.version,requirements:draft.requirements,allowed_paths:draft.allowed_paths});
      if (!isCurrent(generation,requestedTask)) return;
      confirmedSpec = spec;
    }
    const task = await api('/agents/runs',{schema_version:1,team_profile:'cangjie-repair',
      payload:{project:draft.project_id,spec_id:confirmedSpec.id,idempotency_key:startKey}});
    if (!isCurrent(generation,requestedTask)) return;
    taskId = task.id;
    viewedCandidateId=undefined;
    localStorage.setItem('cangsight-task',taskId);
    startKey = undefined;
    candidate = undefined;
    $('diff').textContent = '等待候选修改。';
    $('checks').textContent = '正在读取基线诊断。';
    await refresh();
    refreshHistory();
  } catch(error) {
    if (isCurrent(generation,requestedTask)) {
      running = false;
      $('message').textContent = error.message;
      $('start').disabled = !environmentReady;
      $('prepare').disabled = false;
      $('goal').disabled = false;
      $('project').disabled = false;
    }
  }
});
$('accept').addEventListener('click',async()=>{
  const selected = candidate, requestedTask = taskId, generation = ++refreshGeneration;
  clearTimeout(timer);
  $('accept').disabled=true;
  try {
    const accepted = await api('/api/candidates/'+selected.id+'/accept',{check_set_hash:selected.check_set_hash,
      ...(selected.task_schema_version===2 ? {task_revision:selected.task_revision} : {})});
    if (!isCurrent(generation, requestedTask)) return;
    const result = await api('/api/candidates/'+selected.id+'/export',{acceptance_id:accepted.id});
    if (!isCurrent(generation, requestedTask)) return;
    if (result.download_url) {
      $('download').href=result.download_url;
      $('download').hidden=false;
    }
    await refresh();
  } catch(error) {
    if (isCurrent(generation, requestedTask)) $('message').textContent=error.message;
  }
});
async function stopByUser(reject) {
  const selected=candidate, requestedTask=taskId, revision=taskRevision, generation=++refreshGeneration;
  clearTimeout(timer);
  $('accept').disabled=true;
  $('reject').disabled=true;
  $('cancel').disabled=true;
  try {
    await api(reject ? '/api/candidates/'+selected.id+'/reject' : '/api/tasks/'+requestedTask+'/cancel',
      {task_revision:revision,...(reject ? {reason:$('reject-reason').value} : {})});
    if (!isCurrent(generation,requestedTask)) return;
    $('download').hidden=true;
    await refresh();
  } catch(error) {
    if (isCurrent(generation,requestedTask)) {
      const recovery=refresh(), recoveryGeneration=refreshGeneration;
      await recovery;
      if (isCurrent(recoveryGeneration,requestedTask)) $('message').textContent=error.message;
    }
  }
}
$('reject').addEventListener('click',()=>stopByUser(true));
$('cancel').addEventListener('click',()=>stopByUser(false));
async function refreshHistory() {
  const generation=++historyGeneration;
  try {
    const history=await api('/api/tasks');
    if (generation!==historyGeneration) return;
    $('task-history').textContent='';
    for (const task of history.tasks) {
      const option=document.createElement('option');
      option.value=task.id;option.textContent=`${labels[task.status] || task.status} · ${task.goal.slice(0,35)} · ${task.id.slice(-8)}`;
      $('task-history').appendChild(option);
    }
    $('task-history').value=taskId || '';
  } catch(error) { $('history-status').textContent='历史任务暂不可读取，请刷新重试。'; }
}
$('task-history').addEventListener('change',()=>{
  ++refreshGeneration;
  clearTimeout(timer);
  taskId=$('task-history').value;
  localStorage.setItem('cangsight-task',taskId);
  candidate=undefined;viewedCandidateId=undefined;
  $('download').hidden=true;
  $('accept').disabled=true;$('reject').disabled=true;
  $('diff').textContent='正在读取历史候选。';
  refresh();
});
$('candidate-history').addEventListener('change',()=>{
  viewedCandidateId=$('candidate-history').value;
  candidate=undefined;
  $('accept').disabled=true;$('reject').disabled=true;
  refresh();
});
refreshHistory();
refreshEnvironment();
if (taskId) refresh();

function checkSummary(c) {
  const counts = c.counts || {};
  const suites=Object.entries(c.suite_results || {}).map(([name,result])=>`\n${name==='order-target'?'目标行为':'回归'}  ${result.state}`).join('');
  return `${c.kind === 'build' ? '构建' : '测试'}  ${c.state}` + (counts.total !== undefined ? `
共 ${counts.total} 项 · 通过 ${counts.passed} · 失败 ${counts.failed} · 跳过 ${counts.skipped}` : '') + suites;
}
$('policy-probe').addEventListener('click',async()=>{
  $('policy-probe').disabled=true;
  try {
    const result=await api('/api/policy-probe',{});
    $('policy-result').textContent = result.decision==='Deny' && result.unchanged && !result.action_executed ?
      '仓颉策略已拒绝修改测试；写动作未执行，冻结文件保持不变。' : '保护检查未通过，请查看运行记录。';
  } catch(error) { $('policy-result').textContent=error.message; }
  finally { $('policy-probe').disabled=false; }
});
