import { apiRequest, type ClientRole } from "../../shared/api/client";
import type { PointSummary, RewardItem, RewardList, RewardRedemptionList } from "../../shared/types/api";

// 这个函数读取积分摘要。
export function fetchPointSummary(role: ClientRole) {
  return apiRequest<PointSummary>("/api/points/summary", { role });
}

// 这个函数执行每日签到。
export function checkIn(role: ClientRole) {
  return apiRequest<{ addedPoints: number; summary: PointSummary }>("/api/points/checkins", {
    method: "POST",
    role
  });
}

// 这个函数读取当前视角可见奖品。
export function fetchRewards(role: ClientRole) {
  return apiRequest<RewardList>("/api/rewards", { role });
}

// 这个函数给绑定用户添加奖品。
export function addReward(role: ClientRole, title: string, costPoints: number) {
  return apiRequest<RewardItem>("/api/rewards", {
    method: "POST",
    role,
    body: JSON.stringify({ title, costPoints, description: "绑定用户添加的可兑换奖品" })
  });
}

// 这个函数兑换当前用户自己的奖品。
export function redeemReward(role: ClientRole, rewardId: string) {
  return apiRequest<Record<string, unknown>>(`/api/rewards/${rewardId}/redeem`, {
    method: "POST",
    role
  });
}

// 这个函数读取兑换记录。
export function fetchRedemptions(role: ClientRole) {
  return apiRequest<RewardRedemptionList>("/api/reward-redemptions", { role });
}
