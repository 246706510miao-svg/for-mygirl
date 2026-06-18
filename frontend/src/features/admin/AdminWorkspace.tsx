import { useEffect, useState } from "react";
import { apiRequest, login } from "../../shared/api/client";

// 这个组件承载管理员 PC 后台基础页面。
export function AdminWorkspace() {
  const [dashboard, setDashboard] = useState<Record<string, unknown>>({});
  const [records, setRecords] = useState<Record<string, unknown>[]>([]);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [trace, setTrace] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    void bootstrapAdmin();
  }, []);

  // 这个函数初始化管理员 token 和后台列表。
  async function bootstrapAdmin() {
    await login("admin");
    const dashboardData = await apiRequest<Record<string, unknown>>("/api/admin/dashboard", { role: "admin" });
    const recordData = await apiRequest<{ items: Record<string, unknown>[] }>("/api/admin/records?page=1&pageSize=20", { role: "admin" });
    setDashboard(dashboardData);
    setRecords(recordData.items);
  }

  // 这个函数读取管理员记录详情。
  async function openDetail(recordId: string) {
    const data = await apiRequest<Record<string, unknown>>(`/api/admin/records/${recordId}`, { role: "admin" });
    setDetail(data);
    setTrace(null);
  }

  // 这个函数读取记录追踪。
  async function openTrace(recordId: string) {
    const data = await apiRequest<Record<string, unknown>>(`/api/admin/records/${recordId}/trace`, { role: "admin" });
    setTrace(data);
  }

  return (
    <section className="admin-layout">
      <aside>
        <b>Admin</b>
        <button onClick={bootstrapAdmin}>刷新</button>
      </aside>
      <main>
        <section className="summary">
          <div><span>今日记录</span><b>{String(dashboard.todayRecordCount ?? 0)}</b></div>
          <div><span>待反馈</span><b>{String(dashboard.pendingFeedbackCount ?? 0)}</b></div>
          <div><span>异常</span><b>{String(dashboard.abnormalCount ?? 0)}</b></div>
        </section>
        <section className="table">
          {records.map((record) => (
            <div className="row" key={String(record.recordId)}>
              <span>{String(record.recordDate ?? "")}</span>
              <span>{String(record.summary ?? "")}</span>
              <b>{String(record.status ?? "")}</b>
              <button onClick={() => openDetail(String(record.recordId))}>详情</button>
              <button onClick={() => openTrace(String(record.recordId))}>追踪</button>
            </div>
          ))}
        </section>
        {detail && <pre className="json">{JSON.stringify(detail, null, 2)}</pre>}
        {trace && <pre className="json">{JSON.stringify(trace, null, 2)}</pre>}
      </main>
    </section>
  );
}
