import { motion } from "motion/react";

interface ChatBubbleProps {
  type: "user" | "ai" | "system";
  children: string;
}

// 这个组件渲染对话气泡并在新增时轻微上浮。
export function ChatBubble({ type, children }: ChatBubbleProps) {
  return (
    <motion.article
      className={`chat-bubble chat-bubble--${type}`}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      {children}
    </motion.article>
  );
}
