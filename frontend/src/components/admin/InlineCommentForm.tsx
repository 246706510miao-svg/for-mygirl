import { FormEvent, useEffect, useState } from "react";
import * as Slider from "@radix-ui/react-slider";
import { Save } from "lucide-react";
import { Pressable } from "../ui/Pressable";

interface InlineCommentFormProps {
  initialComment?: string;
  initialScore?: number;
  busy?: boolean;
  onSave: (content: string, score: number) => Promise<unknown> | unknown;
}

// 这个组件为绑定管理员提供单条记录评论和打分。
export function InlineCommentForm({ initialComment = "", initialScore = 80, busy = false, onSave }: InlineCommentFormProps) {
  const [comment, setComment] = useState(initialComment);
  const [score, setScore] = useState(initialScore);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setComment(initialComment);
    setScore(initialScore);
  }, [initialComment, initialScore]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const content = comment.trim();
    if (!content) {
      setError("评论不能为空");
      return;
    }
    if (!Number.isFinite(score) || score < 0 || score > 100) {
      setError("打分需为 0-100");
      return;
    }
    setError("");
    setSaving(true);
    try {
      await onSave(content, score);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="inline-comment-form" onSubmit={submit}>
      <label>
        评论
        <textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder="写下评论" />
      </label>
      <div className="score-row">
        <span>打分</span>
        <Slider.Root className="score-slider" value={[score]} min={0} max={100} step={1} onValueChange={([value]) => setScore(value ?? 0)}>
          <Slider.Track className="score-slider__track">
            <Slider.Range className="score-slider__range" />
          </Slider.Track>
          <Slider.Thumb className="score-slider__thumb" aria-label="打分" />
        </Slider.Root>
        <input value={score} type="number" min={0} max={100} onChange={(event) => setScore(Number(event.target.value))} aria-label="打分数字" />
      </div>
      {error && <p className="field-error">{error}</p>}
      <Pressable className="primary-button inline-comment-form__save" type="submit" disabled={busy || saving}>
        <Save size={16} />
        {saving ? "保存中" : "保存"}
      </Pressable>
    </form>
  );
}
