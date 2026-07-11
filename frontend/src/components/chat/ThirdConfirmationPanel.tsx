import { useEffect, useId, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import { Check, Send, X } from "lucide-react";
import { motion } from "motion/react";
import type { PendingThirdConfirmation, ThirdInteractionResponse } from "../../shared/types/api";
import { Pressable } from "../ui/Pressable";

interface ThirdConfirmationPanelProps {
  confirmation: PendingThirdConfirmation;
  busy: boolean;
  onRespond: (response: ThirdInteractionResponse, content?: string) => void;
}

function optionText(option: unknown) {
  if (typeof option === "string") {
    return option;
  }
  if (option && typeof option === "object") {
    const item = option as Record<string, unknown>;
    return String(item.label || item.name || item.value || JSON.stringify(item));
  }
  return String(option ?? "");
}

function previewText(confirmation: PendingThirdConfirmation) {
  if (!confirmation.preview || Object.keys(confirmation.preview).length === 0) {
    return null;
  }
  return JSON.stringify(confirmation.preview, null, 2);
}

// 这个组件按 third 的交互类型承载追问、修改和最终确认。
export function ThirdConfirmationPanel({ confirmation, busy, onRespond }: ThirdConfirmationPanelProps) {
  const [content, setContent] = useState("");
  const inputId = useId();
  const kind = confirmation.interactionKind || "confirm";
  const needsAnswer = kind !== "confirm";
  const preview = previewText(confirmation);

  useEffect(() => setContent(""), [confirmation.confirmationId]);

  function submitContent(event?: FormEvent) {
    event?.preventDefault();
    const value = content.trim();
    if (!value || busy) {
      return;
    }
    onRespond(needsAnswer ? "answer" : "modify", value);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      submitContent();
    }
  }

  return (
    <motion.article className="third-confirm-panel" layout initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
      <div className="third-confirm-panel__heading">
        <span>{needsAnswer ? "还想问你一点" : "执行前确认"}</span>
        <small>我会在这里等你</small>
      </div>
      <h2>{confirmation.requestText || (needsAnswer ? "请补充这一步需要的信息。" : "确认执行以下飞书写入操作吗？")}</h2>

      {confirmation.options && confirmation.options.length > 0 && (
        <div className="third-confirm-panel__options">
          {confirmation.options.map((option, index) => {
            const text = optionText(option);
            return (
              <Pressable key={`${text}-${index}`} disabled={busy} onClick={() => setContent(text)}>
                {text}
              </Pressable>
            );
          })}
        </div>
      )}

      {preview && (
        <details className="third-confirm-panel__preview">
          <summary>查看准备执行的内容</summary>
          <pre>{preview}</pre>
        </details>
      )}

      <form className="third-confirm-panel__reply" onSubmit={submitContent}>
        <label htmlFor={inputId}>{needsAnswer ? "把答案告诉我" : "想调整的话，直接写在这里"}</label>
        <textarea
          id={inputId}
          value={content}
          disabled={busy}
          rows={3}
          onChange={(event) => setContent(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={needsAnswer ? "例如：C 是评分，日期就是今天，总结写练背两小时。" : "例如：把日期改成昨天，并补充一行总结。"}
        />
        <small>支持多行输入 · Ctrl / Cmd + Enter 提交</small>
      </form>

      <div className={`third-confirm-panel__actions ${needsAnswer ? "is-question" : ""}`}>
        <Pressable className="secondary-button" disabled={busy} onClick={() => onRespond("cancel")}>
          <X size={16} />
          暂时取消
        </Pressable>
        {needsAnswer ? (
          <Pressable className="primary-button" disabled={busy || !content.trim()} onClick={() => submitContent()}>
            <Send size={16} />
            提交回答
          </Pressable>
        ) : (
          <>
            <Pressable className="secondary-button" disabled={busy || !content.trim()} onClick={() => submitContent()}>
              <Send size={16} />
              按我的想法调整
            </Pressable>
            <Pressable className="primary-button" disabled={busy} onClick={() => onRespond("approve")}>
              <Check size={16} />
              确认执行
            </Pressable>
          </>
        )}
      </div>
    </motion.article>
  );
}
