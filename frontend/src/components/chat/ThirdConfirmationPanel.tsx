import { Check, X } from "lucide-react";
import { motion } from "motion/react";
import type { PendingThirdConfirmation } from "../../shared/types/api";
import { Pressable } from "../ui/Pressable";

interface ThirdConfirmationPanelProps {
  confirmation: PendingThirdConfirmation;
  busy: boolean;
  onApprove: () => void;
  onReject: () => void;
}

function previewText(confirmation: PendingThirdConfirmation) {
  if (!confirmation.preview || Object.keys(confirmation.preview).length === 0) {
    return "{}";
  }
  return JSON.stringify(confirmation.preview, null, 2);
}

// 这个组件展示 third workflow 生成的操作确认。
export function ThirdConfirmationPanel({ confirmation, busy, onApprove, onReject }: ThirdConfirmationPanelProps) {
  return (
    <motion.article className="third-confirm-panel" layout initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
      <div>
        <span>待确认操作</span>
        <h2>{confirmation.requestText || "确认执行以下飞书写入操作吗？"}</h2>
      </div>
      <pre>{previewText(confirmation)}</pre>
      <div className="third-confirm-panel__actions">
        <Pressable className="secondary-button" disabled={busy} onClick={onReject}>
          <X size={16} />
          取消
        </Pressable>
        <Pressable className="primary-button" disabled={busy} onClick={onApprove}>
          <Check size={16} />
          确认执行
        </Pressable>
      </div>
    </motion.article>
  );
}
