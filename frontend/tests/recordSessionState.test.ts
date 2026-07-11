import assert from "node:assert/strict";
import test from "node:test";
import type { RecordSessionDetail } from "../src/shared/types/api.ts";
import { recordConversationState } from "../src/app/recordSessionState.ts";

test("clears the stale draft when a confirmed detail also contains currentDraft", () => {
  const detail = {
    session: { id: "session_1", status: "confirmed", currentDraftId: "draft_1" },
    messages: [],
    currentDraft: {
      id: "draft_1",
      versionNo: 1,
      status: "confirmed",
      previewText: "已经写入的草稿",
      draft: { title: "记录", score: 80 }
    },
    record: { id: "record_1", status: "success" }
  } satisfies RecordSessionDetail;

  assert.deepEqual(recordConversationState(detail), {
    session: null,
    draft: null,
    pendingConfirmation: null
  });
});

test("keeps an active draft while the session is still previewing", () => {
  const detail = {
    session: { id: "session_1", status: "previewing", currentDraftId: "draft_1" },
    messages: [],
    currentDraft: {
      id: "draft_1",
      versionNo: 1,
      status: "active",
      previewText: "等待确认的草稿",
      draft: { title: "记录", score: 80 }
    },
    record: null
  } satisfies RecordSessionDetail;

  const state = recordConversationState(detail);
  assert.equal(state.session?.id, "session_1");
  assert.equal(state.draft?.id, "draft_1");
  assert.equal(state.pendingConfirmation, null);
});
