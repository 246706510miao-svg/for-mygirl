export type FieldKey = "recordDate" | "summary" | "score" | "displayStatus";

export const fieldLabels: Record<FieldKey, string> = {
  recordDate: "日期",
  summary: "内容",
  score: "打分",
  displayStatus: "状态"
};
