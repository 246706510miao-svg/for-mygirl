import type { ReactNode } from "react";
import { Drawer } from "vaul";

interface BottomSheetProps {
  open: boolean;
  title: string;
  description?: string;
  children: ReactNode;
  actions?: ReactNode;
  onOpenChange: (open: boolean) => void;
}

// 这个组件封装 Vaul 底部抽屉。
export function BottomSheet({ open, title, description, children, actions, onOpenChange }: BottomSheetProps) {
  return (
    <Drawer.Root
      open={open}
      onOpenChange={onOpenChange}
      autoFocus
      repositionInputs
    >
      <Drawer.Portal>
        <Drawer.Overlay className="sheet-overlay" />
        <Drawer.Content className="bottom-sheet" tabIndex={-1}>
          <Drawer.Handle className="bottom-sheet__handle" />
          <div className="bottom-sheet__header">
            <Drawer.Title>{title}</Drawer.Title>
            {description && <Drawer.Description>{description}</Drawer.Description>}
          </div>
          <div className="bottom-sheet__body">{children}</div>
          {actions && <div className="bottom-sheet__actions">{actions}</div>}
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
