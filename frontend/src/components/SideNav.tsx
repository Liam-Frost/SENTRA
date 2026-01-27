import ThemeToggle, { type ThemeMode } from "./ThemeToggle";
import type { RouteKey } from "./DockNav";

type SideNavProps = {
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
    key: "fleet",
    label: "Server fleet",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 4h16v6H4V4zm0 10h16v6H4v-6zm3-7h3v2H7V7zm0 10h3v2H7v-2z" />
      </svg>
    )
  },
  {
    key: "incidents",
    label: "Incidents",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 9v4M12 17h.01M10.3 4.6l-7.3 13A2 2 0 0 0 4.7 21h14.6a2 2 0 0 0 1.7-3.4l-7.3-13a2 2 0 0 0-3.4 0z" />
      </svg>
    )
  },
  {
    key: "policies",
    label: "Policies",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 6h16M7 6v12M17 18V6M4 18h16" />
        <path d="M10 10h6M10 14h6" />
      </svg>
    )
  },
  {
    key: "operations",
    label: "Operations",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 6h16v12H4z" />
        <path d="M8 10l2 2-2 2M12 14h4" />
      </svg>
    )
  },
  {
    key: "actions",
    label: "Actions",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
      </svg>
    )
  }
];

const toolsIcon = (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M4 7h16M4 17h16M9 7v10M15 7v10" />
  </svg>
);

export default function SideNav({
  active,
  onNavigate,
  toolsOpen,
  onToggleTools,
  themeMode,
  onThemeModeChange
}: SideNavProps) {
  return (
    <nav className="side-nav" aria-label="Primary">
      <div className="side-nav-items">
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
      </div>

      <div className="side-nav-divider" role="presentation" />

      <div className="side-nav-items">
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
    </nav>
  );
}
