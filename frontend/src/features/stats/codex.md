# features/stats Codex 入口

打卡统计功能的前端模块，按 `docs/future/04-打卡日历与统计.md` 实现。

## 文件

| 文件 | 作用 |
|---|---|
| `api.ts` | 封装 `GET /api/stats/checkin-calendar`（支持年月参数）和 `GET /api/stats/summary` 两个只读接口。 |
| `../pages/StatsScreen.tsx` | 统计页面：连续签到/累计积分/本月记录三张指标卡、月历双色打卡视图（签到橙色、有记录蓝色）、最近 14 天积分趋势柱状图和上/下月份切换。 |
| `../../shared/types/api.ts` | `StatsCalendar`、`StatsSummary`、`DailyPoint` 三个 DTO。 |

## 口径

- 页面通过 `MobileWorkspace.tsx` 的 `stats` tab 和 `HomeScreen` 的“打卡统计”快捷卡进入。
- 月份切换由页面游标驱动，复用后端 `year`/`month` 参数；查看当月时“下一月”按钮置灰。
- 月历卡显示的签到次数取 `calendar.checkinDates.length`（跟随查看月份），摘要卡的“本月记录”取 `summary.monthRecordCount`（固定当月）。
- “今天”高亮使用本地时区日期（`localToday()`），不用 UTC 的 `toISOString()`，避免凌晨日期偏移。
- 本模块只读，不写任何接口；绑定管理员视角通过后端 `ownerForCurrentView` 口径自动生效。
