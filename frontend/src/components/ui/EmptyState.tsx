interface EmptyStateProps {
  title: string;
  description?: string;
}

// 这个组件统一空数据占位。
export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <section className="empty-state">
      <div className="empty-state__mark" aria-hidden="true">·</div>
      <h2>{title}</h2>
      {description && <p>{description}</p>}
    </section>
  );
}
