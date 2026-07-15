import { FormEvent, useEffect, useRef, useState } from "react";
import { saveRecordComment } from "../features/comment/api";
import { createFeishuTable, fetchFeishuAccount, fetchFeishuTables, saveFeishuAccount, setDefaultFeishuTable, testFeishuTable, updateFeishuTable, type SaveFeishuAccountPayload, type SaveFeishuTablePayload } from "../features/feishu/api";
import { addReward, checkIn, fetchPointSummary, fetchRedemptions, fetchRewards, redeemReward } from "../features/points/api";
import { cancelRecordSession, confirmRecordDraft, createRecordSession, fetchBoundUserRecentRecords, fetchRecordHome, fetchRecordSession, resumeRecordConfirm, sendRecordMessage } from "../features/record/api";
import { acceptBindingInvitation, cancelBindingInvitation, fetchIdentityContext, inviteBindingUser, rejectBindingInvitation, switchViewRole } from "../features/relationship/api";
import { GlassScreen } from "../components/layout/GlassScreen";
import { MobileAppShell, type MobileTabItem } from "../components/layout/MobileAppShell";
import { EmptyState } from "../components/ui/EmptyState";
import { useToast } from "../components/ui/useToast";
import { celebrate } from "../components/motion/confetti";
import { HomeScreen } from "../pages/HomeScreen";
import { RoleScreen } from "../pages/RoleScreen";
import { ChatScreen } from "../pages/ChatScreen";
import { RecordsScreen } from "../pages/RecordsScreen";
import { RewardsScreen } from "../pages/RewardsScreen";
import { CareScreen } from "../pages/CareScreen";
import { ApiRequestError, newClientId, type ClientRole } from "../shared/api/client";
import type { ConfirmRecordResult, FeishuAccount, FeishuTableConfig, IdentityContext, PendingThirdConfirmation, PointSummary, RecordDisplay, RecordDraft, RecordSession, RecordSessionDetail, RecordWorkflowTask, RewardItem, RewardRedemption, ThirdInteractionResponse, UserHome } from "../shared/types/api";
import type { FieldKey } from "../components/records/recordFields";
import { recordConversationState } from "./recordSessionState";
import { appendOptimisticTurn, conversationMessagesFromDetail, replacePendingWithError, replacePendingWithMessage, type ChatMessageItem } from "./chatConversation";

type Screen = "home" | "profile" | "chat" | "userRecent" | "rewards" | "care";

interface MobileSnapshot {
  context: IdentityContext;
  home: UserHome;
  points: PointSummary;
  rewards: RewardItem[];
  redemptions: RewardRedemption[];
  userRecords: RecordDisplay[];
  adminRecords: RecordDisplay[];
  feishuAccount: FeishuAccount;
  feishuTables: FeishuTableConfig[];
}

interface MobileWorkspaceProps {
  role: ClientRole;
  onLogout: () => void;
}

// 这个函数提取可展示的错误信息。
function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "操作失败";
}

// 这个函数从后端 message DTO 中取可展示文本。
function messageContent(message: { content?: unknown } | undefined, fallback: string) {
  const content = message?.content;
  return typeof content === "string" && content.trim() ? content : fallback;
}

// 这个函数等待下一次会话轮询。
function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

// 这个函数判断 workflow task 是否仍需要继续轮询。
function isProcessingTask(task?: RecordWorkflowTask | null) {
  return Boolean(task && ["submitted", "running"].includes(task.status));
}

// 这个函数在刷新飞书配置后保持当前选择稳定。
function resolveSelectedFeishuTable(current: string | null | undefined, tables: FeishuTableConfig[]) {
  if (current && tables.some((table) => table.id === current)) {
    return current;
  }
  return tables.find((table) => table.isDefault)?.id ?? tables[0]?.id ?? null;
}

