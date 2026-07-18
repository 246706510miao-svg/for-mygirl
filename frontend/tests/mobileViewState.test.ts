import assert from "node:assert/strict";
import test from "node:test";
import type { RecordDisplay, RewardRedemption } from "../src/shared/types/api.ts";
import { pendingCareRecords, sortRedemptionsNewestFirst } from "../src/app/mobileViewState.ts";

function record(recordId: string, overrides: Partial<RecordDisplay> = {}): RecordDisplay {
  return {
    recordId,
    title: `记录 ${recordId}`,
    summary: "测试记录",
    displayStatus: "visible",
    ...overrides
  };
}

function redemption(id: string, createdAt?: string): RewardRedemption {
  return {
    id,
    rewardId: `reward_${id}`,
    userId: "user_1",
    title: `奖励 ${id}`,
    costPoints: 20,
    status: "redeemed",
    createdAt
  };
}

test("care comment list excludes records that already have a saved comment", () => {
  const records = [
    record("pending"),
    record("commented", {
      boundComment: {
        id: "comment_1",
        recordId: "commented",
        authorUserId: "user_2",
        authorDisplayName: "小明",
        content: "做得很好",
        score: 90
      }
    }),
    record("legacy-comment", { managerComment: "已经评论过" })
  ];

  assert.deepEqual(pendingCareRecords(records).map((item) => item.recordId), ["pending"]);
});

test("redemptions are complete and ordered newest first with invalid dates last", () => {
  const redemptions = [
    redemption("old", "2026-07-01T08:00:00Z"),
    redemption("missing"),
    redemption("newest", "2026-07-18T08:00:00Z"),
    redemption("invalid", "not-a-date"),
    redemption("middle", "2026-07-10T08:00:00Z")
  ];

  assert.deepEqual(
    sortRedemptionsNewestFirst(redemptions).map((item) => item.id),
    ["newest", "middle", "old", "missing", "invalid"]
  );
});
