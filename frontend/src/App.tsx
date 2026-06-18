import { FormEvent, useState } from "react";
import { saveRecordComment } from "./features/comment/api";
import { OpsWorkspace } from "./features/ops/OpsWorkspace";
import { addReward, checkIn, fetchPointSummary, fetchRedemptions, fetchRewards, redeemReward } from "./features/points/api";
import { confirmRecordDraft, createRecordSession, fetchBoundUserRecentRecords, fetchRecentRecords, fetchRecordHome, sendRecordMessage } from "./features/record/api";
import { fetchIdentityContext, switchViewRole } from "./features/relationship/api";
import { loginWithCredentials, type ClientRole } from "./shared/api/client";
import type { IdentityContext, PointSummary, RecordDisplay, RecordDraft, RecordSession, RewardItem, RewardRedemption, UserHome, ViewRole } from "./shared/types/api";
import "./styles.css";

type Screen = "login" | "home" | "profile" | "chat" | "userRecent" | "adminRewards" | "adminRecent" | "ops";
type FieldKey = "recordDate" | "summary" | "score" | "displayStatus";

const fieldLabels: Record<FieldKey, string> = {
  recordDate: "日期",
  summary: "内容",
  score: "打分",
  displayStatus: "状态"
};

// 这个组件提供登录驱动的手机端和独立后台入口。
export default function App() {
  const [screen, setScreen] = useState<Screen>("login");
  const [role, setRole] = useState<ClientRole>("user");
  const [loginName, setLoginName] = useState("user");
  const [password, setPassword] = useState("dev");
  const [captcha, setCaptcha] = useState("1234");
  const [context, setContext] = useState<IdentityContext | null>(null);
  const [home, setHome] = useState<UserHome | null>(null);
  const [points, setPoints] = useState<PointSummary | null>(null);
  const [rewards, setRewards] = useState<RewardItem[]>([]);
  const [redemptions, setRedemptions] = useState<RewardRedemption[]>([]);
  const [userRecords, setUserRecords] = useState<RecordDisplay[]>([]);
  const [adminRecords, setAdminRecords] = useState<RecordDisplay[]>([]);
  const [selectedFields, setSelectedFields] = useState<FieldKey[]>(["recordDate", "summary", "score"]);
  const [session, setSession] = useState<RecordSession | null>(null);
  const [draft, setDraft] = useState<RecordDraft | null>(null);
  const [chatMessages, setChatMessages] = useState<string[]>([]);
  const [chatInput, setChatInput] = useState("今天完成了晨间拉伸，也按时吃了早餐。");
  const [rewardName, setRewardName] = useState("");
  const [rewardCost, setRewardCost] = useState("20");
  const [status, setStatus] = useState("");

  const isBoundAdmin = context?.currentViewRole === "BOUND_ADMIN";

  // 这个函数登录并按角色进入手机端或后台端。
  async function submitLogin(event: FormEvent) {
    event.preventDefault();
    setStatus("");
    try {
      const result = await loginWithCredentials(loginName, password);
      setRole(result.role);
      if (result.auth.person.role === "OPS_ADMIN" || result.auth.person.role === "ADMIN") {
        setScreen("ops");
        return;
      }
      await loadMobileData(result.role);
      setScreen("home");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "登录失败");
    }
  }

  // 这个函数刷新手机端上下文和当前视角数据。
  async function loadMobileData(nextRole = role) {
    const nextContext = await fetchIdentityContext(nextRole);
    const [{ home: nextHome, records }, nextPoints, nextRewards, nextRedemptions] = await Promise.all([
      fetchRecordHome(nextRole),
      fetchPointSummary(nextRole),
      fetchRewards(nextRole),
      fetchRedemptions(nextRole)
    ]);
    setContext(nextContext);
    setHome(nextHome);
    setPoints(nextPoints);
    setRewards(nextRewards.items);
    setRedemptions(nextRedemptions.items);
    setUserRecords(records);
    if (nextContext.currentViewRole === "BOUND_ADMIN") {
      setAdminRecords(await fetchBoundUserRecentRecords(nextRole));
    } else {
      setAdminRecords([]);
    }
  }

  // 这个函数切换用户视角和绑定管理员视角。
  async function toggleViewRole() {
    const nextView: ViewRole = isBoundAdmin ? "USER" : "BOUND_ADMIN";
    await switchViewRole(role, nextView);
    await loadMobileData(role);
    setScreen("home");
    setStatus(nextView === "BOUND_ADMIN" ? "已切换为绑定管理员视角" : "已切换为用户视角");
  }

  // 这个函数执行签到并刷新积分。
  async function doCheckIn() {
    const result = await checkIn(role);
    await loadMobileData(role);
    setStatus(result.addedPoints > 0 ? "+10 积分" : "今天已经签到");
  }

  // 这个函数发送对话输入并展示草稿。
  async function sendChat(event: FormEvent) {
    event.preventDefault();
    if (!chatInput.trim()) {
      return;
    }
    let current = session;
    if (!current) {
      current = await createRecordSession(role, new Date().toISOString().slice(0, 10));
      setSession(current);
    }
    const result = await sendRecordMessage(role, current.id, chatInput.trim());
    setSession(result.session);
    setDraft(result.draft);
    setChatMessages((items) => [...items, `我：${chatInput.trim()}`, "AI：我整理了一版草稿，你可以确认或继续修改。"]);
    setChatInput("");
  }

  // 这个函数确认当前草稿并刷新最近记录。
  async function confirmDraft() {
    if (!session || !draft) {
      return;
    }
    await confirmRecordDraft(role, session.id, draft.id);
    setDraft(null);
    setSession(null);
    setChatMessages((items) => [...items, "系统：记录已保存。"]);
    setUserRecords(await fetchRecentRecords(role));
    setStatus("记录已保存");
  }

  // 这个函数添加绑定用户可兑换奖品。
  async function submitReward(event: FormEvent) {
    event.preventDefault();
    const cost = Number(rewardCost);
    if (!rewardName.trim() || !Number.isFinite(cost) || cost < 1) {
      setStatus("添加失败：请补全奖品和积分");
      return;
    }
    await addReward(role, rewardName.trim(), cost);
    setRewardName("");
    setRewardCost("20");
    await loadMobileData(role);
    setStatus("奖品添加成功");
  }

  // 这个函数兑换奖品并刷新兑换记录。
  async function redeem(rewardId: string) {
    try {
      await redeemReward(role, rewardId);
      await loadMobileData(role);
      setStatus("兑换成功，奖品已从列表移除");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "兑换失败");
    }
  }

  // 这个函数保存绑定管理员对记录的评论和打分。
  async function submitComment(event: FormEvent<HTMLFormElement>, recordId: string) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const content = String(data.get("comment") || "").trim();
    const score = Number(data.get("score"));
    if (!content || !Number.isFinite(score)) {
      setStatus("保存失败：评论和打分不能为空");
      return;
    }
    await saveRecordComment(role, recordId, content, score);
    setAdminRecords(await fetchBoundUserRecentRecords(role));
    setStatus("评论和打分已保存");
  }

  if (screen === "ops") {
    return <OpsWorkspace />;
  }

  return (
    <main className="mobile-app">
      {screen === "login" && (
        <section className="login-screen">
          <form className="login-panel" onSubmit={submitLogin}>
            <h1>For My Girl</h1>
            <label>
              账号
              <input value={loginName} onChange={(event) => setLoginName(event.target.value)} placeholder="user / partner / admin" />
            </label>
            <label>
              密码
              <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
            </label>
            <label>
              验证码
              <span className="captcha-row">
                <input value={captcha} onChange={(event) => setCaptcha(event.target.value)} />
                <button type="button" onClick={() => setCaptcha(String(Math.floor(1000 + Math.random() * 9000)))}>{captcha}</button>
              </span>
            </label>
            <button type="submit">进入</button>
          </form>
        </section>
      )}

      {screen === "home" && context && (
        <section className="home-screen">
          <button className="avatar-button" onClick={() => setScreen("profile")} aria-label="用户界面">{context.person.displayName.slice(0, 1)}</button>
          <span className="role-pill">{isBoundAdmin ? "管理员视角" : "用户视角"}</span>
          <section className="checkin-widget">
            <p>{home?.homeContent.subText || "把完成过的小事写下来，慢慢看到自己的节奏。"}</p>
            <strong>{points?.currentUser.balance ?? 0}</strong>
            <button onClick={doCheckIn}>{points?.currentUser.checkedInToday ? "已签到" : "签到"}</button>
          </section>
          <nav className="dock">
            {isBoundAdmin ? (
              <>
                <button onClick={() => setScreen("adminRewards")} aria-label="积分奖品">☆</button>
                <button onClick={() => setScreen("adminRecent")} aria-label="绑定用户最近">☰</button>
              </>
            ) : (
              <>
                <button onClick={() => setScreen("chat")} aria-label="对话">✎</button>
                <button onClick={() => setScreen("userRecent")} aria-label="最近">☰</button>
              </>
            )}
          </nav>
        </section>
      )}

      {screen === "profile" && context && (
        <section className="glass-screen">
          <button className="back-button" onClick={() => setScreen("home")} aria-label="返回">×</button>
          <button className="identity-block" onClick={toggleViewRole}>
            <span>{isBoundAdmin ? "TA" : context.person.displayName.slice(0, 1)}</span>
            <b>{isBoundAdmin ? "TA 的管理页" : context.person.displayName}</b>
            <small>{isBoundAdmin ? "管理员视角 · 点击切换" : "用户视角 · 点击切换"}</small>
          </button>
          <section className="metric-line">
            <span>{isBoundAdmin ? "TA 的积分" : "我的积分"}</span>
            <strong>{points?.viewOwner.balance ?? 0}</strong>
          </section>
          <RewardList rewards={rewards} canRedeem={!isBoundAdmin} onRedeem={redeem} />
        </section>
      )}

      {screen === "chat" && (
        <section className="glass-screen chat-screen">
          <Header title="对话" onBack={() => setScreen("home")} />
          <div className="chat-history">
            {chatMessages.map((item, index) => <article key={`${item}-${index}`} className={item.startsWith("我：") ? "message me" : "message"}>{item}</article>)}
            {draft && <article className="draft-panel"><b>{draft.draft.title || "记录草稿"}</b><p>{draft.previewText}</p><span>{draft.draft.score ?? "-"} 分</span><button onClick={confirmDraft}>确认写入</button></article>}
          </div>
          <form className="composer" onSubmit={sendChat}>
            <button type="button" onClick={() => setStatus("语音入口暂未接入")}>🎙</button>
            <input value={chatInput} onChange={(event) => setChatInput(event.target.value)} placeholder="写下今天的记录" />
            <button type="submit">发送</button>
          </form>
        </section>
      )}

      {screen === "userRecent" && (
        <section className="glass-screen">
          <Header title="最近记录" onBack={() => setScreen("home")} />
          <FieldSelector selected={selectedFields} onChange={setSelectedFields} />
          <RecordList records={userRecords} fields={selectedFields} />
        </section>
      )}

      {screen === "adminRewards" && (
        <section className="glass-screen">
          <Header title="积分奖品" onBack={() => setScreen("home")} />
          <section className="metric-line"><span>绑定用户积分</span><strong>{points?.viewOwner.balance ?? 0}</strong></section>
          <form className="reward-form" onSubmit={submitReward}>
            <input value={rewardName} onChange={(event) => setRewardName(event.target.value)} placeholder="奖品名称" />
            <input value={rewardCost} onChange={(event) => setRewardCost(event.target.value)} inputMode="numeric" placeholder="所需积分" />
            <button type="submit">添加</button>
          </form>
          <RewardList rewards={rewards} canRedeem={false} onRedeem={redeem} />
          <section className="redemption-list">
            <h2>兑换提示</h2>
            {redemptions.map((item) => <p key={item.id}>{item.title} 已被兑换 · {item.costPoints} 分</p>)}
            {redemptions.length === 0 && <p>暂无兑换记录</p>}
          </section>
        </section>
      )}

      {screen === "adminRecent" && (
        <section className="glass-screen">
          <Header title="绑定用户最近" onBack={() => setScreen("home")} />
          {adminRecords.map((record) => (
            <article className="admin-record" key={record.recordId}>
              <div className="admin-fields">
                <div><span>时间</span><b>{record.recordDate || "-"}</b></div>
                <div><span>内容</span><b>{record.summary}</b></div>
                <div><span>打分</span><b>{record.managerScore ?? record.score ?? "-"}</b></div>
              </div>
              <form className="inline-form" onSubmit={(event) => submitComment(event, record.recordId)}>
                <input name="comment" defaultValue={record.managerComment || ""} placeholder="评论" />
                <input name="score" defaultValue={String(record.managerScore ?? record.score ?? 80)} inputMode="numeric" placeholder="打分" />
                <button type="submit">保存</button>
              </form>
            </article>
          ))}
        </section>
      )}

      {status && <div className="toast">{status}</div>}
    </main>
  );
}

