package com.formygirl.stats;

import com.formygirl.common.ApiException;
import com.formygirl.identity.CurrentPerson;
import com.formygirl.relationship.RelationshipService;
import java.time.LocalDate;
import java.time.YearMonth;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class StatsService {
    private final StatsRepository statsRepository;
    private final RelationshipService relationshipService;

    public StatsService(StatsRepository statsRepository, RelationshipService relationshipService) {
        this.statsRepository = statsRepository;
        this.relationshipService = relationshipService;
    }

    // 这个函数返回当前视角拥有者指定月份的打卡日历和记录日历。
    public Map<String, Object> calendar(CurrentPerson person, int year, int month) {
        String ownerUserId = relationshipService.ownerForCurrentView(person);
        return calendarFor(ownerUserId, year, month);
    }

    // 这个函数返回绑定管理员视角下对方的打卡日历。
    public Map<String, Object> boundUserCalendar(CurrentPerson person, int year, int month) {
        String targetUserId = relationshipService.requireBoundAdminTarget(person);
        return calendarFor(targetUserId, year, month);
    }

    // 这个函数返回当前视角拥有者的坚持情况统计摘要。
    public Map<String, Object> summary(CurrentPerson person) {
        String ownerUserId = relationshipService.ownerForCurrentView(person);
        return summaryFor(ownerUserId);
    }

    // 这个函数返回绑定管理员视角下对方的统计摘要。
    public Map<String, Object> boundUserSummary(CurrentPerson person) {
        String targetUserId = relationshipService.requireBoundAdminTarget(person);
        return summaryFor(targetUserId);
    }

    // 这个函数组装指定用户指定月份的日历数据。
    private Map<String, Object> calendarFor(String ownerUserId, int year, int month) {
        YearMonth target = parseYearMonth(year, month);
        LocalDate firstDay = target.atDay(1);
        LocalDate lastDay = target.atEndOfMonth();
        List<LocalDate> allCheckinDates = checkinDates(ownerUserId);
        List<String> checkinDates = allCheckinDates.stream()
                .filter(date -> !date.isBefore(firstDay) && !date.isAfter(lastDay))
                .map(LocalDate::toString)
                .sorted()
                .toList();
        List<String> recordDates = statsRepository.recordDatesBetween(ownerUserId, firstDay, lastDay)
                .stream()
                .map(LocalDate::toString)
                .toList();
        return dto(
                "ownerUserId", ownerUserId,
                "year", target.getYear(),
                "month", target.getMonthValue(),
                "checkinDates", checkinDates,
                "recordDates", recordDates,
                "checkedInToday", allCheckinDates.contains(LocalDate.now())
        );
    }

    // 这个函数组装指定用户的统计摘要。
    private Map<String, Object> summaryFor(String ownerUserId) {
        LocalDate today = LocalDate.now();
        YearMonth currentMonth = YearMonth.from(today);
        List<LocalDate> checkinDates = checkinDates(ownerUserId);
        List<Map<String, Object>> dailyPoints = statsRepository
                .dailyPointsSince(ownerUserId, today.minusDays(13))
                .stream()
                .map(this::dailyPointDto)
                .toList();
        return dto(
                "ownerUserId", ownerUserId,
                "streakDays", streakDays(checkinDates, today),
                "totalPoints", statsRepository.totalPoints(ownerUserId),
                "monthRecordCount", statsRepository.recordCountBetween(ownerUserId, currentMonth.atDay(1), currentMonth.atEndOfMonth()),
                "monthCheckinCount", checkinDates.stream().filter(date -> YearMonth.from(date).equals(currentMonth)).count(),
                "dailyPoints", fillDailyPoints(dailyPoints, today.minusDays(13), today)
        );
    }

    // 这个函数把签到流水的 source_key 解析成打卡日期集合。
    private List<LocalDate> checkinDates(String ownerUserId) {
        return statsRepository.checkinSourceKeys(ownerUserId).stream()
                .map(sourceKey -> sourceKey.substring(sourceKey.lastIndexOf(':') + 1))
                .map(dateText -> {
                    try {
                        return LocalDate.parse(dateText);
                    } catch (Exception exception) {
                        return null;
                    }
                })
                .filter(date -> date != null)
                .distinct()
                .sorted()
                .toList();
    }

    // 这个函数按自然日计算连续签到天数，今天没签到则从昨天往回数。
    private int streakDays(List<LocalDate> checkinDates, LocalDate today) {
        int streak = 0;
        LocalDate cursor = checkinDates.contains(today) ? today : today.minusDays(1);
        while (checkinDates.contains(cursor)) {
            streak = streak + 1;
            cursor = cursor.minusDays(1);
        }
        return streak;
    }

    // 这个函数把按天积分汇总行转换成 day/points DTO。
    private Map<String, Object> dailyPointDto(Map<String, Object> row) {
        Object day = row.get("day");
        Object points = row.get("points");
        String dayText = day instanceof java.sql.Timestamp timestamp
                ? timestamp.toLocalDateTime().toLocalDate().toString()
                : String.valueOf(day);
        int pointsValue = points instanceof Number number ? number.intValue() : 0;
        return dto("day", dayText, "points", pointsValue);
    }

    // 这个函数把最近 N 天的积分序列补零对齐，方便前端直接画图。
    private List<Map<String, Object>> fillDailyPoints(List<Map<String, Object>> dailyPoints, LocalDate startDate, LocalDate endDate) {
        Map<String, Integer> pointsByDay = new LinkedHashMap<>();
        for (Map<String, Object> row : dailyPoints) {
            pointsByDay.put(String.valueOf(row.get("day")), (Integer) row.get("points"));
        }
        List<Map<String, Object>> filled = new ArrayList<>();
        for (LocalDate date = startDate; !date.isAfter(endDate); date = date.plusDays(1)) {
            filled.add(dto("date", date.toString(), "points", pointsByDay.getOrDefault(date.toString(), 0)));
        }
        return filled;
    }

    // 这个函数校验并规范年月参数。
    private YearMonth parseYearMonth(int year, int month) {
        if (year < 2000 || year > 2100 || month < 1 || month > 12) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "BAD_REQUEST", "年月参数不合法");
        }
        return YearMonth.of(year, month);
    }

    private Map<String, Object> dto(Object... entries) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index + 1 < entries.length; index += 2) {
            result.put(String.valueOf(entries[index]), entries[index + 1]);
        }
        return result;
    }
}
