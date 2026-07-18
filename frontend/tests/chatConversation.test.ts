import assert from "node:assert/strict";
import test from "node:test";
import type { RecordSessionDetail } from "../src/shared/types/api.ts";
import { appendOptimisticTurn, conversationMessagesFromDetail, replacePendingWithMessage, shouldShowInteractionPrompt } from "../src/app/chatConversation.ts";

test("shows the user message and thinking reply before the request finishes", () => {
  const messages = appendOptimisticTurn([], "今天完成了两件事", "turn_1");

  assert.deepEqual(messages, [
    { id: "user-turn_1", type: "user", content: "今天完成了两件事" },
    { id: "pending-turn_1", type: "ai", content: "正在思考…", pending: true }
  ]);
});

test("keeps workflow progress in the conversation and removes old generic prompts", () => {
  const detail = {
    session: { id: "session_1", status: "active" },
    messages: [
      { id: "message_1", sessionId: "session_1", sender: "user", inputType: "text", content: "两条记录", sequenceNo: 1 },
      { id: "message_2", sessionId: "session_1", sender: "ai", inputType: "text", content: "还差一点信息，回答后我会继续帮你整理。", sequenceNo: 2 }
    ],
    latestWorkflowTask: {
      id: "task_1",
      sessionId: "session_1",
      triggerType: "message",
      clientActionId: "message_1",
      status: "running"
    }
  } satisfies RecordSessionDetail;

  assert.deepEqual(conversationMessagesFromDetail(detail), [
    { id: "message_1", type: "user", content: "两条记录" },
    { id: "pending-task_1", type: "ai", content: "正在思考…", pending: true }
  ]);
});

test("replaces the thinking reply with the real AI response", () => {
  const pending = appendOptimisticTurn([], "是", "turn_2");

  assert.deepEqual(replacePendingWithMessage(pending, "turn_2", "好的，我继续整理。"), [
    { id: "user-turn_2", type: "user", content: "是" },
    { id: "pending-turn_2", type: "ai", content: "好的，我继续整理。" }
  ]);
});

test("does not repeat the resolved interaction prompt after the thinking reply", () => {
  const prompt = "新增的“抽象程度”字段需要指定字段类型和属性。";
  const messages = appendOptimisticTurn(
    [{ id: "message_1", type: "ai", content: prompt }],
    "文本",
    "turn_3"
  );

  assert.equal(shouldShowInteractionPrompt(messages, prompt), false);
  assert.equal(
    shouldShowInteractionPrompt(
      messages.filter((message) => !message.pending),
      prompt
    ),
    true
  );
});

test("shows a short in-conversation error instead of the raw backend exception", () => {
  const detail = {
    session: { id: "session_1", status: "active" },
    messages: [],
    latestWorkflowTask: {
      id: "task_failed",
      sessionId: "session_1",
      triggerType: "message",
      clientActionId: "message_1",
      status: "failed",
      errorText: "400 Bad Request: confirmation_id 不属于当前 task"
    }
  } satisfies RecordSessionDetail;

  assert.deepEqual(conversationMessagesFromDetail(detail), [
    { id: "error-task_failed", type: "ai", content: "这次没有顺利完成，请再试一次。", error: true }
  ]);
});
