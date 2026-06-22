import type { ReactNode } from "react";
import { motion } from "motion/react";

type Direction = "right" | "left" | "up" | "none";

interface PageTransitionProps {
  children: ReactNode;
  className?: string;
  direction?: Direction;
}

const offsets: Record<Direction, { x?: number; y?: number }> = {
  right: { x: 16 },
  left: { x: -16 },
  up: { y: 18 },
  none: {}
};

// 这个组件统一页面切换的淡入和位移动效。
export function PageTransition({ children, className = "", direction = "right" }: PageTransitionProps) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, scale: 0.98, ...offsets[direction] }}
      animate={{ opacity: 1, scale: 1, x: 0, y: 0 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
