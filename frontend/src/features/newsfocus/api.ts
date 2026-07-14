import { apiRequest, type ClientRole } from "../../shared/api/client";
import type { NewsFocus } from "../../shared/types/api";

// 这个函数读取共享每日热门的当天或昨天结果。
export function fetchNewsFocus(role: ClientRole, date: string) {
  return apiRequest<NewsFocus>(`/api/user/news-focus?date=${encodeURIComponent(date)}`, { role });
}
