import type { OpsRecord } from "../../features/ops/api";
import { EmptyState } from "../ui/EmptyState";
import { Pressable } from "../ui/Pressable";

interface OpsTableProps {
  records: OpsRecord[];
  busy: boolean;
  onDetail: (recordId: string) => void;
  onTrace: (recordId: string) => void;
}

// 这个组件保留 Ops 的桌面高密度表格形态。
export function OpsTable({ records, busy, onDetail, onTrace }: OpsTableProps) {
  if (records.length === 0) {
    return <EmptyState title="暂无后台记录" />;
  }
  return (
    <section className="ops-table">
      {records.map((record) => {
        const id = String(record.recordId);
        return (
          <div className="ops-row" key={id}>
            <span>{String(record.recordDate ?? "")}</span>
            <span>{String(record.summary ?? "")}</span>
            <b>{String(record.status ?? "")}</b>
            <Pressable onClick={() => onDetail(id)} disabled={busy}>详情</Pressable>
            <Pressable onClick={() => onTrace(id)} disabled={busy}>追踪</Pressable>
          </div>
        );
      })}
    </section>
  );
}
