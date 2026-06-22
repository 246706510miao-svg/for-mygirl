interface JsonPanelProps {
  title: string;
  data: Record<string, unknown> | null;
}

// 这个组件展示 Ops 详情或追踪原始 JSON。
export function JsonPanel({ title, data }: JsonPanelProps) {
  if (!data) {
    return null;
  }
  return (
    <section className="json-panel">
      <h2>{title}</h2>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </section>
  );
}