function Header({ title, onBack }: { title: string; onBack: () => void }) {
  return <header className="screen-header"><button onClick={onBack} aria-label="返回">‹</button><h1>{title}</h1></header>;
}

function FieldSelector({ selected, onChange }: { selected: FieldKey[]; onChange: (value: FieldKey[]) => void }) {
  const choices = Object.keys(fieldLabels) as FieldKey[];
  return (
    <div className="field-selector">
      {selected.map((field, index) => (
        <select key={`${field}-${index}`} value={field} onChange={(event) => {
          const next = [...selected];
          next[index] = event.target.value as FieldKey;
          onChange(next);
        }}>
          {choices.map((item) => <option key={item} value={item}>{fieldLabels[item]}</option>)}
        </select>
      ))}
    </div>
  );
}

function RecordList({ records, fields }: { records: RecordDisplay[]; fields: FieldKey[] }) {
  return (
    <section className="record-list">
      {records.map((record) => (
        <article className="record-item" key={record.recordId}>
          <div className="record-fields">
            {fields.map((field) => <div key={field}><span>{fieldLabels[field]}</span><b>{String(record[field] ?? "-")}</b></div>)}
          </div>
          <p><b>管理员评论：</b>{record.managerComment || "暂无评论"}</p>
        </article>
      ))}
    </section>
  );
}

function RewardList({ rewards, canRedeem, onRedeem }: { rewards: RewardItem[]; canRedeem: boolean; onRedeem: (rewardId: string) => void }) {
  return (
    <section className="reward-list">
      {rewards.map((reward) => (
        <article className="reward-item" key={reward.id}>
          <div><h2>{reward.title}</h2><p>{reward.description || "可兑换奖品"}</p></div>
          <strong>{reward.costPoints} 分</strong>
          {canRedeem && <button disabled={!reward.redeemable} onClick={() => onRedeem(reward.id)}>{reward.redeemable ? "兑换" : "积分不足"}</button>}
        </article>
      ))}
      {rewards.length === 0 && <p>暂无可兑换奖品</p>}
    </section>
  );
}
