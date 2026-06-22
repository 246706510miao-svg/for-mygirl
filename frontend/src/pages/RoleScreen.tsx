import { AnimatePresence, motion } from "motion/react";
import { UserRound } from "lucide-react";
import { GlassScreen } from "../components/layout/GlassScreen";
import { MobileAppShell } from "../components/layout/MobileAppShell";
import { ScreenHeader } from "../components/layout/ScreenHeader";
import { MetricLine } from "../components/ui/MetricLine";
import { Pressable } from "../components/ui/Pressable";
import { EmptyState } from "../components/ui/EmptyState";
import { RewardCard } from "../components/rewards/RewardCard";
import type { IdentityContext, PointSummary, RewardItem } from "../shared/types/api";

interface RoleScreenProps {
  context: IdentityContext;
  points: PointSummary | null;
  rewards: RewardItem[];
  isBoundAdmin: boolean;
  canSwitchToBoundAdmin: boolean;
  busy: boolean;
  onBack: () => void;
  onToggleRole: () => void;
  onRedeem: (rewardId: string) => void;
}

// 这个页面展示身份、视角切换、积分和奖品。
export function RoleScreen({
  context,
  points,
  rewards,
  isBoundAdmin,
  canSwitchToBoundAdmin,
  busy,
  onBack,
  onToggleRole,
  onRedeem
}: RoleScreenProps) {
  return (
    <MobileAppShell>
      <GlassScreen>
        <ScreenHeader title="Profile" onBack={onBack} />
        <section className="identity-card">
          <div className="identity-card__avatar"><UserRound size={30} /></div>
          <h1>{isBoundAdmin ? "TA 的管理页" : context.person.displayName}</h1>
          <p>{isBoundAdmin ? "Bound administrator" : "User view"}</p>
          <div className="segmented-control">
            <Pressable className={!isBoundAdmin ? "is-selected" : ""} onClick={isBoundAdmin ? onToggleRole : undefined} disabled={busy || !isBoundAdmin}>
              用户
            </Pressable>
            <Pressable
              className={isBoundAdmin ? "is-selected" : ""}
              onClick={!isBoundAdmin ? onToggleRole : undefined}
              disabled={busy || isBoundAdmin || !canSwitchToBoundAdmin}
            >
              管理员
            </Pressable>
          </div>
        </section>
        <AnimatePresence mode="wait">
          <motion.div
            key={isBoundAdmin ? "admin" : "user"}
            className="role-content"
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -16 }}
            transition={{ duration: 0.22 }}
          >
            <MetricLine label={isBoundAdmin ? "TA 的积分" : "我的积分"} value={points?.viewOwner.balance ?? 0} unit="points" />
            <section className="reward-list">
              {rewards.map((reward) => (
                <RewardCard key={reward.id} reward={reward} canRedeem={!isBoundAdmin} adminMode={isBoundAdmin} busy={busy} onRedeem={onRedeem} />
              ))}
              {rewards.length === 0 && <EmptyState title="暂无可兑换奖品" description="奖品会在这里展示。" />}
            </section>
          </motion.div>
        </AnimatePresence>
      </GlassScreen>
    </MobileAppShell>
  );
}
