"""调试台页面模板。"""

from __future__ import annotations


# 这个函数返回内置调试台 HTML，页面通过 fetch 调用 third API。
def debug_page_html() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>third Workflow 调试台</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --line: #d9dde4;
      --text: #1d2633;
      --muted: #687384;
      --ok: #147a49;
      --warn: #9a5b00;
      --bad: #b42318;
      --run: #1f5fbf;
      --wait: #7a4cc2;
      --accent: #1c6b6a;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
      font-size: 14px;
      letter-spacing: 0;
    }

    button,
    input,
    textarea {
      font: inherit;
    }

    button {
      border: 1px solid var(--line);
      background: #fff;
      color: var(--text);
      border-radius: 6px;
      padding: 8px 12px;
      cursor: pointer;
      min-height: 36px;
    }

    button.primary {
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }

    button.danger {
      border-color: #e5b8b4;
      color: var(--bad);
    }

    button:disabled {
      cursor: not-allowed;
      opacity: 0.55;
    }

    textarea {
      width: 100%;
      min-height: 88px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      background: #fff;
      color: var(--text);
    }

    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: Consolas, "SFMono-Regular", Menlo, monospace;
      font-size: 12px;
      line-height: 1.5;
    }

    .layout {
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr;
    }

    .topbar {
      border-bottom: 1px solid var(--line);
      background: var(--panel);
      padding: 14px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }

    .top-actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 10px;
      flex-wrap: wrap;
    }

    .toggle {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
      user-select: none;
    }

    .toggle input {
      width: 16px;
      height: 16px;
      margin: 0;
    }

    .title {
      font-size: 18px;
      font-weight: 700;
    }

    .subtitle {
      color: var(--muted);
      font-size: 12px;
      margin-top: 3px;
    }

    .main {
      display: grid;
      grid-template-columns: 320px minmax(0, 1fr);
      gap: 14px;
      padding: 14px;
      min-height: 0;
    }

    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }

    .panel-header {
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }

    .panel-title {
      font-weight: 700;
    }

    .panel-body {
      padding: 14px;
    }

    .sidebar {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      gap: 14px;
      min-height: 0;
    }

    .session-list {
      display: grid;
      gap: 8px;
      max-height: calc(100vh - 380px);
      overflow: auto;
    }

    .session-item {
      text-align: left;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      display: grid;
      gap: 6px;
    }

    .session-item.active {
      border-color: var(--accent);
      box-shadow: 0 0 0 2px rgba(28, 107, 106, 0.12);
    }

    .session-id {
      font-family: Consolas, "SFMono-Regular", Menlo, monospace;
      font-size: 12px;
    }

    .session-input {
      color: var(--muted);
      font-size: 12px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .status {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: fit-content;
      min-height: 24px;
      padding: 3px 8px;
      border-radius: 999px;
      border: 1px solid var(--line);
      font-size: 12px;
      font-weight: 600;
      background: #fff;
    }

    .status.success,
    .status.ok {
      color: var(--ok);
      border-color: #9fd6bb;
      background: #f0fbf5;
    }

    .status.running,
    .status.queued {
      color: var(--run);
      border-color: #aac8f0;
      background: #f0f6ff;
    }

    .status.waiting_user,
    .status.waiting {
      color: var(--wait);
      border-color: #cbb9ee;
      background: #f7f2ff;
    }

    .status.failed,
    .status.error,
    .status.cancelled {
      color: var(--bad);
      border-color: #efb4ae;
      background: #fff2f0;
    }

    .status.warning,
    .status.missing,
    .status.skipped {
      color: var(--warn);
      border-color: #efd199;
      background: #fff8e8;
    }

    .content-grid {
      display: grid;
      grid-template-rows: auto auto minmax(0, 1fr);
      gap: 14px;
      min-width: 0;
    }

    .health-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 8px;
    }

    .check {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px;
      display: grid;
      gap: 6px;
      background: #fff;
    }

    .check-name {
      font-weight: 700;
    }

    .check-message {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
    }

    .tabs {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }

    .tab {
      border-radius: 6px;
      padding: 7px 10px;
    }

    .tab.active {
      background: #26323f;
      color: #fff;
      border-color: #26323f;
    }

    .view {
      display: none;
    }

    .view.active {
      display: block;
    }

    .step-list {
      display: grid;
      gap: 8px;
    }

    .step {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      display: grid;
      gap: 8px;
      background: #fff;
    }

    .step-head,
    .artifact-head,
    .confirm-actions {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      flex-wrap: wrap;
    }

    .step-title {
      font-weight: 700;
    }

    .meta {
      color: var(--muted);
      font-size: 12px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }

    .graph {
      display: flex;
      align-items: center;
      gap: 8px;
      overflow: auto;
      padding-bottom: 8px;
    }

    .graph-node {
      min-width: 180px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      background: #fff;
      display: grid;
      gap: 8px;
    }

    .arrow {
      color: var(--muted);
      font-weight: 700;
    }

    .json-box {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fbfcfd;
      padding: 10px;
      max-height: 420px;
      overflow: auto;
    }

    .artifact-list {
      display: grid;
      gap: 8px;
    }

    .artifact {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      background: #fff;
      display: grid;
      gap: 8px;
    }

    .empty {
      color: var(--muted);
      padding: 12px;
      border: 1px dashed var(--line);
      border-radius: 6px;
      background: #fff;
    }

    @media (max-width: 900px) {
      .main {
        grid-template-columns: 1fr;
      }

      .session-list {
        max-height: 260px;
      }
    }
  </style>
