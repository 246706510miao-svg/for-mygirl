import assert from "node:assert/strict";
import test from "node:test";
import { buildResumeRecordConfirmRequest } from "../src/features/record/interactionRequest.ts";
import { apiRequest } from "../src/shared/api/client.ts";
import type { PendingThirdConfirmation, ThirdInteractionResponse } from "../src/shared/types/api.ts";

test("confirm resume API sends the current third interaction contract with cookie credentials", async () => {
  const originalFetch = globalThis.fetch;
  const calls: Array<{ input: string; init: RequestInit }> = [];
  const confirmation = {
    status: "waiting_user",
    thirdSessionId: "third_session_1",
    confirmationId: "confirmation_1",
    requestText: "请确认或补充",
    interactionKind: "confirm",
    preview: {},
    clientConfirmId: "client_confirm_1",
    draftId: "draft_1"
  } satisfies PendingThirdConfirmation;

  globalThis.fetch = async (input, init = {}) => {
    calls.push({ input: String(input), init });
    return new Response(JSON.stringify({
      code: "OK",
      message: "ok",
      data: {
        session: { id: "session_1", status: "active" },
        workflowStatus: "processing"
      },
      requestId: "request_1"
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });
  };

  try {
    const cases: Array<{ response: ThirdInteractionResponse; content: string; approved: boolean }> = [
      { response: "answer", content: "补充说明", approved: false },
      { response: "approve", content: "", approved: true }
    ];

    for (const item of cases) {
      const request = buildResumeRecordConfirmRequest("session_1", confirmation, item.response, item.content);
      await apiRequest(request.path, request.options);
    }
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.equal(calls.length, 2);
  for (const [index, call] of calls.entries()) {
    const expected = index === 0
      ? { response: "answer", content: "补充说明", approved: false }
      : { response: "approve", content: "", approved: true };
    const headers = new Headers(call.init.headers);
    const body = JSON.parse(String(call.init.body));

    assert.equal(call.input, "/api/record-sessions/session_1/confirm/resume");
    assert.equal(call.init.method, "POST");
    assert.equal(call.init.credentials, "include");
    assert.equal(headers.get("Content-Type"), "application/json");
    assert.ok(headers.get("X-Request-Id")?.startsWith("req_"));
    assert.deepEqual(body, {
      clientConfirmId: "client_confirm_1",
      draftId: "draft_1",
      thirdSessionId: "third_session_1",
      confirmationId: "confirmation_1",
      ...expected
    });
  }
});
