import type { RecordDisplay, RewardRedemption } from "../shared/types/api";

// 照顾者评论页只展示尚未保存过绑定评论的记录。
export function pendingCareRecords(records: RecordDisplay[]) {
  return records.filter((record) => !record.boundComment?.id && !record.managerComment?.trim());
}

function redemptionTimestamp(item: RewardRedemption) {
  if (!item.createdAt) {
    return null;
  }
  const timestamp = Date.parse(item.createdAt);
  return Number.isFinite(timestamp) ? timestamp : null;
}

// 已兑换奖励按时间降序排列；无有效时间的数据稳定放在末尾。
export function sortRedemptionsNewestFirst(redemptions: RewardRedemption[]) {
  return redemptions
    .map((item, index) => ({ item, index, timestamp: redemptionTimestamp(item) }))
    .sort((left, right) => {
      if (left.timestamp === null && right.timestamp === null) {
        return left.index - right.index;
      }
      if (left.timestamp === null) {
        return 1;
      }
      if (right.timestamp === null) {
        return -1;
      }
      return right.timestamp - left.timestamp || left.index - right.index;
    })
    .map(({ item }) => item);
}
