import { ExternalLink, Flame, Sparkles } from "lucide-react";
import { useState } from "react";
import { BottomSheet } from "../../components/ui/BottomSheet";
import { Pressable } from "../../components/ui/Pressable";
import { fetchNewsFocus } from "../record/api";
import type { ClientRole } from "../../shared/api/client";
import type { NewsFocus } from "../../shared/types/api";

interface DailyFocusCardProps {
  focus?: NewsFocus;
  role: ClientRole;
}

function displayTime(value?: string) {
  if (!value) return "刚刚更新";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Shanghai" }).format(date);
}

function shanghaiDate(offsetDays = 0) {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return new Date(Date.UTC(Number(values.year), Number(values.month) - 1, Number(values.day) + offsetDays)).toISOString().slice(0, 10);
}

function itemCount(focus?: NewsFocus) {
  return focus?.groups.reduce((total, group) => total + group.items.length, 0) ?? 0;
}

// 首页只显示一个入口卡；抽屉内按日期与分类查看共享热门。
export function DailyFocusCard({ focus, role }: DailyFocusCardProps) {
  const [open, setOpen] = useState(false);
  const [selectedDate, setSelectedDate] = useState(() => shanghaiDate());
  const [history, setHistory] = useState<NewsFocus | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const today = shanghaiDate();
  const yesterday = shanghaiDate(-1);
  const shownFocus = selectedDate === today ? focus : history;
  const groups = shownFocus?.groups ?? [];
  const available = Boolean(focus?.available && itemCount(focus));
  const headline = focus?.groups.flatMap((group) => group.items)[0];
  const description = shownFocus?.stale
    ? `${shownFocus.focusDate || "此前"} 生成 · 非今日生成`
    : shownFocus?.generatedAt
      ? `${displayTime(shownFocus.generatedAt)} 生成`
      : "公开 RSS 自动整理";
  const dateLabel = selectedDate === today ? "今日" : "昨日";

  async function selectDate(date: string) {
    setSelectedDate(date);
    setHistoryError("");
    if (date === today || history?.focusDate === date) return;
    setLoadingHistory(true);
    try {
      setHistory(await fetchNewsFocus(role, date));
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : "昨日热门暂时不可用。");
    } finally {
      setLoadingHistory(false);
    }
  }

  function openSheet() {
    setSelectedDate(today);
    setHistoryError("");
    setOpen(true);
  }

  return (
    <>
      <Pressable className="news-focus-card" onClick={openSheet} disabled={!available} aria-label="打开今日热门">
        <div className="news-focus-card__heading">
          <span><Flame size={17} /> 今日热门</span>
          {available && <small>{itemCount(focus)} 条 <Sparkles size={13} /></small>}
        </div>
        <strong>{headline?.title || "今日热门正在生成"}</strong>
        <p>{available ? "AI、中国大事、新闻、开源四类内容" : "正在从公开 RSS 来源整理信息。"}</p>
      </Pressable>
      <BottomSheet open={open} onOpenChange={setOpen} title="今日热门" description={description}>
        <div className="news-focus-date-tabs" aria-label="选择每日热门日期">
          <button type="button" className={selectedDate === today ? "active" : ""} onClick={() => void selectDate(today)}>今日</button>
          <button type="button" className={selectedDate === yesterday ? "active" : ""} onClick={() => void selectDate(yesterday)}>查看昨日</button>
        </div>
        {loadingHistory && <p className="news-focus-status">正在读取昨日热门…</p>}
        {historyError && <p className="news-focus-status">{historyError}</p>}
        {!loadingHistory && !historyError && (
          <div className="news-focus-groups">
            {groups.map((group) => (
              <section className="news-focus-group" key={group.key} aria-label={`${group.title}热门`}>
                <div className="news-focus-group__heading">
                  <h3>{group.title}</h3>
                  <span>{group.items.length} 条</span>
                </div>
                <div className="news-focus-list">
                  {group.items.map((item) => (
                    <article className="news-focus-item" key={`${item.rank}-${item.sourceUrl}`}>
                      <div className="news-focus-item__meta">
                        <span>{item.source}</span>
                        <span>{displayTime(item.publishedAt)}</span>
                      </div>
                      <h3>{item.title}</h3>
                      <p>{item.summary}</p>
                      {item.tags.length > 0 && (
                        <div className="news-focus-item__tags">
                          {item.tags.map((tag) => <span key={tag}>{tag}</span>)}
                        </div>
                      )}
                      <a className="news-focus-item__link" href={item.sourceUrl} target="_blank" rel="noopener noreferrer">
                        查看原文 <ExternalLink size={15} />
                      </a>
                    </article>
                  ))}
                  {group.items.length === 0 && <p className="news-focus-status">{dateLabel}暂无可展示的{group.title}内容。</p>}
                  {group.items.length > 0 && group.items.length < 5 && <p className="news-focus-status">该分类不足五条，已按近 72 小时补充。</p>}
                </div>
              </section>
            ))}
            {groups.length === 0 && <p className="news-focus-status">{dateLabel}暂无可展示的热门内容。</p>}
          </div>
        )}
      </BottomSheet>
    </>
  );
}
