import { Check, PencilLine } from "lucide-react";
import { motion } from "motion/react";
import type { RecordDraft } from "../../shared/types/api";
import { Pressable } from "../ui/Pressable";

interface DraftPanelProps {
  draft: RecordDraft;
  busy: boolean;
  onConfirm: () => void;
  onEdit: () => void;
}

// 这个组件展示 AI 生成的记录草稿。
export function DraftPanel({ draft, busy, onConfirm, onEdit }: DraftPanelProps) {
  return (
    <motion.article className="draft-panel" layout initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
      <div>
        <span>草稿已生成</span>
        <h2>{draft.draft.title || "记录草稿"}</h2>
        <p>{draft.previewText}</p>
      </div>
      <div className="draft-panel__score">{draft.draft.score ?? "-"} 分</div>
      <div className="draft-panel__actions">
        <Pressable className="secondary-button" disabled={busy} onClick={onEdit}>
          <PencilLine size={16} />
          继续修改
        </Pressable>
        <Pressable className="primary-button" disabled={busy} onClick={onConfirm}>
          <Check size={16} />
          确认
        </Pressable>
      </div>
    </motion.article>
  );
}
