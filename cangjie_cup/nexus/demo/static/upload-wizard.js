'use strict';
/* 上传修复四步向导：仅负责步骤切换、分步校验与核对摘要，
   所有字段读写与 API 调用仍由 upload.js 完成，元素 ID 与其约定保持一致。 */
(() => {
  const dialog = document.getElementById('upload-dialog');
  if (!dialog) return;
  const steps = [...dialog.querySelectorAll('.upload-step')];
  const dots = [...dialog.querySelectorAll('[data-step-dot]')];
  const prevBtn = document.getElementById('upload-step-prev');
  const nextBtn = document.getElementById('upload-step-next');
  const hint = document.getElementById('upload-step-hint');
  if (!steps.length || !prevBtn || !nextBtn) return;

  const TOTAL = steps.length;
  let current = 1;
  let visited = new Set([1]);
  let observedFnDisabled = null;

  const modeLabels = { single: '单个 .cj 文件', project: '仓颉工程 ZIP', directory: '仓颉工程目录' };
  const field = id => document.getElementById(id);

  function gateError(next) {
    if (next === 3 && !field('upload-function')?.value) return '请先在第 1 步「读取函数」，并在此选择待测函数';
    if (next === 4) {
      const examples = field('upload-examples')?.value.trim();
      if (!examples) return '请先填写或导入「输入与预期输出」测试 JSON';
      try { JSON.parse(examples); } catch { return '测试 JSON 格式有误，请先修正'; }
    }
    return '';
  }

  function render() {
    steps.forEach(s => { s.hidden = Number(s.dataset.step) !== current; });
    dots.forEach(d => {
      const n = Number(d.dataset.stepDot);
      d.classList.toggle('active', n === current);
      d.classList.toggle('done', visited.has(n) && n < current);
      d.setAttribute('aria-current', n === current ? 'step' : 'false');
    });
    prevBtn.disabled = current === 1;
    nextBtn.hidden = current === TOTAL; // 最后一步由「确认测试并进入工作台」收尾
    if (hint && current !== 2 && current !== 3) hint.textContent = '';
    if (current === TOTAL) fillSummary();
  }

  function goTo(n) {
    if (n < 1 || n > TOTAL || n === current) return;
    if (n > current) {
      for (let k = current; k < n; k++) {
        const err = gateError(k + 1);
        if (err) { current = k; visited.add(k); render(); if (hint) hint.textContent = err; return; }
        visited.add(k + 1);
      }
    }
    current = n; visited.add(n); render();
  }

  function fillSummary() {
    const set = (id, text) => { const el = field(id); if (el) el.textContent = text; };
    const fn = field('upload-function');
    set('upload-summary-function', fn?.value || '—');
    const mode = field('upload-mode')?.value || 'single';
    let modeText = modeLabels[mode] || mode;
    const picked = dialog.querySelectorAll('#upload-project-tree input[type="checkbox"]:checked').length;
    if (mode !== 'single' && picked) modeText += ` · 已选 ${picked} 个生产文件`;
    set('upload-summary-mode', modeText);
    const goal = (field('upload-goal')?.value || '').trim();
    set('upload-summary-goal', goal ? (goal.length > 60 ? goal.slice(0, 60) + '…' : goal) : '—');
    const examples = (field('upload-examples')?.value || '').trim();
    let exText = '未填写';
    if (examples) {
      try { const arr = JSON.parse(examples); exText = `${Array.isArray(arr) ? arr.length : 1} 组用例`; }
      catch { exText = '已填写'; }
    }
    set('upload-summary-examples', exText);
    const advanced = [['upload-oracle', '独立规则'], ['upload-properties', '业务属性'], ['upload-relations', '成对关系'], ['upload-sequences', '状态模型']]
      .filter(([id]) => (field(id)?.value || '').trim()).map(([, name]) => name);
    set('upload-summary-advanced', advanced.length ? advanced.join('、') : '未启用');
  }

  prevBtn.addEventListener('click', () => goTo(current - 1));
  nextBtn.addEventListener('click', () => goTo(current + 1));
  dots.forEach(d => d.addEventListener('click', () => {
    const n = Number(d.dataset.stepDot);
    if (visited.has(n) || n < current) goTo(n);
    else goTo(n); // goTo 内部会做分步校验拦截
  }));
  dialog.addEventListener('keydown', event => {
    if (event.key !== 'Enter' || event.target?.tagName === 'TEXTAREA' || event.target?.tagName === 'BUTTON') return;
    if (current < TOTAL) { event.preventDefault(); goTo(current + 1); }
  });

  // 读取函数完成后自动进入第 2 步
  function watchPrepare() {
    const fn = field('upload-function');
    if (!fn || observedFnDisabled === null) return;
    if (observedFnDisabled && !fn.disabled && dialog.open) { observedFnDisabled = false; goTo(Math.max(current, 2)); return; }
    observedFnDisabled = fn.disabled;
  }
  observedFnDisabled = field('upload-function') ? field('upload-function').disabled : null;
  setInterval(watchPrepare, 300);
  const prepareBtn = field('upload-prepare');
  if (prepareBtn) prepareBtn.addEventListener('click', () => { observedFnDisabled = true; });

  // 每次打开对话框时回到第 1 步（保留已填内容）
  dialog.addEventListener('close', () => { current = 1; visited = new Set([1]); render(); });
  document.getElementById('upload-open')?.addEventListener('click', () => { current = 1; visited = new Set([1]); render(); });

  render();
})();
