import { FormEvent, useState } from "react";
import { Gift, MessageCircleHeart, Plus, Sparkles } from "lucide-react";
import { InlineCommentForm } from "../components/admin/InlineCommentForm";
import { GlassScreen } from "../components/layout/GlassScreen";
import { MobileAppShell } from "../components/layout/MobileAppShell";
import { ScreenHeader } from "../components/layout/ScreenHeader";
import { RecordCard } from "../components/records/RecordCard";
import { RewardCard } from "../components/rewards/RewardCard";
import { BottomSheet } from "../components/ui/BottomSheet";
import { EmptyState } from "../components/ui/EmptyState";
import { MetricLine } from "../components/ui/MetricLine";
import { Pressable } from "../components/ui/Pressable";
import { pendingCareRecords } from "../app/mobileViewState";
import type { PointSummary, RecordDisplay, RewardItem, RewardRedemption } from "../shared/types/api";

interface CareScreenProps {
  points: PointSummary | null;
  records: RecordDisplay[];
  rewards: RewardItem[];
  redemptions: RewardRedemption[];
  busy: boolean;
  onBack: () => void;
  onAddReward: (title: string, description: string, costPoints: number) => Promise<boolean>;
  onSaveComment: (recordId: string, content: string, score: number) => Promise<unknown> | unknown;
}

const careFields = ["recordDate", "summary", "score"] as const;

// 照顾者模式只保留两个真实活动：评论记录与管理奖品。
export function CareScreen({ points, records, rewards, redemptions, busy, onBack, onAddReward, onSaveComment }: CareScreenProps) {
  const [tab, setTab] = useState<"comments" | "rewards">("comments");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [rewardName, setRewardName] = useState("");
  const [rewardCost, setRewardCost] = useState("20");
  const [rewardDescription, setRewardDescription] = useState("");
  const [error, setError] = useState("");
  const commentRecords = pendingCareRecords(records);

  async function submitReward(event: FormEvent) {
    event.preventDefault();
    const cost = Number(rewardCost);
    if (!rewardName.trim() || !Number.isInteger(cost) || cost < 1) {
      setError("请补全奖品名称和正整数积分");
      return;
    }
    setError("");
    if (await onAddReward(rewardName.trim(), rewardDescription.trim(), cost)) {
      setRewardName("");
      setRewardCost("20");
      setRewardDescription("");
      setSheetOpen(false);
    }
  }

  return (
    <MobileAppShell className="care-shell">
      <GlassScreen>
        <ScreenHeader title="照顾者模式" subtitle="把关心放进两件具体的小事里" onBack={onBack} />
        <section className="care-hero">
          <span><MessageCircleHeart size={19} /></span>
          <div><p>当前仅开放</p><h1>记录反馈与奖品管理</h1><small>这里使用绑定用户权限，不会混入后台运维功能。</small></div>
        </section>
        <div className="care-tabs" role="tablist" aria-label="照顾者活动">
          <Pressable role="tab" aria-selected={tab === "comments"} className={tab === "comments" ? "is-selected" : ""} onClick={() => setTab("comments")}><MessageCircleHeart size={16} />评论记录</Pressable>
          <Pressable role="tab" aria-selected={tab === "rewards"} className={tab === "rewards" ? "is-selected" : ""} onClick={() => setTab("rewards")}><Gift size={16} />管理奖品</Pressable>
        </div>

        {tab === "comments" && (
          <section className="record-list care-record-list" role="tabpanel">
            {commentRecords.map((record) => (
              <RecordCard key={record.recordId} record={record} fields={[...careFields]}>
                <InlineCommentForm
                  initialComment={record.managerComment || ""}
                  initialScore={record.managerScore ?? record.score ?? 80}
                  busy={busy}
                  onSave={(content, score) => onSaveComment(record.recordId, content, score)}
                />
              </RecordCard>
            ))}
            {commentRecords.length === 0 && <EmptyState title="暂无待评论记录" description="新的记录出现后，就可以在这里评论和打分。" />}
          </section>
        )}

        {tab === "rewards" && (
          <section className="care-rewards" role="tabpanel">
            <MetricLine label="TA 的可用积分" value={points?.viewOwner.balance ?? 0} unit="积分" icon={<Sparkles size={20} />} />
            <Pressable className="care-add-reward" onClick={() => setSheetOpen(true)} disabled={busy}>
              <Plus size={19} /><span><b>添加一份新奖品</b><small>名称、说明与所需积分会展示给 TA</small></span>
            </Pressable>
            <section className="reward-list">
              {rewards.map((reward) => <RewardCard key={reward.id} reward={reward} canRedeem={false} adminMode busy={busy} />)}
              {rewards.length === 0 && <EmptyState title="还没有准备奖品" description="添加后会出现在 TA 的心意商店。" />}
            </section>
            <section className="redemption-list">
              <h2>最近兑换</h2>
              {redemptions.map((item) => <p key={item.id}>{item.title} 已被兑换 · {item.costPoints} 分</p>)}
              {redemptions.length === 0 && <p>暂无兑换记录</p>}
            </section>
          </section>
        )}

        <BottomSheet open={sheetOpen} onOpenChange={setSheetOpen} title="添加一份心意" description="给绑定用户添加一个可兑换奖品。">
          <form className="sheet-form" onSubmit={submitReward}>
            <label>奖品名称<input value={rewardName} onChange={(event) => setRewardName(event.target.value)} placeholder="例如：一起看一场电影" /></label>
            <label>所需积分<input value={rewardCost} onChange={(event) => setRewardCost(event.target.value)} inputMode="numeric" type="number" min="1" /></label>
            <label>奖品说明<textarea value={rewardDescription} onChange={(event) => setRewardDescription(event.target.value)} placeholder="写下兑换后的约定或小惊喜" /></label>
            {error && <p className="field-error">{error}</p>}
            <Pressable className="primary-button" type="submit" disabled={busy}>{busy ? "保存中" : "保存奖品"}</Pressable>
          </form>
        </BottomSheet>
      </GlassScreen>
    </MobileAppShell>
  );
}
