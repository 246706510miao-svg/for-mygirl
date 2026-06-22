import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import * as ToastPrimitive from "@radix-ui/react-toast";
import { CheckCircle2, Info, XCircle } from "lucide-react";
import { ToastContext, type ToastKind } from "./useToast";

interface ToastItem {
  id: number;
  kind: ToastKind;
  title: string;
  description?: string;
}

interface AppToastProviderProps {
  children: ReactNode;
}

const icons = {
  success: <CheckCircle2 size={18} />,
  error: <XCircle size={18} />,
  info: <Info size={18} />
};

// 这个组件提供全局成功、失败和信息反馈。
export function AppToastProvider({ children }: AppToastProviderProps) {
  const [items, setItems] = useState<ToastItem[]>([]);

  function notify(kind: ToastKind, title: string, description?: string) {
    const id = Date.now() + Math.random();
    setItems((current) => [...current, { id, kind, title, description }]);
  }

  const api = useMemo(
    () => ({
      success: (title: string, description?: string) => notify("success", title, description),
      error: (title: string, description?: string) => notify("error", title, description),
      info: (title: string, description?: string) => notify("info", title, description)
    }),
    []
  );

  return (
    <ToastContext.Provider value={api}>
      <ToastPrimitive.Provider swipeDirection="down">
        {children}
        {items.map((item) => (
          <ToastPrimitive.Root
            key={item.id}
            className={`toast-root toast-root--${item.kind}`}
            duration={2800}
            onOpenChange={(open) => {
              if (!open) {
                setItems((current) => current.filter((candidate) => candidate.id !== item.id));
              }
            }}
          >
            <div className="toast-root__icon">{icons[item.kind]}</div>
            <div>
              <ToastPrimitive.Title>{item.title}</ToastPrimitive.Title>
              {item.description && <ToastPrimitive.Description>{item.description}</ToastPrimitive.Description>}
            </div>
          </ToastPrimitive.Root>
        ))}
        <ToastPrimitive.Viewport className="toast-viewport" />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  );
}