</head>
<body>
  <div class="layout">
    <header class="topbar">
      <div>
        <div class="title">third Workflow 调试台</div>
        <div class="subtitle">查看 workflowagent 计划、步骤状态、artifact、确认门和最终答案</div>
      </div>
      <div class="top-actions">
        <label class="toggle">
          <input id="auto-refresh" type="checkbox" checked />
          自动刷新
        </label>
        <span id="poll-status" class="subtitle">运行中每 1.8s 刷新</span>
        <button id="refresh-all">刷新</button>
      </div>
    </header>

    <main class="main">
      <section class="sidebar">
        <div class="panel">
          <div class="panel-header">
            <div class="panel-title">提交 workflow</div>
          </div>
          <div class="panel-body">
            <textarea id="workflow-input">查询状态为进行中的记录，只返回标题、状态</textarea>
            <div style="display:flex; gap:8px; margin-top:10px;">
              <button class="primary" id="submit-workflow">提交</button>
              <button id="use-write-demo">写入示例</button>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <div class="panel-title">最近 session</div>
            <button id="refresh-sessions">刷新</button>
          </div>
          <div class="panel-body">
            <div id="sessions" class="session-list"></div>
          </div>
        </div>
      </section>

      <section class="content-grid">
        <div class="panel">
          <div class="panel-header">
            <div class="panel-title">运行模式体检</div>
            <span id="health-summary" class="status">loading</span>
          </div>
          <div class="panel-body">
            <div id="health" class="health-grid"></div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <div>
              <div class="panel-title">当前 workflow</div>
              <div id="current-session" class="subtitle">未选择 session</div>
            </div>
            <div class="tabs">
              <button class="tab active" data-view="timeline">时间线</button>
              <button class="tab" data-view="graph">动态图</button>
              <button class="tab" data-view="artifacts">Artifacts</button>
              <button class="tab" data-view="raw">JSON</button>
            </div>
          </div>
          <div class="panel-body">
            <div id="confirm-box"></div>
            <div id="timeline" class="view active"></div>
            <div id="graph" class="view"></div>
            <div id="artifacts" class="view"></div>
            <div id="raw" class="view"></div>
          </div>
        </div>
      </section>
    </main>
  </div>

  <script>
    const state = {
      sessionId: "",
      timeline: null,
      graph: null,
      artifacts: null,
      poller: null,
      autoRefresh: true,
      refreshing: false,
      activeView: "timeline"
    };

    const $ = (id) => document.getElementById(id);

    document.addEventListener("DOMContentLoaded", () => {
      $("submit-workflow").addEventListener("click", submitWorkflow);
      $("refresh-sessions").addEventListener("click", loadSessions);
      $("refresh-all").addEventListener("click", refreshAll);
      $("auto-refresh").addEventListener("change", () => {
        state.autoRefresh = $("auto-refresh").checked;
        updateAutoRefreshStatus();
      });
      $("use-write-demo").addEventListener("click", () => {
        $("workflow-input").value = "新增一条记录，标题为测试新增，状态为进行中";
      });
      document.querySelectorAll(".tab").forEach((button) => {
        button.addEventListener("click", () => setView(button.dataset.view));
      });
      refreshAll();
      state.poller = window.setInterval(() => {
        if (shouldAutoRefreshCurrent()) {
          refreshCurrent(false, {preserveScroll: true, auto: true}).catch(() => {
            updateAutoRefreshStatus("自动刷新失败");
          });
        }
      }, 1800);
    });

    async function refreshAll() {
      await Promise.all([loadHealth(), loadSessions()]);
      if (state.sessionId) {
        await refreshCurrent(true, {preserveScroll: true});
      }
    }

    async function loadHealth() {
      try {
        const payload = await getJson("/debug/health");
        const checks = payload.checks || [];
        const hasError = checks.some((item) => item.status === "error");
        const hasWarn = checks.some((item) => ["warning", "missing", "skipped"].includes(item.status));
        $("health-summary").className = `status ${hasError ? "error" : hasWarn ? "warning" : "ok"}`;
        $("health-summary").textContent = hasError ? "error" : hasWarn ? "warning" : "ok";
        $("health").innerHTML = checks.map(renderCheck).join("") || `<div class="empty">暂无体检信息</div>`;
      } catch (error) {
        $("health-summary").className = "status error";
        $("health-summary").textContent = "error";
        $("health").innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
      }
    }

    async function loadSessions() {
      try {
        const payload = await getJson("/debug/workflows?limit=50");
        const sessions = payload.sessions || [];
        const errorText = payload.error_text ? `<div class="empty">${escapeHtml(payload.error_text)}</div>` : "";
        $("sessions").innerHTML = errorText || (sessions.length ? sessions.map(renderSession).join("") : `<div class="empty">暂无 workflow</div>`);
        document.querySelectorAll(".session-item").forEach((button) => {
          button.addEventListener("click", () => selectSession(button.dataset.sessionId));
        });
      } catch (error) {
        $("sessions").innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
      }
    }

    async function submitWorkflow() {
      const text = $("workflow-input").value.trim();
      if (!text) {
        return;
      }
      $("submit-workflow").disabled = true;
      try {
        const response = await fetch("/v1/workflows/invoke", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({content: [{text}]})
        });
        if (!response.ok) {
          throw new Error(await response.text());
        }
        const payload = await response.json();
        state.sessionId = payload.sessionId;
        await loadSessions();
        await refreshCurrent(true);
      } catch (error) {
        alert(error.message);
      } finally {
        $("submit-workflow").disabled = false;
      }
    }

    async function selectSession(sessionId) {
      state.sessionId = sessionId;
      await refreshCurrent(true);
      await loadSessions();
    }

    // 这个函数刷新当前 session 详情，按参数决定是否保留滚动位置。
    async function refreshCurrent(showLoading, options = {}) {
      if (!state.sessionId || state.refreshing) {
        return;
      }
      state.refreshing = true;
      const scrollState = options.preserveScroll ? captureScrollState() : null;
      if (showLoading) {
        $("current-session").textContent = `${state.sessionId} 加载中`;
      }
      try {
        const [timeline, graph, artifacts] = await Promise.all([
          getJson(`/debug/workflows/${encodeURIComponent(state.sessionId)}/timeline`),
          getJson(`/debug/workflows/${encodeURIComponent(state.sessionId)}/graph`),
          getJson(`/debug/workflows/${encodeURIComponent(state.sessionId)}/artifacts`)
        ]);
        state.timeline = timeline;
        state.graph = graph;
        state.artifacts = artifacts;
        renderCurrent();
        if (scrollState) {
          restoreScrollState(scrollState);
        }
      } finally {
        state.refreshing = false;
        updateAutoRefreshStatus();
      }
    }

    async function resumeWorkflow(approved) {
      const confirmation = state.timeline && state.timeline.confirmation;
      if (!confirmation || !confirmation.confirmation_id) {
        return;
      }
      const response = await fetch(`/v1/workflows/${encodeURIComponent(state.sessionId)}/resume`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          confirmationId: confirmation.confirmation_id,
          approved,
          response: approved ? "approve" : "cancel",
          content: [{text: approved ? "确认执行" : "拒绝执行"}]
        })
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      await refreshCurrent(true, {preserveScroll: true});
      await loadSessions();
    }

    function renderCurrent() {
      const session = state.timeline.session || {};
      $("current-session").innerHTML = `${escapeHtml(session.session_id || "")} <span class="status ${escapeAttr(session.status || "")}">${escapeHtml(session.status || "")}</span>`;
      renderConfirmation();
      renderTimeline();
      renderGraph();
      renderArtifacts();
      $("raw").innerHTML = `<div class="json-box"><pre>${escapeHtml(JSON.stringify(state.timeline, null, 2))}</pre></div>`;
    }

    // 这个函数判断当前 session 是否还需要自动刷新详情。
    function shouldAutoRefreshCurrent() {
      if (!state.autoRefresh || !state.sessionId || state.refreshing) {
        return false;
      }
      const session = state.timeline && state.timeline.session;
      if (!session || !session.status) {
        return true;
      }
      return ["queued", "running"].includes(session.status);
    }

    // 这个函数更新顶部自动刷新状态提示。
    function updateAutoRefreshStatus(message) {
      if (message) {
        $("poll-status").textContent = message;
        return;
      }
      if (!state.autoRefresh) {
        $("poll-status").textContent = "自动刷新已关闭";
        return;
      }
      const status = state.timeline && state.timeline.session && state.timeline.session.status;
      if (!state.sessionId) {
        $("poll-status").textContent = "选择 session 后自动刷新";
      } else if (["queued", "running"].includes(status)) {
        $("poll-status").textContent = "运行中每 1.8s 刷新";
      } else if (status) {
        $("poll-status").textContent = `已暂停，当前状态 ${status}`;
      } else {
        $("poll-status").textContent = "等待 workflow 状态";
      }
    }

    // 这个函数记录页面和当前视图的滚动位置，避免刷新后跳回顶部。
    function captureScrollState() {
      const view = $(state.activeView);
      return {
        windowY: window.scrollY,
        viewId: state.activeView,
        viewTop: view ? view.scrollTop : 0,
        boxTops: view ? Array.from(view.querySelectorAll(".json-box")).map((box) => box.scrollTop) : []
      };
    }

    // 这个函数在重绘后恢复滚动位置，主要服务 Artifacts 和 JSON 视图。
    function restoreScrollState(scrollState) {
      window.requestAnimationFrame(() => {
        window.scrollTo(0, scrollState.windowY || 0);
        const view = $(scrollState.viewId);
        if (!view) {
          return;
        }
        view.scrollTop = scrollState.viewTop || 0;
        Array.from(view.querySelectorAll(".json-box")).forEach((box, index) => {
          box.scrollTop = scrollState.boxTops[index] || 0;
        });
      });
    }

    function renderConfirmation() {
      const confirmation = state.timeline.confirmation;
      if (!confirmation || confirmation.status !== "waiting") {
        $("confirm-box").innerHTML = "";
        return;
      }
      $("confirm-box").innerHTML = `
        <div class="step" style="margin-bottom:12px; border-color:#cbb9ee;">
          <div class="step-head">
            <div class="step-title">${escapeHtml(confirmation.request_text || "等待确认")}</div>
            <span class="status waiting">waiting</span>
          </div>
          <div class="json-box"><pre>${escapeHtml(JSON.stringify(confirmation.preview_json || {}, null, 2))}</pre></div>
          <div class="confirm-actions">
            <button class="primary" id="approve-confirm">确认执行</button>
            <button class="danger" id="reject-confirm">拒绝执行</button>
          </div>
        </div>`;
      $("approve-confirm").addEventListener("click", () => resumeWorkflow(true));
      $("reject-confirm").addEventListener("click", () => resumeWorkflow(false));
    }

    function renderTimeline() {
      const steps = state.timeline.steps || [];
      const finalAnswer = state.timeline.session && state.timeline.session.final_answer;
      const errorText = state.timeline.session && state.timeline.session.error_text;
      const items = steps.map(renderStep).join("");
      const summary = finalAnswer || errorText
        ? `<div class="step"><div class="step-title">${finalAnswer ? "最终答案" : "错误"}</div><div class="json-box"><pre>${escapeHtml(finalAnswer || errorText)}</pre></div></div>`
        : "";
      $("timeline").innerHTML = `<div class="step-list">${items || `<div class="empty">暂无步骤</div>`}${summary}</div>`;
    }

    function renderGraph() {
      const nodes = state.graph.nodes || [];
      const nodeHtml = nodes.map((node, index) => `
        <div style="display:flex; align-items:center; gap:8px;">
          <div class="graph-node">
            <div class="step-title">${escapeHtml(node.label || node.id)}</div>
            <span class="status ${escapeAttr(node.status || "")}">${escapeHtml(node.status || "")}</span>
          </div>
          ${index < nodes.length - 1 ? `<div class="arrow">→</div>` : ""}
        </div>`).join("");
      $("graph").innerHTML = `
        <div class="graph">${nodeHtml || `<div class="empty">暂无图数据</div>`}</div>
        <div class="json-box" style="margin-top:12px;"><pre>${escapeHtml(state.graph.mermaid || "")}</pre></div>`;
    }

    function renderArtifacts() {
      const artifacts = state.artifacts.artifacts || [];
      $("artifacts").innerHTML = `<div class="artifact-list">${artifacts.map(renderArtifact).join("") || `<div class="empty">暂无 artifact</div>`}</div>`;
    }

    function renderCheck(item) {
      return `
        <div class="check">
          <div class="check-name">${escapeHtml(item.name)}</div>
          <span class="status ${escapeAttr(item.status)}">${escapeHtml(item.status)}</span>
          <div class="check-message">${escapeHtml(item.message || "")}</div>
        </div>`;
    }

    function renderSession(session) {
      const active = session.session_id === state.sessionId ? " active" : "";
      return `
        <button class="session-item${active}" data-session-id="${escapeAttr(session.session_id)}">
          <div class="step-head">
            <span class="session-id">${escapeHtml(session.session_id)}</span>
            <span class="status ${escapeAttr(session.status)}">${escapeHtml(session.status)}</span>
          </div>
          <div class="session-input">${escapeHtml(session.original_input || "")}</div>
        </button>`;
    }

    function renderStep(step) {
      const artifactNames = (step.artifacts || []).map((artifact) => escapeHtml(artifact.artifact_key)).join("、") || "无";
      return `
        <div class="step">
          <div class="step-head">
            <div class="step-title">${escapeHtml(step.step_seq + ". " + step.name)}</div>
            <span class="status ${escapeAttr(step.status)}">${escapeHtml(step.status)}</span>
          </div>
          <div class="meta">
            <span>kind: ${escapeHtml(step.kind || "")}</span>
            <span>output: ${escapeHtml(step.output_key || "")}</span>
            <span>duration: ${step.duration_ms === null || step.duration_ms === undefined ? "-" : escapeHtml(String(step.duration_ms)) + "ms"}</span>
            <span>artifacts: ${artifactNames}</span>
          </div>
          ${step.error_text ? `<div class="json-box"><pre>${escapeHtml(step.error_text)}</pre></div>` : ""}
        </div>`;
    }

    function renderArtifact(artifact) {
      return `
        <div class="artifact">
          <div class="artifact-head">
            <div class="step-title">${escapeHtml(artifact.artifact_key)}</div>
            <span class="session-id">${escapeHtml(artifact.artifact_id)}</span>
          </div>
          <div class="meta">
            <span>source: ${escapeHtml(artifact.source_step_id || "-")}</span>
            <span>created: ${escapeHtml(artifact.created_at || "")}</span>
          </div>
          <div class="json-box"><pre>${escapeHtml(JSON.stringify(artifact.data_json || {}, null, 2))}</pre></div>
        </div>`;
    }

    async function getJson(url) {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(await response.text());
      }
      return response.json();
    }

    function setView(viewName) {
      state.activeView = viewName;
      document.querySelectorAll(".tab").forEach((button) => {
        button.classList.toggle("active", button.dataset.view === viewName);
      });
      document.querySelectorAll(".view").forEach((view) => {
        view.classList.toggle("active", view.id === viewName);
      });
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function escapeAttr(value) {
      return escapeHtml(value).replaceAll(" ", "_");
    }
  </script>
</body>
</html>"""
