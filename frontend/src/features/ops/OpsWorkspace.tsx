import { useEffect, useState } from "react";
import { JsonPanel } from "../../components/ops/JsonPanel";
import { OpsTable } from "../../components/ops/OpsTable";
import { Pressable } from "../../components/ui/Pressable";
import { ensureOpsToken, fetchOpsDashboard, fetchOpsRecordDetail, fetchOpsRecords, fetchOpsRecordTrace, type OpsRecord } from "./api";

// 这个组件承载后台运维 PC 基础页面。
export function OpsWorkspace() {
  const [dashboard, setDashboard] = useState<Record<string, unknown>>({});
  const [records, setRecords] = useState<OpsRecord[]>([]);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [trace, setTrace] = useState<Record<string, unknown> | null>(null);
  const [busyLabel, setBusyLabel] = useState("");
  const [status, setStatus] = useState("");

  useEffect(() => {
    void runOpsAction("加载中", bootstrapOps);
  }, []);

  // 这个函数初始化后台人员 token 和后台列表。
  async function bootstrapOps() {
    await ensureOpsToken();
    const dashboardData = await fetchOpsDashboard();
    const recordItems = await fetchOpsRecords();
    setDashboard(dashboardData);
    setRecords(recordItems);
  }

  // 这个函数统一处理后台异步动作和错误提示。
  async function runOpsAction(label: string, action: () => Promise<void>) {
    setBusyLabel(label);
    setStatus("");
    try {
      await action();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "操作失败");
    } finally {
      setBusyLabel("");
    }
  }

  // 这个函数读取后台记录详情。
  function openDetail(recordId: string) {
    void runOpsAction("读取详情中", async () => {
      const data = await fetchOpsRecordDetail(recordId);
      setDetail(data);
      setTrace(null);
    });
  }

  // 这个函数读取记录追踪。
  function openTrace(recordId: string) {
    void runOpsAction("读取追踪中", async () => {
      const data = await fetchOpsRecordTrace(recordId);
      setTrace(data);
    });
  }

  return (
    <section className="ops-layout">
      <aside>
        <b>Ops</b>
        <Pressable onClick={() => void runOpsAction("刷新中", bootstrapOps)} disabled={Boolean(busyLabel)}>刷新</Pressable>
        {(busyLabel || status) && <p className="ops-status">{busyLabel || status}</p>}
      </aside>
      <main>
        <section className="summary">
          <div><span>今日记录</span><b>{String(dashboard.todayRecordCount ?? 0)}</b></div>
          <div><span>待反馈</span><b>{String(dashboard.pendingFeedbackCount ?? 0)}</b></div>
          <div><span>异常</span><b>{String(dashboard.abnormalCount ?? 0)}</b></div>
        </section>
        <OpsTable records={records} busy={Boolean(busyLabel)} onDetail={openDetail} onTrace={openTrace} />
        <JsonPanel title="记录详情" data={detail} />
        <JsonPanel title="追踪信息" data={trace} />
      </main>
    </section>
  );
}
