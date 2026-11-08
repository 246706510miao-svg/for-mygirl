import { apiRequest, type ClientRole } from "../../shared/api/client";
import type { StatsCalendar, StatsSummary } from "../../shared/types/api";

// 这个函数读取指定月份的打卡日历，不传年月时后端默认返回当月。
export function fetchStatsCalendar(role: ClientRole, year?: number, month?: number) {
  const params = new URLSearchParams();
  if (year !== undefined) {
    params.set("year", String(year));
  }
  if (month !== undefined) {
    params.set("month", String(month));
  }
  const query = params.toString();
  return apiRequest<StatsCalendar>(`/api/stats/checkin-calendar${query ? `?${query}` : ""}`, { role });
}

// 这个函数读取坚持情况统计摘要。
export function fetchStatsSummary(role: ClientRole) {
  return apiRequest<StatsSummary>("/api/stats/summary", { role });
}
