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
  onDismiss: (item: NotificationItem) => void;
};

export default function NotificationTray({
  items,
  onSelect,
  onDismiss
}: NotificationTrayProps) {
  if (items.length === 0) return null;

  return (
    <div className="notification-tray" aria-live="polite">
      <AnimatedList
        items={items}
        getKey={(item) => item.id}
        renderItem={(item) => (
          <div
            className="notification-card"
            role="button"
            tabIndex={0}
            onClick={() => onSelect(item)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelect(item);
              }
            }}
          >
            <button
              type="button"
              className="notification-dismiss"
              aria-label="Dismiss notification"
              onClick={(event) => {
                event.stopPropagation();
                onDismiss(item);
              }}
            >
              ×
            </button>
            <div className="notification-title">Incident detected</div>
            <div className="notification-message">{item.message}</div>
            <div className="notification-meta">
              <span>Tick {item.tick}</span>
              <span>{formatTime(item.ts)}</span>
            </div>
          </div>
        )}
      />
    </div>
  );
}
