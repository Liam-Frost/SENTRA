import { useEffect, useState } from "react";
import ThemeToggle, { type ThemeMode } from "./ThemeToggle";

export type RouteKey = "dashboard" | "fleet" | "events";

type DockNavProps = {
  active: RouteKey;
  onNavigate: (route: RouteKey) => void;
  toolsOpen: boolean;
  onToggleTools: () => void;
  themeMode: ThemeMode;
  onThemeModeChange: (mode: ThemeMode) => void;
};

const items: { key: RouteKey; label: string; icon: JSX.Element }[] = [
  {
    key: "dashboard",
    label: "Dashboard",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3 13h7V3H3v10zm11 8h7V11h-7v10zM3 21h7v-6H3v6zm11-8h7V3h-7v10z" />
      </svg>
    )
  },
  {
    key: "events",
    label: "Event timeline",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M6 4v16M6 8h10M6 12h10M6 16h10M18 12l2 2 3-3" />
      </svg>
    )
  },
  {
    key: "fleet",
    label: "Server fleet",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 4h16v6H4V4zm0 10h16v6H4v-6zm3-7h3v2H7V7zm0 10h3v2H7v-2z" />
      </svg>
    )
  }
];

const toolsIcon = (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M4 7h16M4 17h16M9 7v10M15 7v10" />
  </svg>
);

const timeFormatter = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  minute: "2-digit",
  hour12: false
});

function formatTime(date: Date) {
  return timeFormatter.format(date);
}

export default function DockNav({
  active,
  onNavigate,
  toolsOpen,
  onToggleTools,
  themeMode,
  onThemeModeChange
}: DockNavProps) {
  const [time, setTime] = useState(() => formatTime(new Date()));

  useEffect(() => {
    const update = () => setTime(formatTime(new Date()));
    // Check every 10 seconds to catch minute changes promptly
    const interval = window.setInterval(update, 10000);
    return () => window.clearInterval(interval);
  }, []);

  return (
    <nav className="dock" aria-label="Primary">
      <div className="dock-items">
        {items.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`dock-item ${active === item.key ? "active" : ""}`}
            onClick={() => onNavigate(item.key)}
            aria-label={item.label}
            aria-current={active === item.key ? "page" : undefined}
          >
            <span className="dock-icon" aria-hidden="true">
              {item.icon}
            </span>
            <span className="dock-label">{item.label}</span>
          </button>
        ))}

        <button
          type="button"
          className={`dock-item ${toolsOpen ? "active" : ""}`}
          onClick={onToggleTools}
          aria-label={toolsOpen ? "Close tools" : "Open tools"}
          aria-pressed={toolsOpen}
        >
          <span className="dock-icon" aria-hidden="true">
            {toolsIcon}
          </span>
          <span className="dock-label">{toolsOpen ? "Close tools" : "Open tools"}</span>
        </button>

        <ThemeToggle mode={themeMode} onModeChange={onThemeModeChange} />
      </div>
      <div className="dock-divider" role="presentation" />
      <div className="dock-time" aria-label="Current time">
        {time}
      </div>
    </nav>
  );
}
