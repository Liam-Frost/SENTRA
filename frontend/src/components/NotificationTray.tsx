import AnimatedList from "./AnimatedList";
import { formatTime } from "../utils/format";

export type NotificationItem = {
  id: number;
  message: string;
  tick: number;
  ts: string;
};

type NotificationTrayProps = {
  items: NotificationItem[];
  onSelect: (item: NotificationItem) => void;
};

export default function NotificationTray({ items, onSelect }: NotificationTrayProps) {
  if (items.length === 0) return null;

  return (
    <div className="notification-tray" aria-live="polite">
      <AnimatedList
        items={items}
        getKey={(item) => item.id}
        renderItem={(item) => (
          <button
            type="button"
            className="notification-card"
            onClick={() => onSelect(item)}
          >
            <div className="notification-title">Incident detected</div>
            <div className="notification-message">{item.message}</div>
            <div className="notification-meta">
              <span>Tick {item.tick}</span>
              <span>{formatTime(item.ts)}</span>
            </div>
          </button>
        )}
      />
    </div>
  );
}
