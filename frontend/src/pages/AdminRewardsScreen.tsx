import { FormEvent, useState } from "react";
import { Plus, Sparkles } from "lucide-react";
import { BottomSheet } from "../components/ui/BottomSheet";
import { EmptyState } from "../components/ui/EmptyState";
import { MetricLine } from "../components/ui/MetricLine";
import { Pressable } from "../components/ui/Pressable";
import { RewardCard } from "../components/rewards/RewardCard";
import { GlassScreen } from "../components/layout/GlassScreen";
import { MobileAppShell } from "../components/layout/MobileAppShell";
import { ScreenHeader } from "../components/layout/ScreenHeader";
import type { PointSummary, RewardItem, RewardRedemption } from "../shared/types/api";

interface AdminRewardsScreenProps {
  points: PointSummary | null;
  rewards: RewardItem[];
  redemptions: RewardRedemption[];
  busy: boolean;
  onBack: () => void;
  onAddReward: (title: string, costPoints: number) => Promise<boolean>;
}

// 这个页面让绑定管理员管理积分奖品。
export function AdminRewardsScreen({ points, rewards, redemptions, busy, onBack, onAddReward }: AdminRewardsScreenProps) {
  const [sheetOpen, setSheetOpen] = useState(false);
  const [rewardName, setRewardName] = useState("");
  const [rewardCost, setRewardCost] = useState("20");
  const [error, setError] = useState("");

  async function submitReward(event: FormEvent) {
    event.preventDefault();
    const cost = Number(rewardCost);
    if (!rewardName.trim() || !Number.isInteger(cost) || cost < 1) {
      setError("请补全奖品名称和正整数积分");
      return;
    }
    setError("");
    const ok = await onAddReward(rewardName.trim(), cost);
    if (ok) {
      setRewardName("");
      setRewardCost("20");
      setSheetOpen(false);
    }
  }

  return (
    <MobileAppShell>
      <GlassScreen>
        <ScreenHeader
          title="Rewards"
          onBack={onBack}
          rightSlot={
            <Pressable className="icon-button" onClick={() => setSheetOpen(true)} aria-label="添加奖品">
              <Plus size={20} />
            </Pressable>
          }
        />
        <MetricLine label="绑定用户积分" value={points?.viewOwner.balance ?? 0} unit="points" icon={<Sparkles size={20} />} />
        <section className="reward-list">
          {rewards.map((reward) => (
            <RewardCard key={reward.id} reward={reward} canRedeem={false} adminMode busy={busy} />
          ))}
          {rewards.length === 0 && <EmptyState title="暂无奖品" description="添加后会展示给绑定用户兑换。" />}
        </section>
        <section className="redemption-list">
          <h2>兑换提示</h2>
          {redemptions.map((item) => <p key={item.id}>{item.title} 已被兑换 · {item.costPoints} 分</p>)}
          {redemptions.length === 0 && <p>暂无兑换记录</p>}
        </section>
        <BottomSheet open={sheetOpen} onOpenChange={setSheetOpen} title="Add reward" description="给绑定用户添加一个可兑换奖品。">
          <form className="sheet-form" onSubmit={submitReward}>
            <label>
              奖品名称
              <input value={rewardName} onChange={(event) => setRewardName(event.target.value)} placeholder="奖品名称" />
            </label>
            <label>
              所需积分
              <input value={rewardCost} onChange={(event) => setRewardCost(event.target.value)} inputMode="numeric" type="number" min="1" />
            </label>
            {error && <p className="field-error">{error}</p>}
            <Pressable className="primary-button" type="submit" disabled={busy}>
              {busy ? "保存中" : "保存"}
            </Pressable>
          </form>
        </BottomSheet>
      </GlassScreen>
    </MobileAppShell>
  );
}
