import { ArrowRight, Gift, Heart, MessageCircle, NotebookText, Sparkles } from "lucide-react";
import { MobileAppShell, type MobileTabItem } from "../components/layout/MobileAppShell";
import { PageTransition } from "../components/motion/PageTransition";
import { Pressable } from "../components/ui/Pressable";
import { DailyFocusCard } from "../features/newsfocus/DailyFocusCard";
import type { IdentityContext, PointSummary, UserHome } from "../shared/types/api";
import type { ClientRole } from "../shared/api/client";

interface HomeScreenProps {
  context: IdentityContext;
  home: UserHome | null;
  points: PointSummary | null;
  busy: boolean;
  role: ClientRole;
  tabs: MobileTabItem[];
  onProfile: () => void;
  onCheckIn: () => void;
  onChat: () => void;
  onUserRecent: () => void;
  onRewards: () => void;
}

// 这个页面只承载用户自己的首页；照顾者活动从个人页独立进入。
export function HomeScreen({
  context,
  home,
  points,
  busy,
  role,
  tabs,
  onProfile,
  onCheckIn,
  onChat,
  onUserRecent,
  onRewards
}: HomeScreenProps) {
  const balance = points?.currentUser.balance ?? 0;
  const checkedIn = Boolean(points?.currentUser.checkedInToday);
  const today = new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "long",
    timeZone: "Asia/Shanghai"
  }).format(new Date());
  const boundName = context.binding.active && context.binding.boundUser?.displayName
    ? context.binding.boundUser.displayName
    : "TA";
  const configuredTitle = home?.homeContent.mainText?.trim();
  const usesDefaultTitle = !configuredTitle || ["今天也认真照顾自己", "留下今天的心意"].includes(configuredTitle);
  const heroTitle = usesDefaultTitle ? `今天有没有想${boundName}` : configuredTitle;

  return (
    <MobileAppShell activeTab="home" tabs={tabs}>
      <PageTransition className="home-screen" direction="none">
        <header className="home-header">
          <div>
            <p>{today}</p>
            <h1>晚上好，{context.person.displayName}</h1>
          </div>
          <Pressable className="avatar-button" onClick={onProfile} aria-label="打开个人与关系设置">
            {context.person.displayName.slice(0, 1)}
          </Pressable>
        </header>
        <span className="role-pill"><Heart size={13} fill="currentColor" />我的视角</span>

        <section className="home-card">
          <div className="home-card__eyebrow"><Sparkles size={18} /><span>今天也在认真生活</span></div>
          <h2>{heroTitle}</h2>
          <p>{home?.homeContent.subText || "把完成过的小事写下来，慢慢看到自己的节奏。"}</p>
          <Pressable className="checkin-button home-card__checkin" onClick={onCheckIn} disabled={busy || checkedIn}>
            <Sparkles size={18} />
            {checkedIn ? "今日份心意已收集" : "今日签到 · 积分 +10"}
          </Pressable>
        </section>

        <section className="points-card">
          <div className="points-card__icon"><Gift size={20} /></div>
          <div className="points-card__value"><span>我们的小金库</span><strong>{balance}<small>积分</small></strong></div>
          <Pressable className="points-card__action" onClick={onRewards}>去心意商店<ArrowRight size={15} /></Pressable>
        </section>

        <DailyFocusCard focus={home?.newsFocus} role={role} />

        <section className="home-section">
          <div className="home-section__heading"><div><span>今日入口</span><h2>想从哪里开始？</h2></div></div>
          <div className="home-shortcuts">
            <Pressable className="shortcut-card" onClick={onUserRecent}>
              <span className="shortcut-card__icon"><NotebookText size={19} /></span>
              <span><b>最近记录</b><small>回看我们最近的日常</small></span>
              <ArrowRight size={17} />
            </Pressable>
            <Pressable className="shortcut-card" onClick={onChat}>
              <span className="shortcut-card__icon"><MessageCircle size={19} /></span>
              <span><b>和 CCC 聊聊</b><small>把今天的碎片整理成记录</small></span>
              <ArrowRight size={17} />
            </Pressable>
          </div>
        </section>
      </PageTransition>
    </MobileAppShell>
  );
}
