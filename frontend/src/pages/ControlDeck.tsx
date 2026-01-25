import { useState } from "react";
import type { FaultType, ServerId, WorldState } from "../types";

type ControlDeckProps = {
  state: WorldState;
  busy: boolean;
  onAdvanceTick: (steps?: number) => Promise<void>;
  onToggleAutonomy: (enabled: boolean) => Promise<void>;
  onInjectFault: (type: FaultType, target: ServerId) => Promise<void>;
  onReset: (resetEvents: boolean) => Promise<void>;
};

const faultOptions: { value: FaultType; label: string }[] = [
  { value: "overheat", label: "Overheat" },
  { value: "hardware_fail", label: "Hardware fail" },
  { value: "network_spike", label: "Network spike" }
];

const serverIds: ServerId[] = ["S1", "S2", "S3"];

export default function ControlDeck({
  state,
  busy,
  onAdvanceTick,
  onToggleAutonomy,
  onInjectFault,
  onReset
}: ControlDeckProps) {
  const [tickSteps, setTickSteps] = useState(1);
  const [faultType, setFaultType] = useState<FaultType>("overheat");
  const [faultTarget, setFaultTarget] = useState<ServerId>("S1");
  const [resetEvents, setResetEvents] = useState(true);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-eyebrow">Simulation tools</div>
          <h2 className="page-title">Control deck</h2>
          <p className="page-description">
            Internal tools for advancing the simulation and injecting faults.
          </p>
        </div>
        <div className="page-status">
          <div className="status-chip">
            Autonomy {state.autonomy_enabled ? "Enabled" : "Standby"}
          </div>
        </div>
      </div>

      <div className="controls-page">
        <div className="card control-panel">
          <div className="card-title">Simulation ticks</div>
          <div className="control-row">
            <input
              id="tickSteps"
              type="number"
              min={1}
              max={60}
              value={tickSteps}
              aria-label="Number of ticks to advance"
              onChange={(event) => {
                const value = Number(event.target.value);
                const next = Number.isNaN(value) ? 1 : Math.min(60, Math.max(1, value));
                setTickSteps(next);
              }}
            />
            <button
              type="button"
              className="button primary"
              onClick={() => onAdvanceTick(tickSteps)}
              disabled={busy}
            >
              Advance
            </button>
          </div>
          <div className="control-hint">1 tick = 1 second of simulated time.</div>
        </div>

        <div className="card control-panel">
          <div className="card-title">Autonomy loop</div>
          <div className="control-row">
            <button
              type="button"
              role="switch"
              aria-checked={state.autonomy_enabled}
              className={`toggle ${state.autonomy_enabled ? "on" : "off"}`}
              onClick={() => onToggleAutonomy(!state.autonomy_enabled)}
              disabled={busy}
            >
              <span className="toggle-thumb" />
              <span>{state.autonomy_enabled ? "Enabled" : "Disabled"}</span>
            </button>
          </div>
          <div className="control-hint">Autonomy executes safe actions automatically.</div>
        </div>

        <div className="card control-panel">
          <div className="card-title">Fault injection</div>
          <div className="control-row">
            <select
              value={faultType}
              aria-label="Fault type"
              onChange={(event) => setFaultType(event.target.value as FaultType)}
            >
              {faultOptions.map((option) => (
                <option value={option.value} key={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <select
              value={faultTarget}
              aria-label="Target server"
              onChange={(event) => setFaultTarget(event.target.value as ServerId)}
            >
              {serverIds.map((id) => (
                <option value={id} key={id}>
                  {id}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="button ghost"
              onClick={() => onInjectFault(faultType, faultTarget)}
              disabled={busy}
            >
              Inject fault
            </button>
          </div>
          <div className="control-hint">Use faults to demonstrate recovery.</div>
        </div>

        <div className="card control-panel">
          <div className="card-title">Reset world</div>
          <div className="reset-row">
            <label className="inline-check">
              <input
                type="checkbox"
                checked={resetEvents}
                onChange={(event) => setResetEvents(event.target.checked)}
              />
              Clear event timeline
            </label>
            <button
              type="button"
              className="button outline"
              onClick={() => onReset(resetEvents)}
              disabled={busy}
            >
              Reset simulation
            </button>
          </div>
          <div className="control-hint">Restores baseline state for repeatable demos.</div>
        </div>
      </div>
    </div>
  );
}
