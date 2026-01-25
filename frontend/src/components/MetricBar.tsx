import { clamp } from "../utils/format";

type MetricBarProps = {
  value: number;
  max: number;
  tone: string;
  label: string;
};

export default function MetricBar({ value, max, tone, label }: MetricBarProps) {
  const percent = clamp((value / max) * 100, 0, 100);
  return (
    <div
      className="metric-bar"
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label={label}
    >
      <div className={`metric-fill ${tone}`} style={{ width: `${percent}%` }} />
    </div>
  );
}
