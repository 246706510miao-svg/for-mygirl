import type { FormEvent } from "react";
import { Mic, Send } from "lucide-react";
import { Pressable } from "../ui/Pressable";

interface ComposerProps {
  value: string;
  busy: boolean;
  onChange: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
  onVoice: () => void;
}

// 这个组件承载底部输入栏和未来语音入口。
export function Composer({ value, busy, onChange, onSubmit, onVoice }: ComposerProps) {
  return (
    <form className="composer" onSubmit={onSubmit}>
      <Pressable className="icon-button composer__voice" onClick={onVoice} aria-label="语音输入">
        <Mic size={19} />
      </Pressable>
      <input value={value} onChange={(event) => onChange(event.target.value)} placeholder="写下今天的记录" />
      <Pressable className="composer__send" type="submit" disabled={busy || !value.trim()} aria-label="发送">
        <Send size={18} />
      </Pressable>
    </form>
  );
}
