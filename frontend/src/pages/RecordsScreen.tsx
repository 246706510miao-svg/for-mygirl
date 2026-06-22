import { useState } from "react";
import { BottomSheet } from "../components/ui/BottomSheet";
import { EmptyState } from "../components/ui/EmptyState";
import { FieldSelector } from "../components/records/FieldSelector";
import { RecordCard } from "../components/records/RecordCard";
import type { FieldKey } from "../components/records/recordFields";
import { GlassScreen } from "../components/layout/GlassScreen";
import { MobileAppShell } from "../components/layout/MobileAppShell";
import { ScreenHeader } from "../components/layout/ScreenHeader";
import type { RecordDisplay } from "../shared/types/api";

interface RecordsScreenProps {
  title: string;
  records: RecordDisplay[];
  selectedFields: FieldKey[];
  onFieldsChange: (value: FieldKey[]) => void;
  onBack: () => void;
}

// 这个页面展示用户最近记录和字段选择。
export function RecordsScreen({ title, records, selectedFields, onFieldsChange, onBack }: RecordsScreenProps) {
  const [selectedRecord, setSelectedRecord] = useState<RecordDisplay | null>(null);

  return (
    <MobileAppShell>
      <GlassScreen>
        <ScreenHeader title={title} onBack={onBack} />
        <FieldSelector selected={selectedFields} onChange={onFieldsChange} />
        <section className="record-list">
          {records.map((record) => (
            <RecordCard key={record.recordId} record={record} fields={selectedFields} onOpen={() => setSelectedRecord(record)} />
          ))}
          {records.length === 0 && <EmptyState title="No records yet" description="写下第一条记录后会在这里出现。" />}
        </section>
        <BottomSheet open={Boolean(selectedRecord)} onOpenChange={(open) => !open && setSelectedRecord(null)} title={selectedRecord?.title || "记录详情"}>
          {selectedRecord && (
            <article className="record-detail">
              <span>{selectedRecord.recordDate || "-"}</span>
              <h2>{selectedRecord.title}</h2>
              <p>{selectedRecord.summary}</p>
              <strong>{selectedRecord.managerScore ?? selectedRecord.score ?? "-"} 分</strong>
              <div>
                <b>管理员评论</b>
                <p>{selectedRecord.managerComment || selectedRecord.boundComment?.content || "暂无评论"}</p>
              </div>
            </article>
          )}
        </BottomSheet>
      </GlassScreen>
    </MobileAppShell>
  );
}
