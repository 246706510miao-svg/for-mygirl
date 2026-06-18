package com.formygirl.points;

import com.formygirl.common.ApiException;
import com.formygirl.identity.CurrentPerson;
import com.formygirl.relationship.RelationshipService;
import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class PointService {
    private final PointRepository pointRepository;
    private final RelationshipService relationshipService;

    public PointService(PointRepository pointRepository, RelationshipService relationshipService) {
        this.pointRepository = pointRepository;
        this.relationshipService = relationshipService;
    }

    // 这个函数读取当前用户和当前视角拥有者的积分摘要。
    public Map<String, Object> summary(CurrentPerson person) {
        String viewOwnerId = relationshipService.ownerForCurrentView(person);
        return dto(
                "currentUser", accountDto(person.id(), LocalDate.now()),
                "viewOwner", accountDto(viewOwnerId, LocalDate.now()),
                "currentViewRole", relationshipService.currentViewRole(person)
        );
    }

    // 这个函数为当前登录用户执行每日签到。
    @Transactional
    public Map<String, Object> checkin(CurrentPerson person, LocalDate date) {
        String sourceKey = "checkin:" + person.id() + ":" + date;
        Map<String, Object> existing = pointRepository.ledger(person.id(), "checkin", sourceKey);
        int added = 0;
        if (existing.isEmpty()) {
            pointRepository.insertLedger(person.id(), 10, "每日签到", "checkin", sourceKey, null, Map.of("date", date.toString()));
            added = 10;
        }
        return dto("addedPoints", added, "summary", summary(person));
    }

    // 这个函数按绑定用户打分结果刷新记录积分。
    @Transactional
    public Map<String, Object> applyRecordScore(String ownerUserId, String recordId, LocalDate recordDate, int aiScore, int managerScore) {
        int normalized = Math.max(0, Math.min(10, ((Math.max(0, aiScore) + Math.max(0, managerScore)) / 20)));
        String sourceKey = "record_score:" + recordId;
        Map<String, Object> metadata = Map.of(
                "recordId", recordId,
                "recordDate", recordDate.toString(),
                "aiScore", aiScore,
                "managerScore", managerScore,
                "points", normalized
        );
        Map<String, Object> existing = pointRepository.ledger(ownerUserId, "record_score", sourceKey);
        int delta;
        if (existing.isEmpty()) {
            pointRepository.insertLedger(ownerUserId, normalized, "绑定用户记录打分", "record_score", sourceKey, recordId, metadata);
            delta = normalized;
        } else {
            delta = pointRepository.updateLedgerAmount(existing, normalized, metadata);
        }
        return dto("recordId", recordId, "scorePoints", normalized, "deltaPoints", delta, "ownerUserId", ownerUserId);
    }

    // 这个函数读取当前视角可见奖品。
    public Map<String, Object> rewards(CurrentPerson person) {
        String ownerUserId = relationshipService.ownerForCurrentView(person);
        int balance = intValue(pointRepository.ensureAccount(ownerUserId).get("balance"), 0);
        return dto(
                "ownerUserId", ownerUserId,
                "items", pointRepository.activeRewards(ownerUserId).stream().map(row -> rewardDto(row, balance)).toList()
        );
    }

    // 这个函数给绑定用户添加奖品。
    @Transactional
    public Map<String, Object> addReward(CurrentPerson person, String title, String description, int costPoints) {
        String ownerUserId = relationshipService.requireBoundAdminTarget(person);
        if (title == null || title.isBlank() || costPoints < 1) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "BAD_REQUEST", "奖品名称和积分不能为空");
        }
        return rewardDto(pointRepository.insertReward(ownerUserId, person.id(), title.trim(), description == null ? "" : description.trim(), costPoints), intValue(pointRepository.ensureAccount(ownerUserId).get("balance"), 0));
    }

    // 这个函数兑换当前用户自己的奖品。
    @Transactional
    public Map<String, Object> redeem(CurrentPerson person, String rewardId) {
        Map<String, Object> reward = pointRepository.reward(rewardId);
        if (reward.isEmpty() || !"active".equals(String.valueOf(reward.get("status"))) || !person.id().equals(String.valueOf(reward.get("owner_user_id")))) {
            throw new ApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", "奖品不存在或不可兑换");
        }
        int cost = intValue(reward.get("cost_points"), 0);
        int balance = intValue(pointRepository.ensureAccount(person.id()).get("balance"), 0);
        if (balance < cost) {
            throw new ApiException(HttpStatus.CONFLICT, "CONFLICT", "积分不足");
        }
        Map<String, Object> ledger = pointRepository.insertLedger(person.id(), -cost, "兑换奖品", "reward_redeem", "reward:" + rewardId, null, Map.of("rewardId", rewardId, "title", String.valueOf(reward.get("title"))));
        pointRepository.markRewardRedeemed(rewardId);
        Map<String, Object> redemption = pointRepository.insertRedemption(rewardId, person.id(), String.valueOf(ledger.get("id")));
        return dto("reward", rewardDto(pointRepository.reward(rewardId), balance - cost), "redemption", redemptionDto(redemption), "summary", summary(person));
    }

    // 这个函数读取当前视角下的兑换记录。
    public Map<String, Object> redemptions(CurrentPerson person) {
        String ownerUserId = relationshipService.ownerForCurrentView(person);
        return dto("ownerUserId", ownerUserId, "items", pointRepository.redemptions(ownerUserId).stream().map(this::redemptionDto).toList());
    }

    private Map<String, Object> accountDto(String ownerUserId, LocalDate date) {
        Map<String, Object> account = pointRepository.ensureAccount(ownerUserId);
        return dto(
                "ownerUserId", ownerUserId,
                "balance", intValue(account.get("balance"), 0),
                "checkedInToday", pointRepository.hasCheckin(ownerUserId, date)
        );
    }

    private Map<String, Object> rewardDto(Map<String, Object> row, int balance) {
        return dto(
                "id", row.get("id"),
                "ownerUserId", row.get("owner_user_id"),
                "title", row.get("title"),
                "description", row.get("description"),
                "costPoints", row.get("cost_points"),
                "status", row.get("status"),
                "redeemable", "active".equals(String.valueOf(row.get("status"))) && balance >= intValue(row.get("cost_points"), 0),
                "createdByUserId", row.get("created_by_user_id"),
                "redeemedAt", row.get("redeemed_at")
        );
    }

    private Map<String, Object> redemptionDto(Map<String, Object> row) {
        return dto(
                "id", row.get("id"),
                "rewardId", row.get("reward_id"),
                "userId", row.get("user_id"),
                "title", row.get("title"),
                "description", row.get("description"),
                "costPoints", row.get("cost_points"),
                "status", row.get("status"),
                "createdAt", row.get("created_at"),
                "notifiedAt", row.get("notified_at")
        );
    }

    private Map<String, Object> dto(Object... entries) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index + 1 < entries.length; index += 2) {
            result.put(String.valueOf(entries[index]), entries[index + 1]);
        }
        return result;
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
