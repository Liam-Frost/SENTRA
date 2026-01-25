import type { ReactNode } from "react";

type AnimatedListProps<T> = {
  items: T[];
  getKey: (item: T) => string | number;
  renderItem: (item: T, index: number) => ReactNode;
  className?: string;
  itemClassName?: string;
};

export default function AnimatedList<T>({
  items,
  getKey,
  renderItem,
  className,
  itemClassName
}: AnimatedListProps<T>) {
  return (
    <div className={`animated-list ${className ?? ""}`.trim()}>
      {items.map((item, index) => (
        <div
          key={getKey(item)}
          className={`animated-list-item ${itemClassName ?? ""}`.trim()}
          style={{ animationDelay: `${Math.min(index, 12) * 60}ms` }}
        >
          {renderItem(item, index)}
        </div>
      ))}
    </div>
  );
}
