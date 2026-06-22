import type { ReactNode } from "react";
import { ArrowLeft } from "lucide-react";
import { Pressable } from "../ui/Pressable";

interface ScreenHeaderProps {
  title: string;
  onBack: () => void;
  rightSlot?: ReactNode;
}

// 这个组件统一二级页面返回栏和标题居中。
export function ScreenHeader({ title, onBack, rightSlot }: ScreenHeaderProps) {
  return (
    <header className="screen-header">
      <Pressable className="icon-button" aria-label="返回" onClick={onBack}>
        <ArrowLeft size={21} />
      </Pressable>
      <h1>{title}</h1>
      <div className="screen-header__right">{rightSlot}</div>
    </header>
  );
}
