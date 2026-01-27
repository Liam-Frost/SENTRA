import { useEffect, useMemo, useRef, useState } from "react";

type VirtualListProps<T> = {
  header?: React.ReactNode;
  items: T[];
  itemHeight: number;
  overscan?: number;
  className?: string;
  getKey: (item: T, index: number) => string | number;
  renderItem: (item: T, index: number) => React.ReactNode;
};

export default function VirtualList<T>({
  header,
  items,
  itemHeight,
  overscan = 6,
  className,
  getKey,
  renderItem
}: VirtualListProps<T>) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const headerRef = useRef<HTMLDivElement | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(0);
  const [headerHeight, setHeaderHeight] = useState(0);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const update = () => {
      setViewportHeight(container.clientHeight);
    };

    update();

    const ro = new ResizeObserver(update);
    ro.observe(container);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!header) {
      setHeaderHeight(0);
      return;
    }
    const el = headerRef.current;
    if (!el) return;

    const update = () => setHeaderHeight(el.clientHeight);
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, [header]);

  const totalHeight = items.length * itemHeight;

  const range = useMemo(() => {
    if (items.length === 0 || viewportHeight <= 0) {
      return { start: 0, end: -1, offset: 0 };
    }

    const effectiveScrollTop = Math.max(0, scrollTop - headerHeight);
    const availableHeight = Math.max(0, viewportHeight - headerHeight);
    const start = Math.max(0, Math.floor(effectiveScrollTop / itemHeight) - overscan);
    const visibleCount = Math.ceil(availableHeight / itemHeight) + overscan * 2;
    const end = Math.min(items.length - 1, start + visibleCount);
    return { start, end, offset: start * itemHeight };
  }, [headerHeight, itemHeight, items.length, overscan, scrollTop, viewportHeight]);

  const visibleItems = range.end >= range.start ? items.slice(range.start, range.end + 1) : [];

  return (
    <div
      ref={containerRef}
      className={className}
      onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}
    >
      {header ? (
        <div ref={headerRef} className="virtual-list-header">
          {header}
        </div>
      ) : null}
      <div className="virtual-list-spacer" style={{ height: totalHeight }}>
        <div className="virtual-list-window" style={{ transform: `translateY(${range.offset}px)` }}>
          {visibleItems.map((item, idx) => {
            const absoluteIndex = range.start + idx;
            return (
              <div
                key={getKey(item, absoluteIndex)}
                className="virtual-list-item"
                style={{ height: itemHeight }}
              >
                {renderItem(item, absoluteIndex)}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
