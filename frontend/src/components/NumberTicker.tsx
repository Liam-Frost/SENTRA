import { useEffect, useRef, useState } from "react";

type NumberTickerProps = {
  value: number;
  decimals?: number;
  duration?: number;
  format?: (value: number) => string;
  className?: string;
};

const DEFAULT_DURATION = 900;

export default function NumberTicker({
  value,
  decimals = 0,
  duration = DEFAULT_DURATION,
  format,
  className
}: NumberTickerProps) {
  const previousRef = useRef(value);
  const [displayValue, setDisplayValue] = useState(value);

  useEffect(() => {
    const from = previousRef.current;
    const to = value;
    previousRef.current = value;

    if (!Number.isFinite(from) || !Number.isFinite(to) || from === to) {
      setDisplayValue(value);
      return;
    }

    let frame = 0;
    const start = performance.now();

    const step = (now: number) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      const next = from + (to - from) * eased;
      setDisplayValue(next);
      if (progress < 1) {
        frame = requestAnimationFrame(step);
      }
    };

    frame = requestAnimationFrame(step);

    return () => {
      cancelAnimationFrame(frame);
    };
  }, [duration, value]);

  const safeDecimals = Math.max(0, Math.min(20, decimals));
  const output = format
    ? format(displayValue)
    : displayValue.toFixed(safeDecimals);

  return <span className={className}>{output}</span>;
}
