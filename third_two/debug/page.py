"""third_two 对话调试台的单文件页面。"""

from __future__ import annotations


def debug_page_html() -> str:
    return r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>third_two 对话调试台</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #07100f;
      --panel: rgba(14, 28, 26, .88);
      --panel-2: rgba(20, 39, 35, .82);
      --line: rgba(180, 220, 205, .13);
      --text: #ecf7f2;
      --muted: #91a9a0;
      --accent: #65e6b2;
      --accent-2: #65bfe6;
      --warn: #f4c66f;
      --danger: #ff8c8c;
      --shadow: 0 24px 70px rgba(0, 0, 0, .28);
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; }
    body {
      margin: 0;
      overflow: hidden;
      color: var(--text);
      font: 14px/1.55 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at 14% 5%, rgba(58, 178, 134, .18), transparent 28%),
        radial-gradient(circle at 85% 10%, rgba(54, 136, 172, .14), transparent 24%),
        var(--bg);
    }
    button, textarea, input { font: inherit; }
    button { cursor: pointer; }
    .app { display: grid; grid-template-columns: 280px minmax(440px, 1fr) 390px; height: 100vh; }
    .sidebar, .inspector { background: rgba(7, 18, 16, .72); backdrop-filter: blur(18px); }
    .sidebar { border-right: 1px solid var(--line); display: flex; flex-direction: column; min-width: 0; }
    .inspector { border-left: 1px solid var(--line); display: flex; flex-direction: column; min-width: 0; }
    .brand { padding: 22px 20px 18px; border-bottom: 1px solid var(--line); }
    .brand-line { display: flex; align-items: center; gap: 11px; }
    .mark { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 11px; color: #06261c; font-weight: 900; background: linear-gradient(140deg, #8df3c9, #4fc5a0); box-shadow: 0 9px 25px rgba(101, 230, 178, .22); }
    .brand h1 { margin: 0; font-size: 15px; letter-spacing: .02em; }
    .brand p { margin: 3px 0 0; color: var(--muted); font-size: 12px; }
    .new-button { width: 100%; margin-top: 16px; padding: 10px 12px; border: 1px solid rgba(101,230,178,.34); border-radius: 10px; color: var(--text); background: rgba(101,230,178,.1); }
    .new-button:hover { background: rgba(101,230,178,.17); }
    .side-title { padding: 16px 20px 8px; color: var(--muted); font-size: 11px; letter-spacing: .13em; text-transform: uppercase; }
    .task-list { overflow: auto; padding: 0 10px 18px; }
    .task-item { width: 100%; margin: 3px 0; padding: 12px; border: 1px solid transparent; border-radius: 12px; color: inherit; text-align: left; background: transparent; }
    .task-item:hover { background: rgba(255,255,255,.035); }
    .task-item.active { border-color: rgba(101,230,178,.24); background: rgba(101,230,178,.09); }
    .task-title { overflow: hidden; white-space: nowrap; text-overflow: ellipsis; font-size: 13px; }
    .task-meta { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 7px; color: var(--muted); font-size: 11px; }
    .status-dot { display: inline-block; width: 7px; height: 7px; margin-right: 5px; border-radius: 99px; background: var(--muted); }
    .status-dot.completed { background: var(--accent); }
    .status-dot.waiting_user { background: var(--warn); }
    .status-dot.failed, .status-dot.cancelled { background: var(--danger); }
    .main { min-width: 0; display: flex; flex-direction: column; }
    .topbar { min-height: 76px; padding: 14px 22px; border-bottom: 1px solid var(--line); display: flex; align-items: center; justify-content: space-between; gap: 18px; background: rgba(10,24,21,.58); backdrop-filter: blur(16px); }
    .topbar h2 { margin: 0; font-size: 16px; font-weight: 650; }
    .task-id { max-width: 380px; margin-top: 3px; overflow: hidden; color: var(--muted); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
    .badges { display: flex; gap: 7px; flex-wrap: wrap; justify-content: flex-end; }
    .badge { padding: 4px 8px; border: 1px solid var(--line); border-radius: 99px; color: var(--muted); background: rgba(255,255,255,.03); font-size: 11px; }
    .badge.accent { color: var(--accent); border-color: rgba(101,230,178,.25); }
    .conversation { flex: 1; min-height: 0; overflow: auto; padding: 24px max(22px, 6vw); scroll-behavior: smooth; }
    .empty { max-width: 680px; margin: 9vh auto 0; text-align: center; }
    .empty-orb { width: 64px; height: 64px; display: grid; place-items: center; margin: 0 auto 18px; border: 1px solid rgba(101,230,178,.25); border-radius: 20px; color: var(--accent); font-size: 26px; background: linear-gradient(145deg, rgba(101,230,178,.13), rgba(101,191,230,.07)); box-shadow: var(--shadow); }
    .empty h3 { margin: 0; font-size: 24px; letter-spacing: -.02em; }
    .empty p { max-width: 540px; margin: 10px auto 23px; color: var(--muted); }
    .scenarios { display: grid; grid-template-columns: repeat(2, 1fr); gap: 9px; text-align: left; }
    .scenario { padding: 12px 13px; border: 1px solid var(--line); border-radius: 12px; color: var(--text); background: rgba(255,255,255,.025); }
    .scenario:hover { border-color: rgba(101,230,178,.28); background: rgba(101,230,178,.07); }
    .scenario strong { display: block; margin-bottom: 2px; font-size: 12px; }
    .scenario span { color: var(--muted); font-size: 11px; }
    .message { display: flex; max-width: 820px; margin: 0 auto 18px; gap: 10px; }
    .message.user { justify-content: flex-end; }
    .avatar { flex: 0 0 30px; width: 30px; height: 30px; display: grid; place-items: center; border-radius: 9px; color: var(--muted); background: var(--panel-2); font-size: 11px; }
    .message.user .avatar { order: 2; color: #06261c; background: var(--accent); }
    .bubble { max-width: min(680px, 84%); padding: 11px 14px; border: 1px solid var(--line); border-radius: 6px 16px 16px 16px; white-space: pre-wrap; word-break: break-word; background: var(--panel); box-shadow: 0 10px 28px rgba(0,0,0,.12); }
    .message.user .bubble { border-color: rgba(101,230,178,.2); border-radius: 16px 6px 16px 16px; background: rgba(67,151,119,.17); }
    .message-label { margin-bottom: 4px; color: var(--muted); font-size: 10px; }
    .interaction-card { max-width: 820px; margin: 4px auto 20px; padding: 16px; border: 1px solid rgba(244,198,111,.25); border-radius: 15px; background: linear-gradient(135deg, rgba(244,198,111,.09), rgba(20,39,35,.78)); }
    .interaction-title { display: flex; justify-content: space-between; gap: 12px; color: var(--warn); font-size: 12px; }
    .interaction-question { margin: 9px 0 13px; font-size: 15px; }
    .option-row, .action-row { display: flex; gap: 8px; flex-wrap: wrap; }
    .option { padding: 7px 10px; border: 1px solid var(--line); border-radius: 9px; color: var(--text); background: rgba(255,255,255,.035); }
    .option:hover { border-color: rgba(101,230,178,.3); }
    .preview { margin: 12px 0; padding: 10px; max-height: 200px; overflow: auto; border: 1px solid var(--line); border-radius: 10px; background: rgba(0,0,0,.18); color: #b9cec6; font: 11px/1.5 ui-monospace, SFMono-Regular, Consolas, monospace; white-space: pre-wrap; }
    .inline-input { flex: 1; min-width: 180px; padding: 9px 11px; border: 1px solid var(--line); border-radius: 9px; outline: none; color: var(--text); background: rgba(0,0,0,.18); }
    .inline-input:focus, .composer textarea:focus { border-color: rgba(101,230,178,.45); }
    .btn { padding: 8px 12px; border: 1px solid var(--line); border-radius: 9px; color: var(--text); background: rgba(255,255,255,.04); }
    .btn.primary { color: #05251b; border-color: transparent; background: var(--accent); font-weight: 650; }
    .btn.danger { color: var(--danger); }
    .composer-wrap { padding: 14px max(22px, 6vw) 18px; border-top: 1px solid var(--line); background: rgba(8,20,18,.82); backdrop-filter: blur(18px); }
    .composer { max-width: 820px; margin: auto; padding: 7px 8px 7px 14px; border: 1px solid var(--line); border-radius: 16px; display: flex; align-items: flex-end; gap: 8px; background: var(--panel); box-shadow: var(--shadow); }
    .composer textarea { flex: 1; min-height: 46px; max-height: 140px; padding: 10px 0; resize: none; border: 0; outline: none; color: var(--text); background: transparent; }
    .send { flex: 0 0 40px; width: 40px; height: 40px; border: 0; border-radius: 12px; color: #06261c; background: var(--accent); font-size: 18px; font-weight: 800; }
    .send:disabled, .btn:disabled { opacity: .45; cursor: wait; }
    .composer-note { max-width: 820px; margin: 7px auto 0; color: var(--muted); font-size: 10px; text-align: center; }
    .inspector-head { padding: 17px 16px 10px; border-bottom: 1px solid var(--line); }
    .metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 7px; }
    .metric { padding: 9px; border: 1px solid var(--line); border-radius: 10px; background: rgba(255,255,255,.025); }
    .metric span { display: block; color: var(--muted); font-size: 10px; }
    .metric strong { display: block; margin-top: 2px; overflow: hidden; font-size: 15px; text-overflow: ellipsis; white-space: nowrap; }
    .tabs { display: flex; padding: 9px 12px 0; gap: 2px; overflow-x: auto; border-bottom: 1px solid var(--line); }
    .tab { padding: 8px 9px; border: 0; border-bottom: 2px solid transparent; color: var(--muted); background: transparent; font-size: 11px; white-space: nowrap; }
    .tab.active { border-bottom-color: var(--accent); color: var(--text); }
    .panel-content { flex: 1; min-height: 0; overflow: auto; padding: 14px; }
    .timeline { position: relative; padding-left: 12px; }
    .timeline:before { content: ""; position: absolute; left: 20px; top: 10px; bottom: 10px; width: 1px; background: var(--line); }
    .step { position: relative; display: grid; grid-template-columns: 18px 1fr; gap: 10px; margin-bottom: 12px; }
    .step-dot { z-index: 1; width: 17px; height: 17px; margin-top: 3px; display: grid; place-items: center; border: 2px solid #162e29; border-radius: 99px; color: #05251b; background: var(--accent); font-size: 8px; }
    .step-dot.waiting_confirmation { background: var(--warn); }
    .step-dot.retryable_error, .step-dot.terminal_error { background: var(--danger); }
    .step-body { padding: 9px 10px; border: 1px solid var(--line); border-radius: 10px; background: rgba(255,255,255,.025); }
    .step-head { display: flex; justify-content: space-between; gap: 8px; }
    .step-name { font: 12px ui-monospace, SFMono-Regular, Consolas, monospace; }
    .step-status { color: var(--muted); font-size: 10px; }
    .step-summary { margin-top: 6px; color: #c5d7d0; font-size: 11px; }
    .step-decision { margin-top: 5px; color: var(--muted); font-size: 10px; }
    .json { margin: 0; padding: 12px; overflow: auto; border: 1px solid var(--line); border-radius: 10px; color: #b9cec6; background: rgba(0,0,0,.18); font: 11px/1.55 ui-monospace, SFMono-Regular, Consolas, monospace; white-space: pre-wrap; word-break: break-word; }
    .artifact { margin-bottom: 9px; border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
    .artifact summary { padding: 10px; cursor: pointer; color: #cfe2da; background: rgba(255,255,255,.025); }
    .artifact .json { border: 0; border-top: 1px solid var(--line); border-radius: 0; }
    .config-row { display: flex; justify-content: space-between; gap: 10px; padding: 9px 2px; border-bottom: 1px solid var(--line); }
    .config-row span { color: var(--muted); }
    .check { margin-top: 9px; padding: 9px 10px; border: 1px solid var(--line); border-radius: 9px; }
    .check.ok strong { color: var(--accent); }
    .check.error strong { color: var(--danger); }
    .toast { position: fixed; right: 18px; bottom: 18px; z-index: 20; max-width: 420px; padding: 11px 14px; border: 1px solid var(--line); border-radius: 10px; color: var(--text); background: #19332e; box-shadow: var(--shadow); transform: translateY(30px); opacity: 0; transition: .2s; pointer-events: none; }
    .toast.show { transform: translateY(0); opacity: 1; }
    @media (max-width: 1180px) { .app { grid-template-columns: 230px 1fr 340px; } }
    @media (max-width: 920px) { .app { grid-template-columns: 210px 1fr; } .inspector { position: fixed; z-index: 10; right: 0; top: 0; bottom: 0; width: min(390px, 92vw); transform: translateX(100%); transition: .2s; box-shadow: var(--shadow); } .inspector.open { transform: translateX(0); } }
    @media (max-width: 640px) { body { overflow: auto; } .app { display: block; height: auto; min-height: 100vh; } .sidebar { display: none; } .main { min-height: 100vh; } .topbar { padding: 12px 14px; } .conversation { padding: 18px 12px; } .composer-wrap { padding: 10px 10px 14px; } .scenarios { grid-template-columns: 1fr; } .badges .badge:not(.accent) { display: none; } }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-line"><div class="mark">2</div><div><h1>third_two</h1><p>Rolling agent debugger</p></div></div>
        <button class="new-button" id="newTask">＋ 新建对话</button>
      </div>
      <div class="side-title">最近任务</div>
      <div class="task-list" id="taskList"></div>
    </aside>

    <main class="main">
      <header class="topbar">
        <div><h2 id="pageTitle">对话调试台</h2><div class="task-id" id="taskId">每一轮只规划并执行一个小步骤</div></div>
        <div class="badges" id="modeBadges"><span class="badge accent">正在读取配置</span></div>
      </header>
      <section class="conversation" id="conversation"></section>
      <footer class="composer-wrap">
        <div class="composer">
          <textarea id="messageInput" rows="1" placeholder="输入一个真实场景，例如：把字段“文本”改成“今日总结”"></textarea>
          <button class="send" id="sendButton" title="发送">↑</button>
        </div>
        <div class="composer-note">Enter 发送 · Shift + Enter 换行 · 配置直接沿用 third，不会在页面展示密钥</div>
      </footer>
    </main>

    <aside class="inspector" id="inspector">
      <div class="inspector-head"><div class="metrics" id="metrics"></div></div>
      <div class="tabs" id="tabs">
        <button class="tab active" data-tab="timeline">步骤时间线</button>
        <button class="tab" data-tab="state">TaskState</button>
        <button class="tab" data-tab="decision">决策 / 回流</button>
        <button class="tab" data-tab="artifacts">Artifacts</button>
        <button class="tab" data-tab="config">配置</button>
      </div>
      <div class="panel-content" id="panelContent"></div>
    </aside>
  </div>
  <div class="toast" id="toast"></div>

  <script>
    const state = { tasks: [], task: null, timeline: null, health: null, activeTab: 'timeline', busy: false };
    const $ = (id) => document.getElementById(id);
    const esc = (value) => String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
    const json = (value) => esc(JSON.stringify(value ?? null, null, 2));
    const statusName = {running:'执行中', waiting_user:'等待用户', completed:'已完成', failed:'失败', cancelled:'已取消'};
    const interactionName = {clarify:'补充信息', choose_candidate:'选择候选', confirm:'执行确认'};
    const scenarios = [
      ['新增记录', '新增一条记录，标题是场景验证，内容是查看执行步骤'],
      ['空结果回流', '完成了服务器的更新，写到飞书'],
      ['字段追问', '我可以更改这个表头吗？'],
      ['字段修改', '把字段“文本”重命名为“今日总结”']
    ];

    async function request(url, options = {}) {
      const response = await fetch(url, {headers: {'Content-Type':'application/json'}, ...options});
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || `请求失败：${response.status}`);
      return payload;
    }

    function toast(message) {
      const node = $('toast'); node.textContent = message; node.classList.add('show');
      clearTimeout(toast.timer); toast.timer = setTimeout(() => node.classList.remove('show'), 2600);
    }

    function setBusy(value) {
      state.busy = value; $('sendButton').disabled = value; $('messageInput').disabled = value;
      $('sendButton').textContent = value ? '…' : '↑';
    }

    async function bootstrap() {
      try {
        [state.health] = await Promise.all([request('/debug/health'), refreshTasks(false)]);
        renderHealth();
        if (state.tasks[0]) await loadTask(state.tasks[0].taskId);
        else renderAll();
      } catch (error) { toast(error.message); renderAll(); }
    }

    async function refreshTasks(render = true) {
      const payload = await request('/debug/tasks?limit=80');
      state.tasks = payload.tasks || [];
      if (render) renderTaskList();
      return payload;
    }

    async function loadTask(taskId) {
      try {
        const [task, timeline] = await Promise.all([request(`/tasks/${encodeURIComponent(taskId)}`), request(`/debug/tasks/${encodeURIComponent(taskId)}/timeline`)]);
        state.task = task; state.timeline = timeline;
        await refreshTasks(false); renderAll();
      } catch (error) { toast(error.message); }
    }

    async function createTask(text) {
      const content = text.trim(); if (!content || state.busy) return;
      setBusy(true);
      try {
        const task = await request('/tasks/invoke', {method:'POST', body: JSON.stringify({content:[{text: content}]})});
        $('messageInput').value = ''; state.task = task;
        state.timeline = await request(`/debug/tasks/${encodeURIComponent(task.taskId)}/timeline`);
        await refreshTasks(false); renderAll();
      } catch (error) { toast(error.message); }
      finally { setBusy(false); }
    }

    async function resume(response, content = '') {
      const interaction = state.task?.interaction; if (!interaction || state.busy) return;
      setBusy(true);
      try {
        state.task = await request(`/tasks/${encodeURIComponent(state.task.taskId)}/resume`, {
          method:'POST', body: JSON.stringify({interactionId: interaction.interaction_id, response, content: content ? [{text:content}] : []})
        });
        state.timeline = await request(`/debug/tasks/${encodeURIComponent(state.task.taskId)}/timeline`);
        await refreshTasks(false); renderAll();
      } catch (error) { toast(error.message); }
      finally { setBusy(false); }
    }

    function renderAll() {
      renderTaskList(); renderHeader(); renderConversation(); renderMetrics(); renderPanel(); renderHealth();
      requestAnimationFrame(() => { const box = $('conversation'); box.scrollTop = box.scrollHeight; });
    }

    function renderHealth() {
      const modes = state.health?.modes || {};
      $('modeBadges').innerHTML = modes.runtime ? [
        `<span class="badge accent">${esc(modes.runtime)}</span>`, `<span class="badge">Planner · ${esc(modes.planner)}</span>`,
        `<span class="badge">${esc(modes.model)}</span>`, `<span class="badge">飞书 · ${esc(modes.feishu)}</span>`
      ].join('') : '<span class="badge">配置状态不可用</span>';
    }

    function renderTaskList() {
      $('taskList').innerHTML = state.tasks.length ? state.tasks.map(task => `
        <button class="task-item ${state.task?.taskId === task.taskId ? 'active' : ''}" data-task="${esc(task.taskId)}">
          <div class="task-title">${esc(task.title || task.originalInput)}</div>
          <div class="task-meta"><span><i class="status-dot ${esc(task.status)}"></i>${esc(statusName[task.status] || task.status)}</span><span>${task.stepCount} 步</span></div>
        </button>`).join('') : '<div style="padding:16px 10px;color:var(--muted);font-size:12px">还没有调试任务</div>';
      document.querySelectorAll('[data-task]').forEach(node => node.onclick = () => loadTask(node.dataset.task));
    }

    function renderHeader() {
      const taskState = state.task?.taskState;
      $('pageTitle').textContent = taskState?.goal?.summary || '对话调试台';
      $('taskId').textContent = state.task?.taskId || '每一轮只规划并执行一个小步骤';
    }

    function renderConversation() {
      if (!state.task) {
        $('conversation').innerHTML = `<div class="empty"><div class="empty-orb">⌁</div><h3>把多步骤过程摊开来看</h3><p>输入一个真实场景，右侧会同步显示动作数、每轮 Decision、Observation 回流和完整 TaskState。</p><div class="scenarios">${scenarios.map(([title,text]) => `<button class="scenario" data-scenario="${esc(text)}"><strong>${esc(title)}</strong><span>${esc(text)}</span></button>`).join('')}</div></div>`;
        document.querySelectorAll('[data-scenario]').forEach(node => node.onclick = () => { $('messageInput').value = node.dataset.scenario; $('messageInput').focus(); });
        return;
      }
      const taskState = state.task.taskState || {};
      const messages = (taskState.user_events || []).map(event => messageHtml('user', eventLabel(event.event_type), event.content));
      if (state.task.status === 'completed' && state.task.content?.[0]?.text) messages.push(messageHtml('assistant', '最终回答', state.task.content[0].text));
      if (state.task.status === 'failed') messages.push(messageHtml('assistant', '任务失败', state.task.errorText || '任务执行失败。'));
      if (state.task.status === 'cancelled') messages.push(messageHtml('assistant', '已取消', state.task.content?.[0]?.text || '已取消本次任务。'));
      if (state.task.interaction) messages.push(interactionHtml(state.task.interaction));
      $('conversation').innerHTML = messages.join('');
      bindInteraction();
    }

    function messageHtml(role, label, content) {
      return `<div class="message ${role}"><div class="avatar">${role === 'user' ? '你' : '2'}</div><div class="bubble"><div class="message-label">${esc(label)}</div>${esc(content)}</div></div>`;
    }

    function eventLabel(type) {
      return ({user_input:'初始目标', user_reply:'补充回答', user_modification:'修改要求', user_confirmation:'执行确认'})[type] || '用户输入';
    }

    function interactionHtml(interaction) {
      const options = interaction.options || [];
      const preview = interaction.preview ? `<pre class="preview">${json(interaction.preview)}</pre>` : '';
      const optionButtons = interaction.kind !== 'confirm' && options.length ? `<div class="option-row">${options.map((item, index) => `<button class="option" data-option="${esc(typeof item === 'string' ? item : JSON.stringify(item))}">${index + 1}. ${esc(typeof item === 'string' ? item : item.label || item.name || JSON.stringify(item))}</button>`).join('')}</div>` : '';
      const controls = interaction.kind === 'confirm'
        ? `<div class="action-row"><button class="btn primary" id="approveAction">确认执行</button><input class="inline-input" id="interactionInput" placeholder="如需修改，输入新的要求"><button class="btn" id="modifyAction">修改</button><button class="btn danger" id="cancelAction">取消</button></div>`
        : `<div class="action-row"><input class="inline-input" id="interactionInput" placeholder="输入回答或点击上方候选"><button class="btn primary" id="answerAction">提交回答</button><button class="btn danger" id="cancelAction">取消任务</button></div>`;
      return `<div class="interaction-card"><div class="interaction-title"><span>${esc(interactionName[interaction.kind] || interaction.kind)}</span><span>执行已暂停</span></div><div class="interaction-question">${esc(interaction.question)}</div>${optionButtons}${preview}${controls}</div>`;
    }

    function bindInteraction() {
      const input = $('interactionInput');
      document.querySelectorAll('[data-option]').forEach(node => node.onclick = () => { input.value = node.dataset.option; input.focus(); });
      if ($('approveAction')) $('approveAction').onclick = () => resume('approve', '确认');
      if ($('modifyAction')) $('modifyAction').onclick = () => resume('modify', input.value.trim());
      if ($('answerAction')) $('answerAction').onclick = () => resume('answer', input.value.trim());
      if ($('cancelAction')) $('cancelAction').onclick = () => resume('cancel', '取消');
      if (input) input.onkeydown = event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); $('answerAction')?.click(); } };
    }

    function renderMetrics() {
      const task = state.task?.taskState;
      $('metrics').innerHTML = [
        ['已走步骤', task?.step_count ?? 0], ['当前状态', statusName[state.task?.status] || state.task?.status || '未开始'], ['上限', task?.max_steps ?? '—']
      ].map(([label,value]) => `<div class="metric"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join('');
    }

    function renderPanel() {
      document.querySelectorAll('.tab').forEach(tab => tab.classList.toggle('active', tab.dataset.tab === state.activeTab));
      const panel = $('panelContent');
      if (state.activeTab === 'timeline') panel.innerHTML = timelineHtml();
      if (state.activeTab === 'state') panel.innerHTML = `<pre class="json">${json(state.task?.taskState || {})}</pre>`;
      if (state.activeTab === 'decision') panel.innerHTML = decisionHtml();
      if (state.activeTab === 'artifacts') panel.innerHTML = artifactsHtml();
      if (state.activeTab === 'config') panel.innerHTML = configHtml();
    }

    function timelineHtml() {
      const steps = state.timeline?.steps || [];
      if (!steps.length) return '<div style="color:var(--muted)">还没有执行动作。发送消息后，这里会按顺序显示每个小步骤。</div>';
      return `<div class="timeline">${steps.map(step => `<div class="step"><div class="step-dot ${esc(step.status)}">${step.step}</div><div class="step-body"><div class="step-head"><span class="step-name">${esc(step.action_name)}</span><span class="step-status">${esc(step.status)}</span></div>${step.observation_summary ? `<div class="step-summary">${esc(step.observation_summary)}</div>` : ''}${step.decision_summary ? `<div class="step-decision">决策：${esc(step.decision_summary)}</div>` : ''}${step.expected_outcome ? `<div class="step-decision">预期：${esc(step.expected_outcome)}</div>` : ''}${step.error_code ? `<div class="step-decision" style="color:var(--danger)">${esc(step.error_code)}</div>` : ''}</div></div>`).join('')}</div>`;
    }

    function decisionHtml() {
      const timeline = state.timeline || {};
      return `<div style="margin-bottom:8px;color:var(--muted);font-size:11px">最近一次策划决策</div><pre class="json">${json(timeline.lastDecision)}</pre><div style="margin:15px 0 8px;color:var(--muted);font-size:11px">最近一次动作回流</div><pre class="json">${json(timeline.lastObservation)}</pre>`;
    }

    function artifactsHtml() {
      const artifacts = state.timeline?.artifacts || [];
      if (!artifacts.length) return '<div style="color:var(--muted)">当前任务还没有 Artifact。</div>';
      return artifacts.slice().reverse().map(item => `<details class="artifact"><summary>${esc(item.artifact_key)} · ${esc(item.artifact_id)}</summary><pre class="json">${json(item.data)}</pre></details>`).join('');
    }

    function configHtml() {
      const health = state.health || {}; const modes = health.modes || {};
      const rows = Object.entries(modes).map(([key,value]) => `<div class="config-row"><span>${esc(key)}</span><strong>${esc(value)}</strong></div>`).join('');
      const checks = (health.checks || []).map(item => `<div class="check ${esc(item.status)}"><strong>${esc(item.status.toUpperCase())}</strong> · ${esc(item.name)}<div style="color:var(--muted);font-size:11px;margin-top:3px">${esc(item.detail)}</div></div>`).join('');
      return `<div style="margin-bottom:12px;color:var(--muted);font-size:11px">${esc(health.note || '配置沿用 third。')}</div>${rows}<div style="margin-top:14px">${checks}</div>`;
    }

    $('newTask').onclick = () => { state.task = null; state.timeline = null; renderAll(); $('messageInput').focus(); };
    $('sendButton').onclick = () => createTask($('messageInput').value);
    $('messageInput').onkeydown = event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); createTask(event.target.value); } };
    $('messageInput').oninput = event => { event.target.style.height = 'auto'; event.target.style.height = `${Math.min(event.target.scrollHeight, 140)}px`; };
    $('tabs').onclick = event => { const tab = event.target.closest('[data-tab]'); if (!tab) return; state.activeTab = tab.dataset.tab; renderPanel(); };
    bootstrap();
  </script>
</body>
</html>'''
