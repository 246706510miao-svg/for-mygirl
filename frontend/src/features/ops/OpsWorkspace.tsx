import { useEffect, useState } from "react";
import { fetchOpsDashboard, fetchOpsRecordDetail, fetchOpsRecords, fetchOpsRecordTrace, loginOpsUser, type OpsRecord } from "./api";

// 这个组件承载后台运维 PC 基础页面。
export function OpsWorkspace() {
  const [dashboard, setDashboard] = useState<Record<string, unknown>>({});
  const [records, setRecords] = useState<OpsRecord[]>([]);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [trace, setTrace] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    void bootstrapOps();
  }, []);

  // 这个函数初始化后台人员 token 和后台列表。
  async function bootstrapOps() {
    await loginOpsUser();
    const dashboardData = await fetchOpsDashboard();
    const recordItems = await fetchOpsRecords();
    setDashboard(dashboardData);
    setRecords(recordItems);
  }

  // 这个函数读取后台记录详情。
  async function openDetail(recordId: string) {
    const data = await fetchOpsRecordDetail(recordId);
    setDetail(data);
    setTrace(null);
  }

  // 这个函数读取记录追踪。
  async function openTrace(recordId: string) {
    const data = await fetchOpsRecordTrace(recordId);
    setTrace(data);
  }

  return (
    <section className="ops-layout">
      <aside>
        <b>Ops</b>
        <button onClick={bootstrapOps}>刷新</button>
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
