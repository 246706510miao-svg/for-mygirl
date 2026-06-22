import { FormEvent, useEffect, useState } from "react";
import { saveRecordComment } from "../features/comment/api";
import { addReward, checkIn, fetchPointSummary, fetchRedemptions, fetchRewards, redeemReward } from "../features/points/api";
import { confirmRecordDraft, createRecordSession, fetchBoundUserRecentRecords, fetchRecordHome, sendRecordMessage } from "../features/record/api";
import { fetchIdentityContext, switchViewRole } from "../features/relationship/api";
import { GlassScreen } from "../components/layout/GlassScreen";
import { MobileAppShell } from "../components/layout/MobileAppShell";
import { EmptyState } from "../components/ui/EmptyState";
import { useToast } from "../components/ui/useToast";
import { celebrate } from "../components/motion/confetti";
import { HomeScreen } from "../pages/HomeScreen";
import { RoleScreen } from "../pages/RoleScreen";
import { ChatScreen } from "../pages/ChatScreen";
import { RecordsScreen } from "../pages/RecordsScreen";
import { AdminRewardsScreen } from "../pages/AdminRewardsScreen";
import { AdminRecordsScreen } from "../pages/AdminRecordsScreen";
import type { ClientRole } from "../shared/api/client";
import type { IdentityContext, PointSummary, RecordDisplay, RecordDraft, RecordSession, RewardItem, RewardRedemption, UserHome, ViewRole } from "../shared/types/api";
import type { FieldKey } from "../components/records/recordFields";

type Screen = "home" | "profile" | "chat" | "userRecent" | "adminRewards" | "adminRecent";

interface MobileSnapshot {
  context: IdentityContext;
  home: UserHome;
  points: PointSummary;
  rewards: RewardItem[];
  redemptions: RewardRedemption[];
  userRecords: RecordDisplay[];
  adminRecords: RecordDisplay[];
}

interface MobileWorkspaceProps {
  role: ClientRole;
}

// 这个函数提取可展示的错误信息。
function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "操作失败";
}

// 这个组件编排手机端用户视角和绑定管理员视角。
export function MobileWorkspace({ role }: MobileWorkspaceProps) {
  const toast = useToast();
  const [screen, setScreen] = useState<Screen>("home");
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
  const [loading, setLoading] = useState(true);
  const [busyLabel, setBusyLabel] = useState("");
  const [status, setStatus] = useState("");

  const isBoundAdmin = context?.currentViewRole === "BOUND_ADMIN";
  const canSwitchToBoundAdmin = Boolean(context?.binding.active);

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
          setScreen("home");
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
    const [nextContext, recordData, nextPoints, nextRewards, nextRedemptions] = await Promise.all([
      fetchIdentityContext(nextRole),
      fetchRecordHome(nextRole),
      fetchPointSummary(nextRole),
      fetchRewards(nextRole),
      fetchRedemptions(nextRole)
    ]);
    const nextAdminRecords = nextContext.currentViewRole === "BOUND_ADMIN" ? await fetchBoundUserRecentRecords(nextRole) : [];
    return {
      context: nextContext,
      home: recordData.home,
      points: nextPoints,
      rewards: nextRewards.items,
      redemptions: nextRedemptions.items,
      userRecords: recordData.records,
      adminRecords: nextAdminRecords
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
  }

  // 这个函数刷新手机端上下文和当前视角数据。
  async function loadMobileData(nextRole = role) {
    applyMobileSnapshot(await readMobileSnapshot(nextRole));
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

  // 这个函数切换用户视角和绑定管理员视角。
  function toggleViewRole() {
    void runAction("切换视角中", async () => {
      if (!isBoundAdmin && !canSwitchToBoundAdmin) {
        throw new Error("当前账号没有绑定对象");
      }
      const nextView: ViewRole = isBoundAdmin ? "USER" : "BOUND_ADMIN";
      await switchViewRole(role, nextView);
      await loadMobileData(role);
      setScreen("home");
      toast.success(nextView === "BOUND_ADMIN" ? "已切换为绑定管理员视角" : "已切换为用户视角");
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

  // 这个函数发送对话输入并展示草稿。
  function sendChat(event: FormEvent) {
    event.preventDefault();
    const content = chatInput.trim();
    if (!content) {
      return;
    }
    void runAction("发送中", async () => {
      let current = session;
      if (!current) {
        current = await createRecordSession(role, new Date().toISOString().slice(0, 10));
        setSession(current);
      }
      const result = await sendRecordMessage(role, current.id, content);
      setSession(result.session);
      setDraft(result.draft);
      setChatMessages((items) => [...items, `我：${content}`, "AI：我整理了一版草稿，你可以确认或继续修改。"]);
      setChatInput("");
      toast.success("草稿已生成");
    });
  }

  // 这个函数确认当前草稿并刷新最近记录。
  function confirmDraft() {
    void runAction("确认中", async () => {
      if (!session || !draft) {
        return;
      }
      await confirmRecordDraft(role, session.id, draft.id);
      setDraft(null);
      setSession(null);
      setChatMessages((items) => [...items, "系统：记录已保存。"]);
      await loadMobileData(role);
      celebrate();
      toast.success("记录已保存");
    });
  }

  // 这个函数添加绑定用户可兑换奖品。
  function submitReward(title: string, cost: number) {
    return runAction("添加奖品中", async () => {
      await addReward(role, title, cost);
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
    setChatInput(draft.draft.summary || draft.previewText);
    toast.info("可以继续发送补充说明");
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

  return (
    <>
      {screen === "home" && (
        <HomeScreen
          context={context}
          home={home}
          points={points}
          isBoundAdmin={Boolean(isBoundAdmin)}
          busy={busy}
          onProfile={() => setScreen("profile")}
          onCheckIn={doCheckIn}
          onChat={() => setScreen("chat")}
          onUserRecent={() => setScreen("userRecent")}
          onAdminRewards={() => setScreen("adminRewards")}
          onAdminRecent={() => setScreen("adminRecent")}
        />
      )}
      {screen === "profile" && (
        <RoleScreen
          context={context}
          points={points}
          rewards={rewards}
          isBoundAdmin={Boolean(isBoundAdmin)}
          canSwitchToBoundAdmin={canSwitchToBoundAdmin}
          busy={busy}
          onBack={() => setScreen("home")}
          onToggleRole={toggleViewRole}
          onRedeem={redeem}
        />
      )}
      {screen === "chat" && (
        <ChatScreen
          messages={chatMessages}
          input={chatInput}
          draft={draft}
          busy={busy}
          onBack={() => setScreen("home")}
          onInputChange={setChatInput}
          onSend={sendChat}
          onConfirmDraft={confirmDraft}
          onEditDraft={editDraft}
          onVoice={() => toast.info("语音入口暂未接入")}
        />
      )}
      {screen === "userRecent" && (
        <RecordsScreen title="Records" records={userRecords} selectedFields={selectedFields} onFieldsChange={setSelectedFields} onBack={() => setScreen("home")} />
      )}
      {screen === "adminRewards" && (
        <AdminRewardsScreen points={points} rewards={rewards} redemptions={redemptions} busy={busy} onBack={() => setScreen("home")} onAddReward={submitReward} />
      )}
      {screen === "adminRecent" && (
        <AdminRecordsScreen records={adminRecords} busy={busy} onBack={() => setScreen("home")} onSaveComment={submitComment} />
      )}
      {busyLabel && <div className="action-status">{busyLabel}</div>}
    </>
  );
}
