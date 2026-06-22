import type { ReactNode } from "react";
import { PageTransition } from "../motion/PageTransition";

interface GlassScreenProps {
  children: ReactNode;
  className?: string;
}

// 这个组件承载二级手机页面的玻璃层。
export function GlassScreen({ children, className = "" }: GlassScreenProps) {
  return (
    <PageTransition direction="up" className={`glass-screen ${className}`}>
      {children}
    </PageTransition>
  );
}
