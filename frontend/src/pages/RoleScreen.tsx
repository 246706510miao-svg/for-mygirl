import { FormEvent, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { LogOut, UserPlus, UserRound } from "lucide-react";
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
  onInviteBinding: (loginName: string) => Promise<boolean>;
  onAcceptBindingInvitation: (bindingId: string) => void;
  onRejectBindingInvitation: (bindingId: string) => void;
  onCancelBindingInvitation: (bindingId: string) => void;
  onLogout: () => void;
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
  onRedeem,
  onInviteBinding,
  onAcceptBindingInvitation,
  onRejectBindingInvitation,
  onCancelBindingInvitation,
  onLogout
}: RoleScreenProps) {
  const [targetLoginName, setTargetLoginName] = useState("");
  const binding = context.binding;
  const incoming = binding.incomingInvitations ?? [];
  const outgoing = binding.outgoingInvitations ?? [];

  async function submitInvite(event: FormEvent) {
    event.preventDefault();
    const ok = await onInviteBinding(targetLoginName.trim());
    if (ok) {
      setTargetLoginName("");
    }
  }

  return (
    <MobileAppShell>
      <GlassScreen>
        <ScreenHeader
          title="Profile"
          onBack={onBack}
          rightSlot={
            <Pressable className="icon-button" onClick={onLogout} disabled={busy} aria-label="退出登录">
              <LogOut size={20} />
            </Pressable>
          }
        />
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
          {!canSwitchToBoundAdmin && <p className="identity-card__hint">绑定用户后可切换管理员视角，评论记录并管理奖品。</p>}
        </section>
        <section className="binding-panel">
          <div className="binding-panel__title">
            <UserPlus size={18} />
            <b>绑定用户</b>
          </div>
          {binding.active && binding.boundUser ? (
            <p>已绑定：{binding.boundUser.displayName}{binding.boundUser.loginName ? `（${binding.boundUser.loginName}）` : ""}</p>
          ) : (
            <form className="binding-form" onSubmit={submitInvite}>
              <input value={targetLoginName} onChange={(event) => setTargetLoginName(event.target.value)} placeholder="输入对方账号" />
              <Pressable className="primary-button" type="submit" disabled={busy || !targetLoginName.trim()}>
                发起邀请
              </Pressable>
            </form>
          )}
          {incoming.length > 0 && (
            <div className="binding-list">
              <strong>收到的邀请</strong>
              {incoming.map((item) => (
                <div className="binding-list__item" key={item.id}>
                  <span>{item.requester.displayName}{item.requester.loginName ? `（${item.requester.loginName}）` : ""}</span>
                  <div>
                    <Pressable className="secondary-button" onClick={() => onRejectBindingInvitation(item.id)} disabled={busy}>拒绝</Pressable>
                    <Pressable className="primary-button" onClick={() => onAcceptBindingInvitation(item.id)} disabled={busy}>接受</Pressable>
                  </div>
                </div>
              ))}
            </div>
          )}
          {outgoing.length > 0 && (
            <div className="binding-list">
              <strong>发出的邀请</strong>
              {outgoing.map((item) => (
                <div className="binding-list__item" key={item.id}>
                  <span>{item.target.displayName}{item.target.loginName ? `（${item.target.loginName}）` : ""}</span>
                  <Pressable className="secondary-button" onClick={() => onCancelBindingInvitation(item.id)} disabled={busy}>取消</Pressable>
                </div>
              ))}
            </div>
          )}
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
