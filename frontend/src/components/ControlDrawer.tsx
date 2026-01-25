import { useEffect } from "react";

import type { FaultType, ServerId, WorldState } from "../types";
import type { RealtimeState } from "../api/sentra";
import ControlDeck from "../pages/ControlDeck";

type ControlDrawerProps = {
  open: boolean;
  state: WorldState;
  busy: boolean;
  realtime: RealtimeState;
  onClose: () => void;
  onAdvanceTick: (steps?: number) => Promise<void>;
  onToggleAutonomy: (enabled: boolean) => Promise<void>;
  onInjectFault: (type: FaultType, target: ServerId) => Promise<void>;
  onReset: (resetEvents: boolean) => Promise<void>;
  onSetRealtime: (enabled: boolean, hz?: number) => Promise<void>;
};

export default function ControlDrawer({
  open,
  state,
  busy,
  realtime,
  onClose,
  onAdvanceTick,
  onToggleAutonomy,
  onInjectFault,
  onReset,
  onSetRealtime
}: ControlDrawerProps) {
  useEffect(() => {
    if (!open) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose, open]);

  return (
    <div className={`control-drawer ${open ? "open" : ""}`.trim()} aria-hidden={!open}>
      <button
        type="button"
        className="control-drawer-backdrop"
        aria-label="Close tools"
        onClick={onClose}
      />
      <aside
        className="control-drawer-panel"
        role="dialog"
        aria-label="Control deck"
        aria-modal="true"
      >
        <div className="control-drawer-header">
          <div>
            <div className="control-drawer-eyebrow">Simulation tools</div>
            <div className="control-drawer-title">Control deck</div>
          </div>
          <button
            type="button"
            className="control-drawer-close"
            aria-label="Close tools"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <div className="control-drawer-body">
          <ControlDeck
            variant="drawer"
            state={state}
            busy={busy}
            realtime={realtime}
            onAdvanceTick={onAdvanceTick}
            onToggleAutonomy={onToggleAutonomy}
            onInjectFault={onInjectFault}
            onReset={onReset}
            onSetRealtime={onSetRealtime}
          />
        </div>
      </aside>
    </div>
  );
}
