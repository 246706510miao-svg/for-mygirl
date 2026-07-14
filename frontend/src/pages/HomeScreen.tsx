import { Gift, NotebookText, Sparkles } from "lucide-react";
import { MobileAppShell } from "../components/layout/MobileAppShell";
import type { MobileTabKey } from "../components/layout/MobileAppShell";
import { PageTransition } from "../components/motion/PageTransition";
import { Pressable } from "../components/ui/Pressable";
import { DailyFocusCard } from "../features/newsfocus/DailyFocusCard";
import type { IdentityContext, PointSummary, UserHome } from "../shared/types/api";
import type { ClientRole } from "../shared/api/client";

interface HomeScreenProps {
  context: IdentityContext;
  home: UserHome | null;
  points: PointSummary | null;
  isBoundAdmin: boolean;
  busy: boolean;
  role: ClientRole;
  onProfile: () => void;
  onCheckIn: () => void;
  onChat: () => void;
  onUserRecent: () => void;
  onAdminRewards: () => void;
  onAdminRecent: () => void;
}

// 这个页面是用户和绑定管理员共用的手机端首页。
export function HomeScreen({
  context,
  home,
  points,
  isBoundAdmin,
  busy,
  role,
  onProfile,
  onCheckIn,
  onChat,
  onUserRecent,
  onAdminRewards,
  onAdminRecent
}: HomeScreenProps) {
  const balance = isBoundAdmin ? points?.viewOwner.balance ?? 0 : points?.currentUser.balance ?? 0;
  const checkedIn = Boolean(points?.currentUser.checkedInToday);
  const tabs = isBoundAdmin
    ? [
        { key: "home" as MobileTabKey, label: "首页", onSelect: () => undefined },
        { key: "rewards" as MobileTabKey, label: "奖品", onSelect: onAdminRewards },
        { key: "records" as MobileTabKey, label: "记录", onSelect: onAdminRecent },
        { key: "profile" as MobileTabKey, label: "身份", onSelect: onProfile }
      ]
    : [
        { key: "home" as MobileTabKey, label: "首页", onSelect: () => undefined },
        { key: "chat" as MobileTabKey, label: "对话", onSelect: onChat },
        { key: "records" as MobileTabKey, label: "记录", onSelect: onUserRecent },
        { key: "profile" as MobileTabKey, label: "身份", onSelect: onProfile }
      ];

  return (
    <MobileAppShell activeTab="home" tabs={tabs}>
      <PageTransition className="home-screen" direction="none">
        <Pressable className="avatar-button" onClick={onProfile} aria-label="用户界面">
          {context.person.displayName.slice(0, 1)}
        </Pressable>
        <span className="role-pill">{isBoundAdmin ? "管理员视角" : "用户视角"}</span>
        <section className="home-card">
          <div className="home-card__eyebrow">
            <Sparkles size={18} />
            <span>{isBoundAdmin ? "Bound admin" : "Daily sign-in"}</span>
          </div>
          <h1>{isBoundAdmin ? "TA 的今日积分" : `晚上好，${context.person.displayName}`}</h1>
          <p>{home?.homeContent.subText || "把完成过的小事写下来，慢慢看到自己的节奏。"}</p>
          <strong>{balance}</strong>
          {isBoundAdmin ? (
            <Pressable className="primary-button" onClick={onAdminRewards} disabled={busy}>
              <Gift size={18} />
              管理奖品
            </Pressable>
          ) : (
            <Pressable className="checkin-button" onClick={onCheckIn} disabled={busy || checkedIn}>
              <Sparkles size={24} />
              {checkedIn ? "已签到" : "签到"}
            </Pressable>
          )}
        </section>
        <DailyFocusCard focus={home?.newsFocus} role={role} />
        <div className="home-shortcuts">
          <Pressable className="shortcut-card" onClick={isBoundAdmin ? onAdminRecent : onUserRecent}>
            <NotebookText size={18} />
            <span>{isBoundAdmin ? "绑定用户最近" : "最近记录"}</span>
          </Pressable>
          <Pressable className="shortcut-card" onClick={isBoundAdmin ? onAdminRewards : onChat}>
            {isBoundAdmin ? <Gift size={18} /> : <Sparkles size={18} />}
            <span>{isBoundAdmin ? "积分奖品" : "记录对话"}</span>
          </Pressable>
        </div>
      </PageTransition>
    </MobileAppShell>
  );
}
