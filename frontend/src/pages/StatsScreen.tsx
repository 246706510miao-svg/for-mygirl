import { useCallback, useEffect, useState } from "react";
import { CalendarCheck, Flame, NotebookText, RefreshCw, TrendingUp } from "lucide-react";
import { MobileAppShell, type MobileTabItem } from "../components/layout/MobileAppShell";
import { PageTransition } from "../components/motion/PageTransition";
import { EmptyState } from "../components/ui/EmptyState";
import { fetchStatsCalendar, fetchStatsSummary } from "../features/stats/api";
import type { StatsCalendar, StatsSummary } from "../shared/types/api";
import type { ClientRole } from "../shared/api/client";

interface StatsScreenProps {
  role: ClientRole;
  tabs: MobileTabItem[];
}

const WEEKDAY_LABELS = ["一", "二", "三", "四", "五", "六", "日"];

// 这个函数计算某年某月第一天在周一开头网格中的偏移。
function firstWeekdayOffset(year: number, month: number) {
  return (new Date(year, month - 1, 1).getDay() + 6) % 7;
}

// 这个函数返回某年某月的天数。
function daysInMonth(year: number, month: number) {
  return new Date(year, month, 0).getDate();
}

// 这个页面展示打卡日历、连续签到和最近 14 天积分趋势。
export function StatsScreen({ role, tabs }: StatsScreenProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [calendar, setCalendar] = useState<StatsCalendar | null>(null);
  const [summary, setSummary] = useState<StatsSummary | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [calendarData, summaryData] = await Promise.all([
        fetchStatsCalendar(role),
        fetchStatsSummary(role)
      ]);
      setCalendar(calendarData);
      setSummary(summaryData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "统计加载失败");
    } finally {
      setLoading(false);
    }
  }, [role]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading && !calendar) {
    return (
      <MobileAppShell activeTab="stats" tabs={tabs}>
        <EmptyState title="统计加载中..." />
      </MobileAppShell>
    );
  }

  if (error && !calendar) {
    return (
      <MobileAppShell activeTab="stats" tabs={tabs}>
        <EmptyState title={error || "统计加载失败"} />
      </MobileAppShell>
    );
  }

  if (!calendar || !summary) {
    return null;
  }

  const checkinSet = new Set(calendar.checkinDates);
  const recordSet = new Set(calendar.recordDates);
  const offset = firstWeekdayOffset(calendar.year, calendar.month);
  const totalDays = daysInMonth(calendar.year, calendar.month);
  const cells: Array<number | null> = [
    ...Array.from({ length: offset }, () => null),
    ...Array.from({ length: totalDays }, (_, index) => index + 1)
  ];
  const todayText = new Date().toISOString().slice(0, 10);
  const maxPoints = Math.max(1, ...summary.dailyPoints.map((item) => item.points));

  return (
    <MobileAppShell activeTab="stats" tabs={tabs}>
      <PageTransition className="home-screen" direction="none">
        <header className="home-header">
          <div>
            <p>{calendar.year} 年 {calendar.month} 月</p>
            <h1>坚持的痕迹</h1>
          </div>
          <button
            type="button"
            className="avatar-button"
            onClick={() => void load()}
            aria-label="刷新统计"
            style={{ border: "none", cursor: "pointer" }}
          >
            <RefreshCw size={16} />
          </button>
        </header>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
          <div className="shortcut-card" style={{ flexDirection: "column", alignItems: "flex-start", gap: 4 }}>
            <span className="shortcut-card__icon"><Flame size={18} /></span>
            <b style={{ fontSize: 22, lineHeight: 1 }}>{summary.streakDays}</b>
            <small>连续签到（天）</small>
          </div>
          <div className="shortcut-card" style={{ flexDirection: "column", alignItems: "flex-start", gap: 4 }}>
            <span className="shortcut-card__icon"><TrendingUp size={18} /></span>
            <b style={{ fontSize: 22, lineHeight: 1 }}>{summary.totalPoints}</b>
            <small>累计积分</small>
          </div>
          <div className="shortcut-card" style={{ flexDirection: "column", alignItems: "flex-start", gap: 4 }}>
            <span className="shortcut-card__icon"><NotebookText size={18} /></span>
            <b style={{ fontSize: 22, lineHeight: 1 }}>{summary.monthRecordCount}</b>
            <small>本月记录（条）</small>
          </div>
        </div>

        <section className="home-card" style={{ marginTop: 14 }}>
          <div className="home-card__eyebrow">
            <CalendarCheck size={18} />
            <span>{calendar.year} 年 {calendar.month} 月 · 签到 {summary.monthCheckinCount} 次</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 6, marginTop: 10 }}>
            {WEEKDAY_LABELS.map((label) => (
              <span key={label} style={{ textAlign: "center", fontSize: 11, opacity: 0.65 }}>{label}</span>
            ))}
            {cells.map((day, index) => {
              if (day === null) {
                return <span key={`blank-${index}`} />;
              }
              const dateText = `${calendar.year}-${String(calendar.month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
              const checked = checkinSet.has(dateText);
              const recorded = recordSet.has(dateText);
              const isToday = dateText === todayText;
              return (
                <span
                  key={dateText}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    height: 34,
                    borderRadius: 10,
                    fontSize: 12,
                    fontWeight: isToday ? 700 : 400,
                    border: isToday ? "1.5px solid currentColor" : "1px solid transparent",
                    background: checked
                      ? "rgba(255, 148, 112, 0.35)"
                      : recorded
                        ? "rgba(120, 170, 255, 0.28)"
                        : "rgba(255, 255, 255, 0.14)"
                  }}
                  title={checked ? "已签到" : recorded ? "有记录" : undefined}
                >
                  {day}
                </span>
              );
            })}
          </div>
          <div style={{ display: "flex", gap: 12, marginTop: 10, fontSize: 11, opacity: 0.75 }}>
            <span>🟠 签到打卡</span>
            <span>🔵 当日有记录</span>
          </div>
        </section>

        <section className="home-section" style={{ marginTop: 14 }}>
          <div className="home-section__heading">
            <div><span>积分趋势</span><h2>最近 14 天</h2></div>
          </div>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 4, height: 110, padding: "8px 4px" }}>
            {summary.dailyPoints.map((item) => (
              <div
                key={item.date}
                style={{
                  flex: 1,
                  height: `${Math.max(4, (item.points / maxPoints) * 100)}%`,
                  minHeight: 4,
                  borderRadius: 6,
                  background: item.points > 0
                    ? "linear-gradient(180deg, rgba(255, 148, 112, 0.85), rgba(255, 148, 112, 0.45))"
                    : "rgba(255, 255, 255, 0.18)",
                  position: "relative"
                }}
                title={`${item.date}：${item.points} 分`}
              />
            ))}
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, opacity: 0.65 }}>
            <span>{summary.dailyPoints[0]?.date.slice(5)}</span>
            <span>今天</span>
          </div>
        </section>
      </PageTransition>
    </MobileAppShell>
  );
}
