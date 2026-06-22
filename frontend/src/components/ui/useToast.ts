import { createContext, useContext } from "react";

export type ToastKind = "success" | "error" | "info";

export interface ToastApi {
  success: (title: string, description?: string) => void;
  error: (title: string, description?: string) => void;
  info: (title: string, description?: string) => void;
}

export const ToastContext = createContext<ToastApi | null>(null);

// 这个 hook 暴露全局反馈入口。
export function useToast() {
  const api = useContext(ToastContext);
  if (!api) {
    return {
      success: () => undefined,
      error: () => undefined,
      info: () => undefined
    };
  }
  return api;
}
