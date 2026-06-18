import { useEffect, useState } from "react";
import { apiRequest, login } from "../../shared/api/client";
import type { PageResult, RecordDisplay, RecordDraft, RecordSession, SendMessageResult, UserHome } from "../../shared/types/api";

// 这个组件承载用户端 iPhone 优先页面。
export function UserWorkspace() {
  const [home, setHome] = useState<UserHome | null>(null);
  const [records, setRecords] = useState<RecordDisplay[]>([]);
  const [session, setSession] = useState<RecordSession | null>(null);
  const [draft, setDraft] = useState<RecordDraft | null>(null);
  const [input, setInput] = useState("今天完成了晨间拉伸，也按时吃了早餐。");
  const [status, setStatus] = useState("");

  useEffect(() => {
    void bootstrapUser();
  }, []);

  // 这个函数初始化用户端 token 和首页数据。
  async function bootstrapUser() {
    await login("user");
    const homeData = await apiRequest<UserHome>("/api/user/home", { role: "user" });
    const recordData = await apiRequest<PageResult<RecordDisplay>>("/api/user/records?page=1&pageSize=10", { role: "user" });
    setHome(homeData);
    setRecords(recordData.items);
  }

  // 这个函数创建记录会话。
  async function startSession() {
    const created = await apiRequest<RecordSession>("/api/record-sessions", {
      method: "POST",
      role: "user",
      body: JSON.stringify({ recordDate: new Date().toISOString().slice(0, 10), source: "user_home" })
    });
    setSession(created);
    setDraft(null);
    setStatus("会话已创建");
  }

  // 这个函数发送文本并展示草稿。
  async function sendMessage() {
    let current = session;
    if (!current) {
      current = await apiRequest<RecordSession>("/api/record-sessions", {
        method: "POST",
        role: "user",
        body: JSON.stringify({ recordDate: new Date().toISOString().slice(0, 10), source: "user_home" })
      });
    }
    setSession(current);
    const result = await apiRequest<SendMessageResult>(`/api/record-sessions/${current.id}/messages`, {
      method: "POST",
      role: "user",
      body: JSON.stringify({ clientMessageId: `cmid_${Date.now()}`, content: input })
    });
    setSession(result.session);
    setDraft(result.draft);
    setStatus("草稿已生成");
  }

  // 这个函数确认当前草稿写入。
  async function confirmDraft() {
    if (!session || !draft) {
      return;
    }
    const result = await apiRequest<Record<string, unknown>>(`/api/record-sessions/${session.id}/confirm`, {
      method: "POST",
      role: "user",
      body: JSON.stringify({ clientConfirmId: `cfid_${Date.now()}`, draftId: draft.id })
    });
    setStatus(`确认完成：${JSON.stringify(result.record ?? {})}`);
    const recordData = await apiRequest<PageResult<RecordDisplay>>("/api/user/records?page=1&pageSize=10", { role: "user" });
    setRecords(recordData.items);
  }

  return (
    <section className="user-shell">
      <div className="phone">
        <header className="mobile-hero">
          <p>{home?.date || new Date().toISOString().slice(0, 10)}</p>
          <h1>{home?.homeContent.mainText || "今天也认真照顾自己"}</h1>
          <span>{home?.homeContent.subText || "记录一点完成过的事。"}</span>
        </header>

        <div className="actions">
          <button onClick={startSession}>开始记录</button>
          <button onClick={bootstrapUser}>刷新记录</button>
        </div>

        <section className="panel">
          <h2>{home?.recordGuide.title || "今日记录引导"}</h2>
          <p>{home?.recordGuide.items?.join(" / ")}</p>
          <textarea value={input} onChange={(event) => setInput(event.target.value)} />
          <button onClick={sendMessage}>发送</button>
        </section>

        {draft && (
          <section className="panel draft">
            <p>v{draft.versionNo} · {draft.status}</p>
            <h2>{draft.draft.title || "记录草稿"}</h2>
            <p>{draft.previewText}</p>
            <div className="meta">评分 {draft.draft.score ?? "-"} · {(draft.draft.tags || []).join(" / ")}</div>
            <button onClick={confirmDraft}>确认写入</button>
          </section>
        )}

        <section className="panel">
          <h2>最近记录</h2>
          {records.map((item) => (
            <article className="record" key={item.recordId}>
              <b>{item.title}</b>
              <p>{item.summary}</p>
              <span>{item.displayStatus} · {item.score ?? "-"} 分</span>
            </article>
          ))}
        </section>

        <p className="status">{status}</p>
      </div>
    </section>
  );
}
