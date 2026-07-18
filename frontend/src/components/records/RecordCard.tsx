import type { ReactNode } from "react";
import { motion } from "motion/react";
import type { RecordDisplay } from "../../shared/types/api";
import { Pressable } from "../ui/Pressable";
import { fieldLabels, type FieldKey } from "./recordFields";

interface RecordCardProps {
  record: RecordDisplay;
  fields: FieldKey[];
  commentAuthorName?: string;
  children?: ReactNode;
  onOpen?: () => void;
}

function RecordContent({ record, fields, commentAuthorName, children }: RecordCardProps) {
  const authorName = record.boundComment?.authorDisplayName?.trim() || commentAuthorName?.trim() || "TA";

  return (
    <>
      <div className="record-card__fields">
        {fields.map((field) => (
          <div key={field}>
            <span>{fieldLabels[field]}</span>
            <b>{String(record[field] ?? "-")}</b>
          </div>
        ))}
      </div>
      <div className="record-card__comment">
        <span>{authorName}评论</span>
        <p>{record.managerComment || record.boundComment?.content || "暂无评论"}</p>
      </div>
      {children}
    </>
  );
}

// 这个组件渲染最近记录卡片，用户列表可点击展开详情。
export function RecordCard(props: RecordCardProps) {
  const { record, onOpen } = props;
  if (onOpen) {
    return (
      <Pressable
        className="record-card record-card--pressable"
        onClick={(event) => {
          event.currentTarget.blur();
          onOpen();
        }}
        aria-haspopup="dialog"
        aria-label={`查看记录 ${record.title || record.recordId}`}
      >
        <RecordContent {...props} />
      </Pressable>
    );
  }
  return (
    <motion.article className="record-card" layout>
      <RecordContent {...props} />
    </motion.article>
  );
}
