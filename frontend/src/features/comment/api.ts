import { apiRequest, type ClientRole } from "../../shared/api/client";

// 这个函数保存绑定管理员对记录的评论和打分。
export function saveRecordComment(role: ClientRole, recordId: string, content: string, score: number) {
  return apiRequest<Record<string, unknown>>(`/api/records/${recordId}/comment`, {
    method: "POST",
    role,
    body: JSON.stringify({ content, score })
  });
}
