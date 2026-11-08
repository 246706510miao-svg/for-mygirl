package com.formygirl.stats;

import java.sql.Date;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class StatsRepository {
    private final JdbcTemplate jdbcTemplate;

    public StatsRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    // 这个函数读取用户全部签到流水的 source_key，用于在服务层解析出打卡日期。
    public List<String> checkinSourceKeys(String ownerUserId) {
        return jdbcTemplate.queryForList(
                """
                SELECT source_key FROM POINT_LEDGER
                WHERE owner_user_id = ? AND source_type = 'checkin'
                """,
                String.class,
                ownerUserId
        );
    }

    // 这个函数按天汇总指定起始日之后的积分流水。
    public List<Map<String, Object>> dailyPointsSince(String ownerUserId, LocalDate startDate) {
        return jdbcTemplate.queryForList(
                """
                SELECT DATE(created_at) AS day, SUM(change_amount) AS points
                FROM POINT_LEDGER
                WHERE owner_user_id = ? AND created_at >= ?
                GROUP BY DATE(created_at)
                ORDER BY day ASC
                """,
                ownerUserId,
                java.sql.Timestamp.valueOf(startDate.atStartOfDay())
        );
    }

    // 这个函数统计用户在指定日期区间内的正式记录数。
    public int recordCountBetween(String ownerUserId, LocalDate startDate, LocalDate endDate) {
        Integer count = jdbcTemplate.queryForObject(
                """
                SELECT COUNT(*) FROM DAILY_RECORD
                WHERE user_id = ? AND record_date BETWEEN ? AND ?
                """,
                Integer.class,
                ownerUserId,
                Date.valueOf(startDate),
                Date.valueOf(endDate)
        );
        return count == null ? 0 : count;
    }

    // 这个函数读取用户在指定日期区间内有正式记录的日期。
    public List<LocalDate> recordDatesBetween(String ownerUserId, LocalDate startDate, LocalDate endDate) {
        return jdbcTemplate.queryForList(
                """
                SELECT record_date FROM DAILY_RECORD
                WHERE user_id = ? AND record_date BETWEEN ? AND ?
                ORDER BY record_date ASC
                """,
                Date.class,
                ownerUserId,
                Date.valueOf(startDate),
                Date.valueOf(endDate)
        ).stream().map(Date::toLocalDate).toList();
    }

    // 这个函数汇总用户的累计积分，没有流水时返回 0。
    public int totalPoints(String ownerUserId) {
        Integer total = jdbcTemplate.queryForObject(
                "SELECT COALESCE(SUM(change_amount), 0) FROM POINT_LEDGER WHERE owner_user_id = ?",
                Integer.class,
                ownerUserId
        );
        return total == null ? 0 : total;
    }
}
