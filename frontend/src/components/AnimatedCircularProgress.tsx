import { useEffect, useMemo, useState } from "react";
import NumberTicker from "./NumberTicker";
import { clamp } from "../utils/format";

type AnimatedCircularProgressProps = {
  value: number;
  max: number;
  size?: number;
  strokeWidth?: number;
  label: string;
  unit?: string;
};

export default function AnimatedCircularProgress({
  value,
  max,
  size = 120,
  strokeWidth = 10,
  label,
  unit
}: AnimatedCircularProgressProps) {
  const radius = useMemo(() => (size - strokeWidth) / 2, [size, strokeWidth]);
  const circumference = useMemo(() => 2 * Math.PI * radius, [radius]);
  const normalized = max > 0 ? clamp((value / max) * 100, 0, 100) : 0;
  const [offset, setOffset] = useState(circumference);

  useEffect(() => {
    const nextOffset = circumference - (normalized / 100) * circumference;
    const timer = window.setTimeout(() => {
      setOffset(nextOffset);
    }, 50);
    return () => window.clearTimeout(timer);
  }, [circumference, normalized]);

  return (
    <div
      className="progress-ring"
      style={{ width: size, height: size }}
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label={label}
    >
      <svg width={size} height={size}>
        <circle
          className="ring-bg"
          strokeWidth={strokeWidth}
          r={radius}
          cx={size / 2}
          cy={size / 2}
        />
        <circle
          className="ring-progress"
          strokeWidth={strokeWidth}
          r={radius}
          cx={size / 2}
          cy={size / 2}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="ring-content">
        <NumberTicker
          value={value}
          decimals={1}
          className="ring-value"
        />
        {unit && <span className="ring-unit">{unit}</span>}
        <span className="ring-label">{label}</span>
      </div>
    </div>
  );
}
