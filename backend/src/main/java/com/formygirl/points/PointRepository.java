package com.formygirl.points;

import com.formygirl.common.Ids;
import com.formygirl.common.JsonSupport;
import java.sql.Timestamp;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class PointRepository {
    private final JdbcTemplate jdbcTemplate;
    private final JsonSupport json;

    public PointRepository(JdbcTemplate jdbcTemplate, JsonSupport json) {
        this.jdbcTemplate = jdbcTemplate;
        this.json = json;
    }

    // 这个函数确保用户积分账户存在。
    public Map<String, Object> ensureAccount(String ownerUserId) {
        String id = Ids.newId("pointacct");
        jdbcTemplate.update(
                """
                INSERT INTO POINT_ACCOUNT (id, owner_user_id, balance, updated_at)
                VALUES (?, ?, 0, ?)
                ON DUPLICATE KEY UPDATE owner_user_id = VALUES(owner_user_id)
                """,
                id,
                ownerUserId,
                Timestamp.valueOf(LocalDateTime.now())
        );
        return account(ownerUserId);
    }

    // 这个函数读取用户积分账户。
    public Map<String, Object> account(String ownerUserId) {
        return queryOne("SELECT * FROM POINT_ACCOUNT WHERE owner_user_id = ?", ownerUserId);
    }

    // 这个函数读取指定积分来源的流水。
    public Map<String, Object> ledger(String ownerUserId, String sourceType, String sourceKey) {
        return queryOne("SELECT * FROM POINT_LEDGER WHERE owner_user_id = ? AND source_type = ? AND source_key = ?", ownerUserId, sourceType, sourceKey);
    }

    // 这个函数创建积分流水并返回新流水。
    public Map<String, Object> insertLedger(String ownerUserId, int amount, String reason, String sourceType, String sourceKey, String sourceRecordId, Map<String, Object> metadata) {
        Map<String, Object> account = ensureAccount(ownerUserId);
        String id = Ids.newId("ledger");
        jdbcTemplate.update(
                """
                INSERT INTO POINT_LEDGER (id, account_id, owner_user_id, change_amount, reason, source_record_id, metadata_json, created_at, source_type, source_key)
                VALUES (?, ?, ?, ?, ?, ?, CAST(? AS JSON), ?, ?, ?)
                """,
                id,
                account.get("id"),
                ownerUserId,
                amount,
                reason,
                sourceRecordId,
                json.stringify(metadata),
                Timestamp.valueOf(LocalDateTime.now()),
                sourceType,
                sourceKey
        );
        addBalance(ownerUserId, amount);
        return queryOne("SELECT * FROM POINT_LEDGER WHERE id = ?", id);
    }

    // 这个函数更新幂等积分流水的积分值并按差额调整账户。
    public int updateLedgerAmount(Map<String, Object> ledger, int nextAmount, Map<String, Object> metadata) {
        int previous = intValue(ledger.get("change_amount"), 0);
        int delta = nextAmount - previous;
        if (delta == 0) {
            return 0;
        }
        jdbcTemplate.update(
                "UPDATE POINT_LEDGER SET change_amount = ?, metadata_json = CAST(? AS JSON) WHERE id = ?",
                nextAmount,
                json.stringify(metadata),
                ledger.get("id")
        );
        addBalance(String.valueOf(ledger.get("owner_user_id")), delta);
        return delta;
    }

    // 这个函数查询用户当天签到流水。
    public boolean hasCheckin(String ownerUserId, LocalDate date) {
        return !ledger(ownerUserId, "checkin", "checkin:" + ownerUserId + ":" + date).isEmpty();
    }

    // 这个函数读取用户可兑换奖品。
    public List<Map<String, Object>> activeRewards(String ownerUserId) {
        return jdbcTemplate.queryForList(
                """
                SELECT * FROM REWARD_ITEM
                WHERE owner_user_id = ? AND status = 'active'
                ORDER BY cost_points ASC, created_at DESC
                """,
                ownerUserId
        );
    }

    // 这个函数创建奖品。
    public Map<String, Object> insertReward(String ownerUserId, String createdByUserId, String title, String description, int costPoints) {
        String id = Ids.newId("reward");
        jdbcTemplate.update(
                """
                INSERT INTO REWARD_ITEM (id, owner_user_id, title, description, cost_points, status, created_by_user_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                id,
                ownerUserId,
                title,
                description,
                costPoints,
                createdByUserId,
                Timestamp.valueOf(LocalDateTime.now()),
                Timestamp.valueOf(LocalDateTime.now())
        );
        return reward(id);
    }

    // 这个函数读取奖品。
    public Map<String, Object> reward(String rewardId) {
        return queryOne("SELECT * FROM REWARD_ITEM WHERE id = ?", rewardId);
    }

    // 这个函数把奖品标记为已兑换。
    public void markRewardRedeemed(String rewardId) {
        jdbcTemplate.update(
                "UPDATE REWARD_ITEM SET status = 'redeemed', redeemed_at = ?, updated_at = ? WHERE id = ?",
                Timestamp.valueOf(LocalDateTime.now()),
                Timestamp.valueOf(LocalDateTime.now()),
                rewardId
        );
    }

    // 这个函数创建兑换记录。
    public Map<String, Object> insertRedemption(String rewardId, String userId, String pointLedgerId) {
        String id = Ids.newId("redeem");
        jdbcTemplate.update(
                """
                INSERT INTO REWARD_REDEMPTION (id, reward_id, user_id, point_ledger_id, status, created_at, updated_at, notified_at)
                VALUES (?, ?, ?, ?, 'redeemed', ?, ?, NULL)
                """,
                id,
                rewardId,
                userId,
                pointLedgerId,
                Timestamp.valueOf(LocalDateTime.now()),
                Timestamp.valueOf(LocalDateTime.now())
        );
        return queryOne("SELECT * FROM REWARD_REDEMPTION WHERE id = ?", id);
    }

    // 这个函数读取用户兑换记录和奖品信息。
    public List<Map<String, Object>> redemptions(String ownerUserId) {
        return jdbcTemplate.queryForList(
                """
                SELECT rr.*, ri.title, ri.description, ri.cost_points, ri.owner_user_id
                FROM REWARD_REDEMPTION rr
                JOIN REWARD_ITEM ri ON ri.id = rr.reward_id
                WHERE rr.user_id = ?
                ORDER BY rr.created_at DESC
                """,
                ownerUserId
        );
    }

    // 这个函数调整积分账户余额。
    private void addBalance(String ownerUserId, int amount) {
        ensureAccount(ownerUserId);
        jdbcTemplate.update(
                "UPDATE POINT_ACCOUNT SET balance = balance + ?, updated_at = ? WHERE owner_user_id = ?",
                amount,
                Timestamp.valueOf(LocalDateTime.now()),
                ownerUserId
        );
    }

    private Map<String, Object> queryOne(String sql, Object... args) {
        try {
            return new LinkedHashMap<>(jdbcTemplate.queryForMap(sql, args));
        } catch (EmptyResultDataAccessException exception) {
            return Map.of();
        }
    }

    private int intValue(Object value, int fallback) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        try {
            return Integer.parseInt(String.valueOf(value));
        } catch (Exception exception) {
            return fallback;
        }
    }
}
