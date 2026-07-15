import { FormEvent, useEffect, useState } from "react";
import { Activity, CalendarRange, FileText, HeartHandshake, LogOut, RefreshCw, Search, Settings2 } from "lucide-react";
import { JsonPanel } from "../../components/ops/JsonPanel";
import { OpsTable } from "../../components/ops/OpsTable";
import { Pressable } from "../../components/ui/Pressable";
import {
  fetchOpsDailyContents,
  fetchOpsDashboard,
  fetchOpsRecordDetail,
  fetchOpsRecords,
  fetchOpsRecordTrace,
  fetchOpsSessionTrace,
  fetchOpsTrace,
  retryOpsRecordSync,
  saveOpsDailyContents,
  updateOpsRecordDisplay,
  type OpsRecord
} from "./api";

type OpsView = "records" | "daily" | "trace";

function today() {
  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: "Asia/Shanghai"
  }).format(new Date());
}

function objectValue(source: Record<string, unknown> | null, key: string) {
  const value = source?.[key];
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

// 这个组件承载后台运维的记录、每日内容与追踪工作区。
export function OpsWorkspace({ onLogout }: { onLogout: () => void }) {
  const [view, setView] = useState<OpsView>("records");
  const [dashboard, setDashboard] = useState<Record<string, unknown>>({});
  const [records, setRecords] = useState<OpsRecord[]>([]);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [trace, setTrace] = useState<Record<string, unknown> | null>(null);
  const [busyLabel, setBusyLabel] = useState("");
  const [status, setStatus] = useState("");
  const [recordDate, setRecordDate] = useState("");
  const [recordStatus, setRecordStatus] = useState("");
  const [onlyAbnormal, setOnlyAbnormal] = useState(false);
  const [dailyTargetUserId, setDailyTargetUserId] = useState("");
  const [dailyDate, setDailyDate] = useState(today);
  const [dailyContents, setDailyContents] = useState("[]");
  const [traceSessionId, setTraceSessionId] = useState("");
  const [traceRecordId, setTraceRecordId] = useState("");
  const [traceThirdSessionId, setTraceThirdSessionId] = useState("");
  const [displayTitle, setDisplayTitle] = useState("");
  const [displaySummary, setDisplaySummary] = useState("");
  const [displayScore, setDisplayScore] = useState("80");
  const [displayStatus, setDisplayStatus] = useState("visible");

  useEffect(() => {
    void runOpsAction("正在加载工作区", bootstrapOps);
  }, []);

  useEffect(() => {
    const display = objectValue(detail, "display");
    setDisplayTitle(String(display.title ?? ""));
    setDisplaySummary(String(display.summary ?? ""));
    setDisplayScore(String(display.score ?? 80));
    setDisplayStatus(String(display.displayStatus ?? "visible"));
  }, [detail]);

  async function bootstrapOps() {
    const [dashboardData, recordItems] = await Promise.all([
      fetchOpsDashboard(),
      fetchOpsRecords({ date: recordDate || undefined, status: recordStatus || undefined, onlyAbnormal })
    ]);
    setDashboard(dashboardData);
    setRecords(recordItems);
  }

  async function runOpsAction(label: string, action: () => Promise<void>) {
    setBusyLabel(label);
    setStatus("");
    try {
      await action();
      return true;
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "操作失败");
      return false;
    } finally {
      setBusyLabel("");
    }
  }

  function filterRecords(event: FormEvent) {
    event.preventDefault();
    void runOpsAction("正在筛选记录", async () => {
      setRecords(await fetchOpsRecords({ date: recordDate || undefined, status: recordStatus || undefined, onlyAbnormal }));
      setDetail(null);
    });
  }

  function openDetail(recordId: string) {
    void runOpsAction("正在读取记录详情", async () => {
      setDetail(await fetchOpsRecordDetail(recordId));
      setTrace(null);
    });
  }

  function openRecordTrace(recordId: string) {
    void runOpsAction("正在聚合记录追踪", async () => {
      setTrace(await fetchOpsRecordTrace(recordId));
      setTraceRecordId(recordId);
      setView("trace");
    });
  }

  function retrySync() {
    const record = objectValue(detail, "record");
    const recordId = String(record.id ?? "");
    if (!recordId) return;
    void runOpsAction("正在提交同步重试", async () => {
      await retryOpsRecordSync(recordId);
      setDetail(await fetchOpsRecordDetail(recordId));
      setRecords(await fetchOpsRecords({ date: recordDate || undefined, status: recordStatus || undefined, onlyAbnormal }));
    });
  }

  function saveDisplay(event: FormEvent) {
    event.preventDefault();
    const record = objectValue(detail, "record");
    const recordId = String(record.id ?? "");
    const score = Number(displayScore);
    if (!recordId || !Number.isFinite(score)) {
      setStatus("展示分数必须是数字");
      return;
    }
    void runOpsAction("正在保存用户端展示", async () => {
      await updateOpsRecordDisplay(recordId, {
        title: displayTitle,
        summary: displaySummary,
        score,
        displayStatus
      });
      setDetail(await fetchOpsRecordDetail(recordId));
    });
  }

  function loadDailyContents(event: FormEvent) {
    event.preventDefault();
    if (!dailyTargetUserId.trim()) {
      setStatus("请输入目标用户 ID");
      return;
    }
    void runOpsAction("正在读取每日内容", async () => {
      const result = await fetchOpsDailyContents(dailyTargetUserId.trim(), dailyDate);
      setDailyContents(JSON.stringify(result.contents ?? [], null, 2));
    });
  }

  function saveDaily(event: FormEvent) {
    event.preventDefault();
    let contents: Record<string, unknown>[];
    try {
      const parsed = JSON.parse(dailyContents);
      if (!Array.isArray(parsed) || parsed.some((item) => !item || typeof item !== "object" || Array.isArray(item))) {
        throw new Error();
      }
      contents = parsed as Record<string, unknown>[];
    } catch {
      setStatus("每日内容必须是 JSON 对象数组");
      return;
    }
    void runOpsAction("正在保存每日内容", async () => {
      await saveOpsDailyContents(dailyTargetUserId.trim(), dailyDate, contents);
    });
  }

  function searchTrace(event: FormEvent) {
    event.preventDefault();
    const sessionId = traceSessionId.trim();
    const recordId = traceRecordId.trim();
    const thirdSessionId = traceThirdSessionId.trim();
    if (!sessionId && !recordId && !thirdSessionId) {
      setStatus("至少填写一个追踪 ID");
      return;
    }
    void runOpsAction("正在查询追踪信息", async () => {
      if (sessionId && !recordId && !thirdSessionId) {
        setTrace(await fetchOpsSessionTrace(sessionId));
      } else if (recordId && !sessionId && !thirdSessionId) {
        setTrace(await fetchOpsRecordTrace(recordId));
      } else {
        setTrace(await fetchOpsTrace({ sessionId: sessionId || undefined, recordId: recordId || undefined, thirdSessionId: thirdSessionId || undefined }));
      }
    });
  }

  const busy = Boolean(busyLabel);
  const detailRecord = objectValue(detail, "record");
  const detailSync = objectValue(detail, "latestFeishuSync");

  return (
    <section className="ops-layout">
      <aside>
        <div className="ops-brand"><span><HeartHandshake size={20} /></span><div><b>For My Girl</b><small>运维工作区</small></div></div>
        <nav className="ops-nav" aria-label="运维功能">
          <Pressable className={view === "records" ? "is-active" : ""} onClick={() => setView("records")}><FileText size={17} />记录与异常</Pressable>
          <Pressable className={view === "daily" ? "is-active" : ""} onClick={() => setView("daily")}><CalendarRange size={17} />每日内容</Pressable>
          <Pressable className={view === "trace" ? "is-active" : ""} onClick={() => setView("trace")}><Activity size={17} />链路追踪</Pressable>
        </nav>
        <div className="ops-sidebar-actions">
          <Pressable className="secondary-button" onClick={() => void runOpsAction("正在刷新", bootstrapOps)} disabled={busy}><RefreshCw size={16} />刷新数据</Pressable>
          <Pressable className="secondary-button" onClick={onLogout} disabled={busy}><LogOut size={16} />退出登录</Pressable>
        </div>
        {(busyLabel || status) && <p className="ops-status">{busyLabel || status}</p>}
      </aside>

      <main>
        <header className="ops-header">
          <div><span>CONTROL ROOM</span><h1>{view === "records" ? "记录与异常" : view === "daily" ? "每日内容配置" : "链路追踪"}</h1><p>{view === "records" ? "查看记录状态、修正展示并处理飞书同步异常。" : view === "daily" ? "为指定用户配置某一天的首页内容。" : "用会话、记录或 third session ID 定位完整链路。"}</p></div>
          <Settings2 size={23} />
        </header>

        {view === "records" && (
          <>
            <section className="summary">
              <div><span>今日记录</span><b>{String(dashboard.todayRecordCount ?? 0)}</b></div>
              <div><span>待反馈</span><b>{String(dashboard.pendingFeedbackCount ?? 0)}</b></div>
              <div><span>异常</span><b>{String(dashboard.abnormalCount ?? 0)}</b></div>
            </section>
            <form className="ops-toolbar" onSubmit={filterRecords}>
              <input type="date" value={recordDate} onChange={(event) => setRecordDate(event.target.value)} aria-label="记录日期" />
              <select value={recordStatus} onChange={(event) => setRecordStatus(event.target.value)} aria-label="记录状态">
                <option value="">全部状态</option>
                <option value="confirmed">已确认</option>
                <option value="syncing">同步中</option>
                <option value="sync_failed">同步失败</option>
                <option value="cancelled">已取消</option>
              </select>
              <label className="ops-checkbox"><input type="checkbox" checked={onlyAbnormal} onChange={(event) => setOnlyAbnormal(event.target.checked)} />只看异常</label>
              <Pressable className="primary-button" type="submit" disabled={busy}><Search size={16} />筛选</Pressable>
            </form>
            <OpsTable records={records} busy={busy} onDetail={openDetail} onTrace={openRecordTrace} />
            {detail && (
              <section className="ops-panel ops-record-detail">
                <div className="ops-panel__heading"><div><span>记录详情</span><h2>{String(detailRecord.id ?? "未命名记录")}</h2></div><strong>{String(detailRecord.status ?? "-")}</strong></div>
                <div className="ops-detail-metrics">
                  <div><span>记录日期</span><b>{String(detailRecord.recordDate ?? "-")}</b></div>
                  <div><span>AI 评分</span><b>{String(detailRecord.aiScore ?? "-")}</b></div>
                  <div><span>飞书同步</span><b>{String(detailSync.syncStatus ?? "未开始")}</b></div>
                </div>
                <form className="ops-form ops-form--display" onSubmit={saveDisplay}>
                  <label>用户端标题<input value={displayTitle} onChange={(event) => setDisplayTitle(event.target.value)} /></label>
                  <label>展示分数<input type="number" value={displayScore} onChange={(event) => setDisplayScore(event.target.value)} /></label>
                  <label className="ops-form__wide">用户端摘要<textarea value={displaySummary} onChange={(event) => setDisplaySummary(event.target.value)} /></label>
                  <label>展示状态<select value={displayStatus} onChange={(event) => setDisplayStatus(event.target.value)}><option value="visible">显示</option><option value="hidden">隐藏</option><option value="draft">草稿</option></select></label>
                  <div className="ops-detail-actions">
                    <Pressable className="secondary-button" type="button" disabled={busy} onClick={retrySync}>重试飞书同步</Pressable>
                    <Pressable className="primary-button" type="submit" disabled={busy}>保存用户端展示</Pressable>
                  </div>
                </form>
                <details className="ops-raw"><summary>查看原始详情</summary><JsonPanel title="原始记录详情" data={detail} /></details>
              </section>
            )}
          </>
        )}

        {view === "daily" && (
          <section className="ops-panel">
            <div className="ops-panel__heading"><div><span>首页内容</span><h2>按用户和日期配置</h2></div></div>
            <form className="ops-form ops-form--lookup" onSubmit={loadDailyContents}>
              <label>目标用户 ID<input value={dailyTargetUserId} onChange={(event) => setDailyTargetUserId(event.target.value)} placeholder="person_user" /></label>
              <label>日期<input type="date" value={dailyDate} onChange={(event) => setDailyDate(event.target.value)} /></label>
              <Pressable className="secondary-button" type="submit" disabled={busy}>读取当前配置</Pressable>
            </form>
            <form className="ops-form" onSubmit={saveDaily}>
              <label>内容对象数组<textarea className="ops-content-editor" value={dailyContents} onChange={(event) => setDailyContents(event.target.value)} spellCheck={false} /></label>
              <Pressable className="primary-button" type="submit" disabled={busy || !dailyTargetUserId.trim()}>保存每日内容</Pressable>
            </form>
          </section>
        )}

        {view === "trace" && (
          <section className="ops-panel">
            <div className="ops-panel__heading"><div><span>TRACE EXPLORER</span><h2>查找一条完整链路</h2></div></div>
            <form className="ops-form ops-form--trace" onSubmit={searchTrace}>
              <label>Session ID<input value={traceSessionId} onChange={(event) => setTraceSessionId(event.target.value)} placeholder="session_..." /></label>
              <label>Record ID<input value={traceRecordId} onChange={(event) => setTraceRecordId(event.target.value)} placeholder="record_..." /></label>
              <label>Third Session ID<input value={traceThirdSessionId} onChange={(event) => setTraceThirdSessionId(event.target.value)} placeholder="sess_..." /></label>
              <Pressable className="primary-button" type="submit" disabled={busy}><Search size={16} />查询链路</Pressable>
            </form>
            <JsonPanel title="追踪信息" data={trace} />
          </section>
        )}
      </main>
    </section>
  );
}
