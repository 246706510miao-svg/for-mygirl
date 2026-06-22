import { InlineCommentForm } from "../components/admin/InlineCommentForm";
import { EmptyState } from "../components/ui/EmptyState";
import { RecordCard } from "../components/records/RecordCard";
import { GlassScreen } from "../components/layout/GlassScreen";
import { MobileAppShell } from "../components/layout/MobileAppShell";
import { ScreenHeader } from "../components/layout/ScreenHeader";
import type { RecordDisplay } from "../shared/types/api";

interface AdminRecordsScreenProps {
  records: RecordDisplay[];
  busy: boolean;
  onBack: () => void;
  onSaveComment: (recordId: string, content: string, score: number) => Promise<unknown> | unknown;
}

const adminFields = ["recordDate", "summary", "score"] as const;

// 这个页面让绑定管理员评论和打分。
export function AdminRecordsScreen({ records, busy, onBack, onSaveComment }: AdminRecordsScreenProps) {
  return (
    <MobileAppShell>
      <GlassScreen>
        <ScreenHeader title="Admin Records" onBack={onBack} />
        <section className="record-list">
          {records.map((record) => (
            <RecordCard key={record.recordId} record={record} fields={[...adminFields]}>
              <InlineCommentForm
                initialComment={record.managerComment || ""}
                initialScore={record.managerScore ?? record.score ?? 80}
                busy={busy}
                onSave={(content, score) => onSaveComment(record.recordId, content, score)}
              />
            </RecordCard>
          ))}
          {records.length === 0 && <EmptyState title="暂无绑定用户记录" />}
        </section>
      </GlassScreen>
    </MobileAppShell>
  );
}
