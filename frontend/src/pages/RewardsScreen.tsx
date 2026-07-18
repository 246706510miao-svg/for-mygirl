import { Gift, Sparkles } from "lucide-react";
import { GlassScreen } from "../components/layout/GlassScreen";
import { MobileAppShell, type MobileTabItem } from "../components/layout/MobileAppShell";
import { ScreenHeader } from "../components/layout/ScreenHeader";
import { RewardCard } from "../components/rewards/RewardCard";
import { EmptyState } from "../components/ui/EmptyState";
import { MetricLine } from "../components/ui/MetricLine";
import { sortRedemptionsNewestFirst } from "../app/mobileViewState";
import type { PointSummary, RewardItem, RewardRedemption } from "../shared/types/api";

interface RewardsScreenProps {
  points: PointSummary | null;
  rewards: RewardItem[];
  redemptions: RewardRedemption[];
  tabs: MobileTabItem[];
  busy: boolean;
  onBack: () => void;
  onRedeem: (rewardId: string) => void;
}

function redemptionDateTime(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Shanghai"
  }).format(date);
}

// 这个页面是用户自己的心意商店，只负责查看积分和兑换奖品。
export function RewardsScreen({ points, rewards, redemptions, tabs, busy, onBack, onRedeem }: RewardsScreenProps) {
  const orderedRedemptions = sortRedemptionsNewestFirst(redemptions);

  return (
    <MobileAppShell activeTab="rewards" tabs={tabs}>
      <GlassScreen>
        <ScreenHeader title="心意商店" subtitle="攒下的每一点，都会变成期待" onBack={onBack} />
        <MetricLine label="我的可用积分" value={points?.currentUser.balance ?? 0} unit="积分" icon={<Sparkles size={20} />} />
        <section className="shop-intro">
          <Gift size={18} />
          <p>这些奖品由你的照顾者准备。打开卡片即可查看详情并确认兑换。</p>
        </section>
        <section className="reward-list reward-list--shop">
          {rewards.map((reward) => (
            <RewardCard key={reward.id} reward={reward} canRedeem balance={points?.currentUser.balance ?? 0} busy={busy} onRedeem={onRedeem} />
          ))}
          {rewards.length === 0 && <EmptyState title="心意正在准备中" description="照顾者添加奖品后会出现在这里。" />}
        </section>
        <section className="redemption-list redemption-list--shop">
          <h2>已兑换</h2>
          {orderedRedemptions.map((item) => {
            const redeemedAt = redemptionDateTime(item.createdAt);
            return (
              <div className="redemption-list__item" key={item.id}>
                <span><b>{item.title}</b><small>{item.costPoints} 积分{redeemedAt ? ` · ${redeemedAt}` : ""}</small></span>
                <em>已兑换</em>
              </div>
            );
          })}
          {orderedRedemptions.length === 0 && <p>还没有兑换记录，慢慢攒下喜欢的心意。</p>}
        </section>
      </GlassScreen>
    </MobileAppShell>
  );
}
