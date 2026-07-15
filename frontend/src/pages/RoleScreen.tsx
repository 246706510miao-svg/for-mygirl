import { FormEvent, useState } from "react";
import { ChevronRight, Gift, HeartHandshake, LogOut, Sparkles, UserPlus, UserRound } from "lucide-react";
import { GlassScreen } from "../components/layout/GlassScreen";
import { MobileAppShell, type MobileTabItem } from "../components/layout/MobileAppShell";
import { ScreenHeader } from "../components/layout/ScreenHeader";
import { Pressable } from "../components/ui/Pressable";
import type { IdentityContext, PointSummary, RewardItem } from "../shared/types/api";

interface RoleScreenProps {
  context: IdentityContext;
  points: PointSummary | null;
  rewards: RewardItem[];
  tabs: MobileTabItem[];
  canEnterCare: boolean;
  busy: boolean;
  onBack: () => void;
  onRewards: () => void;
  onEnterCare: () => void;
  onInviteBinding: (loginName: string) => Promise<boolean>;
  onAcceptBindingInvitation: (bindingId: string) => void;
  onRejectBindingInvitation: (bindingId: string) => void;
  onCancelBindingInvitation: (bindingId: string) => void;
  onLogout: () => void;
}

// 个人页集中展示本人身份、积分心意、绑定关系和照顾者模式入口。
export function RoleScreen({
  context,
  points,
  rewards,
  tabs,
  canEnterCare,
  busy,
  onBack,
  onRewards,
  onEnterCare,
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
  const balance = points?.currentUser.balance ?? 0;
  const previewReward = rewards.find((reward) => reward.status.toLowerCase() === "active") ?? rewards[0];
  const pointsGap = previewReward ? Math.max(previewReward.costPoints - balance, 0) : 0;

  async function submitInvite(event: FormEvent) {
    event.preventDefault();
    const ok = await onInviteBinding(targetLoginName.trim());
    if (ok) setTargetLoginName("");
  }

  return (
    <MobileAppShell activeTab="profile" tabs={tabs}>
      <GlassScreen>
        <ScreenHeader
          title="我的小世界"
          subtitle="关系、身份与照顾方式都在这里"
          onBack={onBack}
          rightSlot={<Pressable className="icon-button" onClick={onLogout} disabled={busy} aria-label="退出登录"><LogOut size={20} /></Pressable>}
        />
        <section className="identity-card">
          <div className="identity-card__avatar"><UserRound size={30} /></div>
          <h1>{context.person.displayName}</h1>
          <p>{binding.active && binding.boundUser ? `已和 ${binding.boundUser.displayName} 互相绑定` : "先邀请对方，建立双向绑定"}</p>
          <span className={`binding-status${binding.active ? " is-active" : ""}`}>{binding.active ? "双向关系已建立" : "等待绑定"}</span>
        </section>

        <Pressable className="profile-wallet" onClick={onRewards} aria-label="查看积分和心意奖品">
          <span className="profile-wallet__points">
            <i><Sparkles size={19} /></i>
            <span><small>我的积分</small><strong>{balance}<em>积分</em></strong></span>
          </span>
          <span className="profile-wallet__reward">
            <small><Gift size={13} />离你最近的心意</small>
            {previewReward ? (
              <><b>{previewReward.title}</b><span className="profile-wallet__copy">{previewReward.description || "打开心意商店查看这份奖品"}</span><em>{previewReward.costPoints} 分 · {previewReward.redeemable ? "现在可兑换" : `还差 ${pointsGap} 分`}</em></>
            ) : (
              <><b>心意正在准备中</b><span className="profile-wallet__copy">照顾者添加奖品后会显示在这里。</span></>
            )}
          </span>
          <ChevronRight className="profile-wallet__arrow" size={18} />
        </Pressable>

        <Pressable className="care-entry" onClick={onEnterCare} disabled={busy || !canEnterCare}>
          <span className="care-entry__icon"><HeartHandshake size={22} /></span>
          <span><b>照顾者模式</b><small>{canEnterCare ? "评论 TA 的记录，或为 TA 添加奖品" : "完成双向绑定后开放"}</small></span>
          <ChevronRight size={18} />
        </Pressable>

        <section className="binding-panel">
          <div className="binding-panel__title"><UserPlus size={18} /><b>双向绑定</b></div>
          {binding.active && binding.boundUser ? (
            <p>已绑定：{binding.boundUser.displayName}{binding.boundUser.loginName ? `（${binding.boundUser.loginName}）` : ""}</p>
          ) : (
            <form className="binding-form" onSubmit={submitInvite}>
              <input value={targetLoginName} onChange={(event) => setTargetLoginName(event.target.value)} placeholder="输入对方账号" />
              <Pressable className="primary-button" type="submit" disabled={busy || !targetLoginName.trim()}>发起邀请</Pressable>
            </form>
          )}
          {incoming.length > 0 && (
            <div className="binding-list">
              <strong>收到的邀请</strong>
              {incoming.map((item) => (
                <div className="binding-list__item" key={item.id}>
                  <span>{item.requester.displayName}{item.requester.loginName ? `（${item.requester.loginName}）` : ""}</span>
                  <div><Pressable className="secondary-button" onClick={() => onRejectBindingInvitation(item.id)} disabled={busy}>拒绝</Pressable><Pressable className="primary-button" onClick={() => onAcceptBindingInvitation(item.id)} disabled={busy}>接受</Pressable></div>
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
      </GlassScreen>
    </MobileAppShell>
  );
}
