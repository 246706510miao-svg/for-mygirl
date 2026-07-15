import type { ReactNode } from "react";
import { motion } from "motion/react";

interface ChatBubbleProps {
  type: "user" | "ai" | "system";
  pending?: boolean;
  error?: boolean;
  children: ReactNode;
}

// 这个组件渲染对话气泡并在新增时轻微上浮。
export function ChatBubble({ type, pending = false, error = false, children }: ChatBubbleProps) {
  return (
    <motion.article
      className={`chat-bubble chat-bubble--${type}${pending ? " chat-bubble--pending" : ""}${error ? " chat-bubble--error" : ""}`}
      aria-live={pending ? "polite" : undefined}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: pending ? 0.58 : 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      {children}
    </motion.article>
  );
}
