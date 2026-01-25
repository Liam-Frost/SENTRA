export type ThemeMode = "light" | "dark" | "system";

type ThemeToggleProps = {
  mode: ThemeMode;
  onModeChange: (mode: ThemeMode) => void;
};

const modes: ThemeMode[] = ["light", "dark", "system"];

const icons: Record<ThemeMode, JSX.Element> = {
  light: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1" />
    </svg>
  ),
  dark: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20.4 15.4a8 8 0 1 1-11.8-11 7 7 0 0 0 11.8 11z" />
    </svg>
  ),
  system: (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="4" y="6" width="16" height="10" rx="2" />
      <path d="M9 20h6" />
    </svg>
  )
};

export default function ThemeToggle({ mode, onModeChange }: ThemeToggleProps) {
  const handleClick = () => {
    const index = modes.indexOf(mode);
    const next = modes[(index + 1) % modes.length];
    onModeChange(next);
  };

  return (
    <button
      type="button"
      className="dock-item theme-item"
      aria-label={`Theme mode: ${mode}`}
      onClick={handleClick}
    >
      <span className="dock-icon" aria-hidden="true">
        {icons[mode]}
      </span>
      <span className="dock-label">Theme: {mode}</span>
    </button>
  );
}
