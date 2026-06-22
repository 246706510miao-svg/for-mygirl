import { forwardRef } from "react";
import type { ReactNode } from "react";
import { motion } from "motion/react";
import type { HTMLMotionProps } from "motion/react";

interface PressableProps extends HTMLMotionProps<"button"> {
  children: ReactNode;
}

// 这个组件统一所有可点击元素的触摸反馈。
export const Pressable = forwardRef<HTMLButtonElement, PressableProps>(
  ({ children, className = "", disabled, type = "button", ...props }, ref) => (
    <motion.button
      ref={ref}
      type={type}
      className={className}
      disabled={disabled}
      whileTap={disabled ? undefined : { scale: 0.96, opacity: 0.84 }}
      transition={{ type: "spring", stiffness: 500, damping: 30 }}
      {...props}
    >
      {children}
    </motion.button>
  )
);

Pressable.displayName = "Pressable";