// 这个组件编排手机端用户视角和绑定管理员视角。
export function MobileWorkspace({ role, onLogout }: MobileWorkspaceProps) {
  const toast = useToast();
  const [screen, setScreen] = useState<Screen>("home");
  const [context, setContext] = useState<IdentityContext | null>(null);
  const [home, setHome] = useState<UserHome | null>(null);
  const [points, setPoints] = useState<PointSummary | null>(null);
  const [rewards, setRewards] = useState<RewardItem[]>([]);
  const [redemptions, setRedemptions] = useState<RewardRedemption[]>([]);
  const [userRecords, setUserRecords] = useState<RecordDisplay[]>([]);
  const [adminRecords, setAdminRecords] = useState<RecordDisplay[]>([]);
  const [feishuAccount, setFeishuAccount] = useState<FeishuAccount | null>(null);
  const [feishuTables, setFeishuTables] = useState<FeishuTableConfig[]>([]);
  const [selectedFeishuTableId, setSelectedFeishuTableId] = useState<string | null>(null);
  const [selectedFields, setSelectedFields] = useState<FieldKey[]>(["recordDate", "summary", "score"]);
  const [session, setSession] = useState<RecordSession | null>(null);
  const [draft, setDraft] = useState<RecordDraft | null>(null);
  const [pendingConfirmation, setPendingConfirmation] = useState<PendingThirdConfirmation | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessageItem[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyLabel, setBusyLabel] = useState("");
  const [status, setStatus] = useState("");
  const chatActionInFlight = useRef(false);

  const isBoundAdmin = context?.currentViewRole === "BOUND_ADMIN";
  const canEnterCare = Boolean(context?.binding.active);

  useEffect(() => {
    let ignored = false;

    // 这个函数加载当前登录角色的手机端首页数据。
    async function bootstrap() {
      setLoading(true);
      setStatus("");
      try {
        const snapshot = await readMobileSnapshot(role);
        if (!ignored) {
          applyMobileSnapshot(snapshot);
          setScreen(snapshot.context.currentViewRole === "BOUND_ADMIN" ? "care" : "home");
        }
      } catch (error) {
        if (!ignored) {
          setStatus(errorMessage(error));
        }
      } finally {
        if (!ignored) {
          setLoading(false);
        }
      }
    }

    void bootstrap();
    return () => {
      ignored = true;
    };
  }, [role]);

  // 这个函数读取手机端当前视角需要的完整数据快照。
  async function readMobileSnapshot(nextRole: ClientRole): Promise<MobileSnapshot> {
    const [nextContext, recordData, nextPoints, nextRewards, nextRedemptions, nextFeishuAccount, nextFeishuTables] = await Promise.all([
      fetchIdentityContext(nextRole),
      fetchRecordHome(nextRole),
      fetchPointSummary(nextRole),
      fetchRewards(nextRole),
      fetchRedemptions(nextRole),
      fetchFeishuAccount(nextRole),
      fetchFeishuTables(nextRole)
    ]);
    const nextAdminRecords = nextContext.currentViewRole === "BOUND_ADMIN" ? await fetchBoundUserRecentRecords(nextRole) : [];
    return {
      context: nextContext,
      home: recordData.home,
      points: nextPoints,
      rewards: nextRewards.items,
      redemptions: nextRedemptions.items,
      userRecords: recordData.records,
      adminRecords: nextAdminRecords,
      feishuAccount: nextFeishuAccount,
      feishuTables: nextFeishuTables
    };
  }

  // 这个函数把接口快照同步到页面状态。
  function applyMobileSnapshot(snapshot: MobileSnapshot) {
    setContext(snapshot.context);
    setHome(snapshot.home);
    setPoints(snapshot.points);
    setRewards(snapshot.rewards);
    setRedemptions(snapshot.redemptions);
    setUserRecords(snapshot.userRecords);
    setAdminRecords(snapshot.adminRecords);
    setFeishuAccount(snapshot.feishuAccount);
    setFeishuTables(snapshot.feishuTables);
    setSelectedFeishuTableId((current) => resolveSelectedFeishuTable(current, snapshot.feishuTables));
  }

  // 这个函数刷新手机端上下文和当前视角数据。
  async function loadMobileData(nextRole = role) {
    applyMobileSnapshot(await readMobileSnapshot(nextRole));
  }

  async function loadFeishuData(nextSelectedId?: string) {
    const [nextAccount, nextTables] = await Promise.all([fetchFeishuAccount(role), fetchFeishuTables(role)]);
    setFeishuAccount(nextAccount);
    setFeishuTables(nextTables);
    setSelectedFeishuTableId(resolveSelectedFeishuTable(nextSelectedId ?? selectedFeishuTableId, nextTables));
  }

  // 这个函数统一包裹页面异步动作和错误提示。
  async function runAction(label: string, action: () => Promise<void>) {
    setBusyLabel(label);
    setStatus("");
    try {
      await action();
      return true;
    } catch (error) {
      toast.error(errorMessage(error));
      return false;
    } finally {
      setBusyLabel("");
    }
  }

  // 进入照顾者模式时才切换 BOUND_ADMIN 权限，普通首页始终属于本人。
  function enterCareMode() {
    void runAction("进入照顾者模式中", async () => {
      if (!canEnterCare) throw new Error("完成双向绑定后才能进入照顾者模式");
      if (!isBoundAdmin) await switchViewRole(role, "BOUND_ADMIN");
      await loadMobileData(role);
      setScreen("care");
      toast.success("已进入照顾者模式");
    });
  }

  // 对话请求使用同步锁避免重复提交；异常只在消息流中给出简短反馈。
  async function runChatAction(label: string, pendingId: string, sessionId: () => string | null, action: () => Promise<void>) {
    if (chatActionInFlight.current) {
      return false;
    }
    chatActionInFlight.current = true;
    setBusyLabel(label);
    setStatus("");
    try {
      await action();
      return true;
    } catch (error) {
      await recoverChatAction(error, pendingId, sessionId());
      return false;
    } finally {
      chatActionInFlight.current = false;
      setBusyLabel("");
    }
  }

  // 确认状态过期时刷新真实会话，其他异常则替换当前思考气泡。
  async function recoverChatAction(error: unknown, pendingId: string, sessionId: string | null) {
    const staleInteraction = error instanceof ApiRequestError
      && (error.status === 409 || error.code === "CONFLICT" || error.message.includes("confirmation_id") || error.message.includes("交互已发生变化"));
    if (sessionId) {
      try {
        const detail = await fetchRecordSession(role, sessionId);
        applyRecordSessionDetail(detail);
        if (detail.pendingConfirmation || isProcessingTask(detail.latestWorkflowTask)) {
          return;
        }
        const refreshedMessages = conversationMessagesFromDetail(detail);
        if (detail.record || detail.currentDraft || refreshedMessages[refreshedMessages.length - 1]?.type === "ai") {
          setChatMessages(refreshedMessages);
          return;
        }
        setChatMessages(replacePendingWithError(
          refreshedMessages,
          pendingId,
          staleInteraction ? "刚才的问题已经更新了，请继续看最新一条。" : "刚才没有顺利完成，请再试一次。"
        ));
        return;
      } catch {
        // 刷新也失败时，保留当前本地对话并给出可重试提示。
      }
    }
    setChatMessages((items) => replacePendingWithError(
      items,
      pendingId,
      staleInteraction ? "刚才的问题已经更新了，请再试一次。" : "刚才没有顺利完成，请再试一次。"
    ));
  }

  // 离开照顾者模式时恢复用户视角和用户自己的数据。
  function leaveCareMode() {
    void runAction("返回我的视角中", async () => {
      if (isBoundAdmin) await switchViewRole(role, "USER");
      await loadMobileData(role);
      setScreen("profile");
      toast.success("已回到我的视角");
    });
  }

  // 这个函数执行签到并刷新积分。
  function doCheckIn() {
    void runAction("签到中", async () => {
      const result = await checkIn(role);
      await loadMobileData(role);
      if (result.addedPoints > 0) {
        celebrate();
        toast.success(`+${result.addedPoints} 积分`);
      } else {
        toast.info("今天已经签到");
      }
    });
  }

  // 这个函数把会话详情同步回聊天页状态。
  function applyRecordSessionDetail(detail: RecordSessionDetail) {
    const state = recordConversationState(detail);
    setSession(state.session);
    setDraft(state.draft);
    setPendingConfirmation(state.pendingConfirmation);
    setChatMessages(conversationMessagesFromDetail(detail));
  }

  // 这个函数轮询会话，直到 third workflow 不再处于 submitted/running。
  async function waitForWorkflow(sessionId: string, pollAfterMs?: number) {
    let detail: RecordSessionDetail | null = null;
    await delay(pollAfterMs ?? 1500);
    for (let attempt = 0; attempt < 80; attempt += 1) {
      detail = await fetchRecordSession(role, sessionId);
      applyRecordSessionDetail(detail);
      if (!isProcessingTask(detail.latestWorkflowTask)) {
        return detail;
      }
      await delay(detail.pollAfterMs ?? 1500);
    }
    return detail;
  }

  // 这个函数根据轮询结果给出最终反馈。
  async function handleWorkflowOutcome(detail: RecordSessionDetail | null) {
    if (!detail) {
      return;
    }
    const task = detail.latestWorkflowTask;
    if (isProcessingTask(task)) {
      return;
    }
    if (detail.session.status === "confirmed" || detail.record) {
      setDraft(null);
      setPendingConfirmation(null);
      setSession(null);
      await loadMobileData(role);
      celebrate();
      return;
    }
    if (detail.pendingConfirmation) {
      return;
    }
    if (detail.currentDraft) {
      return;
    }
    if (task?.status === "failed") {
      return;
    }
    if (task?.status === "cancelled") {
      return;
    }
  }

  // 这个函数发送对话输入，并按 third 决策展示草稿、确认卡或普通回复。
  function sendChat(event: FormEvent) {
    event.preventDefault();
    const content = chatInput.trim();
    if (!content || chatActionInFlight.current) {
      return;
    }
    if (pendingConfirmation) {
      resolvePendingConfirmation(pendingConfirmation.interactionKind === "confirm" ? "modify" : "answer", content);
      return;
    }
    const turnId = newClientId("turn");
    let activeSessionId = session?.id ?? null;
    setChatInput("");
    setChatMessages((items) => appendOptimisticTurn(items, content, turnId));
    void runChatAction("发送中", turnId, () => activeSessionId, async () => {
      let current = session;
      if (!current) {
        current = await createRecordSession(role, new Date().toISOString().slice(0, 10), selectedFeishuTableId);
        setSession(current);
      }
      activeSessionId = current.id;
      const result = await sendRecordMessage(role, current.id, content);
      setSession(result.session);
      if (result.workflowStatus === "processing") {
        setDraft(null);
        setPendingConfirmation(null);
        const detail = await waitForWorkflow(result.session.id, result.pollAfterMs);
        await handleWorkflowOutcome(detail);
        return;
      }
      setDraft(result.draft ?? null);
      setPendingConfirmation(result.pendingConfirmation ?? null);
      const reply = result.pendingConfirmation
        ? result.pendingConfirmation.requestText || "请确认下一步操作。"
        : messageContent(result.aiMessage, result.draft ? "我整理了一版草稿，你可以确认或继续修改。" : "已经处理好了。");
      setChatMessages((items) => replacePendingWithMessage(items, turnId, reply));
    });
  }

  // 这个函数处理确认成功后的本地状态刷新。
  async function finishConfirm(result: ConfirmRecordResult, pendingId: string) {
    setDraft(null);
    setSession(null);
    setPendingConfirmation(null);
    setChatMessages((items) => replacePendingWithMessage(items, pendingId, messageContent(result.replyMessage, result.record ? "记录已保存。" : "已经处理好了。")));
    await loadMobileData(role);
    if (result.record) {
      celebrate();
    }
  }

  // 这个函数确认当前草稿并请求 third 生成最终写入确认。
  function confirmDraft() {
    if (!session || !draft || chatActionInFlight.current) {
      return;
    }
    const currentSession = session;
    const currentDraft = draft;
    const turnId = newClientId("turn");
    setChatMessages((items) => appendOptimisticTurn(items, "确认这份草稿", turnId));
    void runChatAction("确认中", turnId, () => currentSession.id, async () => {
      const result = await confirmRecordDraft(role, currentSession.id, currentDraft.id);
      setSession(result.session);
      if (result.workflowStatus === "processing") {
        const detail = await waitForWorkflow(result.session.id, result.pollAfterMs);
        await handleWorkflowOutcome(detail);
        return;
      }
      if (result.pendingConfirmation) {
        setPendingConfirmation(result.pendingConfirmation);
        setChatMessages((items) => replacePendingWithMessage(items, turnId, result.pendingConfirmation?.requestText || "请确认即将执行的内容。"));
        return;
      }
      await finishConfirm(result, turnId);
    });
  }

  // 这个函数回答或处理 third 当前等待中的交互。
  function resolvePendingConfirmation(response: ThirdInteractionResponse, content = "") {
    if (!session || !pendingConfirmation || chatActionInFlight.current) {
      return;
    }
    const currentSession = session;
    const currentConfirmation = pendingConfirmation;
    const userContent = content.trim() || (response === "approve" ? "确认执行" : response === "cancel" ? "暂不执行" : "");
    if (!userContent) {
      return;
    }
    const turnId = newClientId("turn");
    setChatInput("");
    setChatMessages((items) => appendOptimisticTurn(items, userContent, turnId));
    const actionText = response === "approve" ? "写入中" : response === "cancel" ? "取消中" : "思考中";
    void runChatAction(actionText, turnId, () => currentSession.id, async () => {
      const result = await resumeRecordConfirm(role, currentSession.id, currentConfirmation, response, content);
      setSession(result.session);
      if (response === "cancel") {
        setPendingConfirmation(null);
        setDraft(result.draft || draft);
        setChatMessages((items) => replacePendingWithMessage(items, turnId, messageContent(result.replyMessage, "已取消本次操作，可以继续修改。")));
        return;
      }
      if (result.workflowStatus === "processing") {
        setPendingConfirmation(null);
        const detail = await waitForWorkflow(result.session.id, result.pollAfterMs);
        await handleWorkflowOutcome(detail);
        return;
      }
      if (result.pendingConfirmation) {
        setPendingConfirmation(result.pendingConfirmation);
        setChatMessages((items) => replacePendingWithMessage(items, turnId, result.pendingConfirmation?.requestText || "还需要你确认下一步。"));
        return;
      }
      await finishConfirm(result, turnId);
    });
  }

  // 这个函数添加绑定用户可兑换奖品。
  function submitReward(title: string, description: string, cost: number) {
    return runAction("添加奖品中", async () => {
      await addReward(role, title, description, cost);
      await loadMobileData(role);
      celebrate();
      toast.success("奖品添加成功");
    });
  }

  // 这个函数兑换奖品并刷新兑换记录。
  function redeem(rewardId: string) {
    void runAction("兑换中", async () => {
      await redeemReward(role, rewardId);
      await loadMobileData(role);
      celebrate();
      toast.success("兑换成功，奖品已从列表移除");
    });
  }

  // 这个函数保存绑定管理员对记录的评论和打分。
  function submitComment(recordId: string, content: string, score: number) {
    return runAction("保存评论中", async () => {
      await saveRecordComment(role, recordId, content, score);
      await loadMobileData(role);
      toast.success("评论和打分已保存");
    });
  }

  // 这个函数把草稿内容放回输入栏，继续由对话修改。
  function editDraft() {
    if (!draft) {
      return;
    }
    setPendingConfirmation(null);
    setChatInput(draft.draft.summary || draft.previewText);
  }

  // 这个函数显式取消当前会话并清空本地对话状态。
  function cancelChatSession() {
    void runAction("取消会话中", async () => {
      if (session) {
        await cancelRecordSession(role, session.id);
      }
      setSession(null);
      setDraft(null);
      setPendingConfirmation(null);
      setChatMessages([]);
      setChatInput("");
      toast.info("本次记录已取消");
    });
  }

  function inviteBinding(loginName: string) {
    return runAction("发送绑定邀请中", async () => {
      if (!loginName.trim()) {
        throw new Error("请输入对方账号");
      }
      await inviteBindingUser(role, loginName);
      await loadMobileData(role);
      toast.success("绑定邀请已发送");
    });
  }

  function acceptBinding(bindingId: string) {
    void runAction("接受绑定中", async () => {
      await acceptBindingInvitation(role, bindingId);
      await loadMobileData(role);
      toast.success("已绑定用户");
    });
  }

  function rejectBinding(bindingId: string) {
    void runAction("拒绝绑定中", async () => {
      await rejectBindingInvitation(role, bindingId);
      await loadMobileData(role);
      toast.info("已拒绝绑定邀请");
    });
  }

  function cancelBinding(bindingId: string) {
    void runAction("取消邀请中", async () => {
      await cancelBindingInvitation(role, bindingId);
      await loadMobileData(role);
      toast.info("已取消绑定邀请");
    });
  }

  function selectFeishuTable(tableId: string) {
    if (session || draft || pendingConfirmation) {
      toast.info("当前会话已绑定飞书表");
      return;
    }
    setSelectedFeishuTableId(tableId);
  }

  function submitFeishuAccount(payload: SaveFeishuAccountPayload) {
    return runAction("保存飞书凭证中", async () => {
      await saveFeishuAccount(role, payload);
      await loadFeishuData();
      toast.success("飞书凭证已保存");
    });
  }

  function submitFeishuTable(payload: SaveFeishuTablePayload) {
    return runAction("添加飞书表中", async () => {
      const table = await createFeishuTable(role, payload);
      await loadFeishuData(table.id);
      toast.success("飞书表已添加");
    });
  }

  function saveCurrentFeishuTable(tableId: string, payload: SaveFeishuTablePayload) {
    return runAction("保存飞书表中", async () => {
      await updateFeishuTable(role, tableId, payload);
      await loadFeishuData(tableId);
      toast.success("飞书表已保存");
    });
  }

  function markDefaultFeishuTable(tableId: string) {
    return runAction("设置默认表中", async () => {
      await setDefaultFeishuTable(role, tableId);
      await loadFeishuData(tableId);
      toast.success("默认表已更新");
    });
  }

  function checkFeishuTable(tableId: string) {
    return runAction("测试飞书表中", async () => {
      const result = await testFeishuTable(role, tableId);
      await loadFeishuData(tableId);
      if (result.status === "ok") {
        toast.success(`连接正常，字段 ${result.fieldCount ?? 0} 个`);
      } else {
        throw new Error(result.message || "飞书表测试失败");
      }
    });
  }

  if (loading && !context) {
    return (
      <MobileAppShell>
        <GlassScreen>
          <EmptyState title="加载中..." />
        </GlassScreen>
      </MobileAppShell>
    );
  }

  if (!context) {
    return (
      <MobileAppShell>
        <GlassScreen>
          <EmptyState title={status || "加载失败"} />
        </GlassScreen>
      </MobileAppShell>
    );
  }

  const busy = Boolean(busyLabel);
  const userTabs: MobileTabItem[] = [
    { key: "chat", label: "记录", onSelect: () => setScreen("chat") },
    { key: "records", label: "日常", onSelect: () => setScreen("userRecent") },
    { key: "home", label: "首页", onSelect: () => setScreen("home") },
    { key: "rewards", label: "心意", onSelect: () => setScreen("rewards") },
    { key: "profile", label: "我的", onSelect: () => setScreen("profile") }
  ];

  return (
    <>
      {screen === "home" && (
        <HomeScreen
          context={context}
          home={home}
          points={points}
          busy={busy}
          role={role}
          tabs={userTabs}
          onProfile={() => setScreen("profile")}
          onCheckIn={doCheckIn}
          onChat={() => setScreen("chat")}
          onUserRecent={() => setScreen("userRecent")}
          onRewards={() => setScreen("rewards")}
        />
      )}
      {screen === "profile" && (
        <RoleScreen
          context={context}
          points={points}
          rewards={rewards}
          tabs={userTabs}
          canEnterCare={canEnterCare}
          busy={busy}
          onBack={() => setScreen("home")}
          onRewards={() => setScreen("rewards")}
          onEnterCare={enterCareMode}
          onInviteBinding={inviteBinding}
          onAcceptBindingInvitation={acceptBinding}
          onRejectBindingInvitation={rejectBinding}
          onCancelBindingInvitation={cancelBinding}
          onLogout={onLogout}
        />
      )}
      {screen === "chat" && (
        <ChatScreen
          messages={chatMessages}
          input={chatInput}
          draft={draft}
          pendingConfirmation={pendingConfirmation}
          feishuAccount={feishuAccount}
          feishuTables={feishuTables}
          selectedFeishuTableId={selectedFeishuTableId}
          feishuLocked={Boolean(session || draft || pendingConfirmation)}
          hasSession={Boolean(session)}
          tabs={userTabs}
          busy={busy}
          onBack={() => setScreen("home")}
          onInputChange={setChatInput}
          onSend={sendChat}
          onConfirmDraft={confirmDraft}
          onRespondConfirmation={resolvePendingConfirmation}
          onEditDraft={editDraft}
          onVoice={() => toast.info("语音入口暂未接入")}
          onCancelSession={cancelChatSession}
          onSelectFeishuTable={selectFeishuTable}
          onSaveFeishuAccount={submitFeishuAccount}
          onCreateFeishuTable={submitFeishuTable}
          onUpdateFeishuTable={saveCurrentFeishuTable}
          onSetDefaultFeishuTable={markDefaultFeishuTable}
          onTestFeishuTable={checkFeishuTable}
        />
      )}
      {screen === "userRecent" && (
        <RecordsScreen title="我们的日常" records={userRecords} selectedFields={selectedFields} onFieldsChange={setSelectedFields} onBack={() => setScreen("home")} tabs={userTabs} />
      )}
      {screen === "rewards" && (
        <RewardsScreen points={points} rewards={rewards} redemptions={redemptions} tabs={userTabs} busy={busy} onBack={() => setScreen("home")} onRedeem={redeem} />
      )}
      {screen === "care" && (
        <CareScreen points={points} records={adminRecords} rewards={rewards} redemptions={redemptions} busy={busy} onBack={leaveCareMode} onAddReward={submitReward} onSaveComment={submitComment} />
      )}
      {busyLabel && screen !== "chat" && <div className="action-status">{busyLabel}</div>}
    </>
  );
}
