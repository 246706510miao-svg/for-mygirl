import type { ReactNode } from "react";
import { Home, MessageCircle, NotebookText, Gift, UserRound } from "lucide-react";
import { Pressable } from "../ui/Pressable";

export type MobileTabKey = "home" | "chat" | "records" | "rewards" | "profile";

export interface MobileTabItem {
  key: MobileTabKey;
  label: string;
  onSelect: () => void;
}

interface MobileAppShellProps {
  children: ReactNode;
  activeTab?: MobileTabKey;
  tabs?: MobileTabItem[];
  className?: string;
}

const tabIcons: Record<MobileTabKey, ReactNode> = {
  home: <Home size={22} />,
  chat: <MessageCircle size={22} />,
  records: <NotebookText size={22} />,
  rewards: <Gift size={22} />,
  profile: <UserRound size={22} />
};

// 这个组件承载手机端暖色玻璃背景、安全区和底部导航。
export function MobileAppShell({ children, activeTab, tabs = [], className = "" }: MobileAppShellProps) {
  return (
    <section className={`mobile-shell ${className}`}>
      <div className="mobile-shell__ambient" aria-hidden="true" />
      <div className="mobile-shell__noise" aria-hidden="true" />
      <div className="mobile-shell__content">{children}</div>
      {tabs.length > 0 && (
        <nav className="mobile-tabbar" aria-label="主导航">
          {tabs.map((tab) => (
            <Pressable
              key={tab.key}
              className={`mobile-tabbar__item${activeTab === tab.key ? " is-active" : ""}`}
              aria-label={tab.label}
              aria-current={activeTab === tab.key ? "page" : undefined}
              onClick={tab.onSelect}
            >
              {tabIcons[tab.key]}
              <span>{tab.label}</span>
            </Pressable>
          ))}
        </nav>
      )}
    </section>
  );
}
