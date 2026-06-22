import type { ReactNode } from "react";

interface MetricLineProps {
  label: string;
  value: string | number;
  unit?: string;
  icon?: ReactNode;
}

// 这个组件展示积分或统计类关键数字。
export function MetricLine({ label, value, unit, icon }: MetricLineProps) {
  return (
    <section className="metric-line">
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        {unit && <small>{unit}</small>}
      </div>
      {icon && <div className="metric-line__icon">{icon}</div>}
    </section>
  );
}
