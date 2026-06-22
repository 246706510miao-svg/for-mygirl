import { useState } from "react";
import { Gift, Sparkles } from "lucide-react";
import type { RewardItem } from "../../shared/types/api";
import { BottomSheet } from "../ui/BottomSheet";
import { Pressable } from "../ui/Pressable";

interface RewardCardProps {
  reward: RewardItem;
  canRedeem: boolean;
  adminMode?: boolean;
  busy?: boolean;
  onRedeem?: (rewardId: string) => void;
}

// 这个组件展示奖品并用底部抽屉承载详情和兑换动作。
export function RewardCard({ reward, canRedeem, adminMode = false, busy = false, onRedeem }: RewardCardProps) {
  const [open, setOpen] = useState(false);
  const redeemed = Boolean(reward.redeemedAt) || reward.status === "REDEEMED";
  const disabled = busy || !reward.redeemable || redeemed;

  function redeem() {
    if (disabled || !onRedeem) {
      return;
    }
    onRedeem(reward.id);
    setOpen(false);
  }

  return (
    <>
      <Pressable className={`reward-card${redeemed ? " is-redeemed" : ""}`} onClick={() => setOpen(true)} aria-label={`查看奖品 ${reward.title}`}>
        <div className="reward-card__icon"><Gift size={20} /></div>
        <div>
          <h2>{reward.title}</h2>
          <p>{reward.description || "可兑换奖品"}</p>
        </div>
        <strong>{reward.costPoints} 分</strong>
        <span className="reward-card__status">
          {adminMode ? reward.status : reward.redeemable ? "可兑换" : "积分不足"}
        </span>
      </Pressable>
      <BottomSheet
        open={open}
        onOpenChange={setOpen}
        title={reward.title}
        description={reward.description || "可兑换奖品"}
        actions={
          canRedeem ? (
            <Pressable className="primary-button" disabled={disabled} onClick={redeem}>
              {reward.redeemable && !redeemed ? "兑换" : "暂不可兑换"}
            </Pressable>
          ) : undefined
        }
      >
        <section className="reward-detail">
          <Sparkles size={28} />
          <span>所需积分</span>
          <strong>{reward.costPoints}</strong>
          <p>{redeemed ? "这个奖品已经兑换。" : adminMode ? "绑定用户可在用户视角兑换这个奖品。" : "确认后会从可兑换列表中移除。"}</p>
        </section>
      </BottomSheet>
    </>
  );
}
