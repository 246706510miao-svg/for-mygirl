import { Check, X } from "lucide-react";
import { motion } from "motion/react";
import type { PendingThirdConfirmation, ThirdInteractionResponse } from "../../shared/types/api";
import { Pressable } from "../ui/Pressable";

interface ThirdConfirmationPanelProps {
  confirmation: PendingThirdConfirmation;
  busy: boolean;
  onRespond: (response: ThirdInteractionResponse, content?: string) => void;
}

function previewText(confirmation: PendingThirdConfirmation) {
  if (!confirmation.preview || Object.keys(confirmation.preview).length === 0) {
    return null;
  }
  return JSON.stringify(confirmation.preview, null, 2);
}

// 普通追问统一使用底部输入框；这里只保留风险操作必须显式选择的两个动作。
export function ThirdConfirmationPanel({ confirmation, busy, onRespond }: ThirdConfirmationPanelProps) {
  const preview = previewText(confirmation);

  return (
    <motion.article className="third-confirm-panel" layout initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
      {preview && (
        <details className="third-confirm-panel__preview">
          <summary>查看准备执行的内容</summary>
          <pre>{preview}</pre>
        </details>
      )}

      <div className="third-confirm-panel__actions">
        <Pressable className="secondary-button" disabled={busy} onClick={() => onRespond("cancel")}>
          <X size={16} />
          暂不执行
        </Pressable>
        <Pressable className="primary-button" disabled={busy} onClick={() => onRespond("approve")}>
          <Check size={16} />
          确认执行
        </Pressable>
      </div>
    </motion.article>
  );
}
