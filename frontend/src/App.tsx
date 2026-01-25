import { useMemo, useState } from "react";
import { useSentra } from "./state/useSentra";
import type {
  EventRecord,
  FaultType,
  ServerId,
  ServerState,
  WorldState
} from "./types";

const serverIds: ServerId[] = ["S1", "S2", "S3"];

const defaultServer: ServerState = {
  load: 0,
  temp: 0,
  error_rate: 0,
  power: 0,
  health: 100,
  cooling: false
};

const fallbackState: WorldState = {
  tick: 0,
  incoming_traffic: 0,
  autonomy_enabled: false,
  servers: {
    S1: defaultServer,
    S2: defaultServer,
    S3: defaultServer
  }
};

const faultOptions: { value: FaultType; label: string }[] = [
  { value: "overheat", label: "Overheat" },
  { value: "hardware_fail", label: "Hardware fail" },
  { value: "network_spike", label: "Network spike" }
];

function isIncident(server: ServerState) {
  return server.temp > 80 || server.error_rate > 5 || server.health < 60;
}

function formatNumber(value: number, digits = 1) {
  return Number.isFinite(value) ? value.toFixed(digits) : "-";
}

function formatPercent(value: number) {
  return `${formatNumber(value, 1)}%`;
}

function formatTemp(value: number) {
  return `${formatNumber(value, 1)} C`;
}

function formatPower(value: number) {
  return `${formatNumber(value, 0)} W`;
}

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  }).format(date);
}

function normalizePayload(payload: EventRecord["payload"]) {
  const raw = payload as unknown;
  if (!raw) return null;
  if (typeof raw === "string") {
    try {
      return JSON.parse(raw) as Record<string, unknown>;
    } catch {
      return { value: raw } as Record<string, unknown>;
    }
  }
  if (typeof raw === "object") {
    return raw as Record<string, unknown>;
  }
  return { value: raw } as Record<string, unknown>;
}

function isAiPayload(payload: Record<string, unknown> | null) {
  if (!payload) return false;
  return (
    Array.isArray(payload.root_causes) &&
    Array.isArray(payload.recommended_actions) &&
    Array.isArray(payload.risks) &&
    Array.isArray(payload.rollback_conditions)
  );
}

function renderPayload(event: EventRecord) {
  const payload = normalizePayload(event.payload);
  if (!payload) return null;

  if (event.type === "ai" && isAiPayload(payload)) {
    return (
      <div className="payload-grid">
        <div>
          <div className="payload-label">Root causes</div>
          <ul>
            {(payload.root_causes as string[]).map((item, index) => (
              <li key={`root-${index}`}>{item}</li>
            ))}
          </ul>
        </div>
        <div>
          <div className="payload-label">Actions</div>
          <ul>
            {(payload.recommended_actions as string[]).map((item, index) => (
              <li key={`action-${index}`}>{item}</li>
            ))}
          </ul>
        </div>
        <div>
          <div className="payload-label">Risks</div>
          <ul>
            {(payload.risks as string[]).map((item, index) => (
              <li key={`risk-${index}`}>{item}</li>
            ))}
          </ul>
        </div>
        <div>
          <div className="payload-label">Rollback</div>
          <ul>
            {(payload.rollback_conditions as string[]).map((item, index) => (
              <li key={`rollback-${index}`}>{item}</li>
            ))}
          </ul>
        </div>
      </div>
    );
  }

  const entries = Object.entries(payload);
  return (
    <div className="payload-rows">
      {entries.map(([key, value]) => (
        <div className="payload-row" key={key}>
          <span>{key}</span>
          <span>{typeof value === "string" ? value : JSON.stringify(value)}</span>
        </div>
      ))}
    </div>
  );
}

function MetricBar({
  value,
  max,
  tone,
  label
}: {
  value: number;
  max: number;
  tone: string;
  label: string;
}) {
  const percent = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div
      className="metric-bar"
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label={label}
    >
      <div className={`metric-fill ${tone}`} style={{ width: `${percent}%` }} />
    </div>
  );
}

export default function App() {
  const {
    state,
    events,
    loading,
    error,
    busy,
    lastUpdated,
    advanceTick,
    toggleAutonomy,
    injectFault,
    reset
  } = useSentra();

  const [tickSteps, setTickSteps] = useState(1);
  const [faultType, setFaultType] = useState<FaultType>("overheat");
  const [faultTarget, setFaultTarget] = useState<ServerId>("S1");
  const [resetEvents, setResetEvents] = useState(true);

  const displayState = state ?? fallbackState;
  const incidentCount = useMemo(() => {
    return serverIds.filter((id) => isIncident(displayState.servers[id])).length;
  }, [displayState.servers]);

  const lastEvent = events[events.length - 1];
  const connectionLabel = loading
    ? "Connecting"
    : error
      ? "Degraded"
      : "Live";

  return (
    <div className="app-shell">
      <header className="top-bar">
        <div className="title-block">
          <div className="eyebrow">SENTRA</div>
          <h1>Autonomous Data Center Console</h1>
          <p>
            Monitor S1-S3 in real time, inject faults, and observe the autonomous
            response loop.
          </p>
        </div>
        <div className="status-panel">
          <div className="status-pill">
            <span className={`dot ${error ? "dot-warn" : "dot-ok"}`} />
            <span>{connectionLabel}</span>
          </div>
          <div className="status-stack">
            <div className="status-item">
              <span>Tick</span>
              <strong>{displayState.tick}</strong>
            </div>
            <div className="status-item">
              <span>Incidents</span>
              <strong>{incidentCount}</strong>
            </div>
            <div className="status-item">
              <span>Last update</span>
              <strong>{lastUpdated ? lastUpdated.toLocaleTimeString() : "-"}</strong>
            </div>
          </div>
        </div>
      </header>

      {error && (
        <div className="alert">
          <strong>API issue:</strong> {error}
        </div>
      )}

      <section className="overview-grid">
        <div className="card hero">
          <div>
            <div className="card-title">System pulse</div>
            <div className="hero-value">{displayState.incoming_traffic}</div>
            <div className="hero-label">Incoming traffic</div>
          </div>
          <div className="hero-meta">
            <div className="meta-row">
              <span>Autonomy</span>
              <strong>{displayState.autonomy_enabled ? "Enabled" : "Standby"}</strong>
            </div>
            <div className="meta-row">
              <span>Cooling engaged</span>
              <strong>
                {serverIds.filter((id) => displayState.servers[id].cooling).length}/3
              </strong>
            </div>
            <div className="meta-row">
              <span>Last event</span>
              <strong>{lastEvent ? `${lastEvent.type} @ ${lastEvent.tick}` : "-"}</strong>
            </div>
          </div>
        </div>

        <div className="card controls">
          <div className="card-title">Control deck</div>
          <div className="controls-grid">
            <div className="control-block">
              <label htmlFor="tickSteps">Advance ticks</label>
              <div className="control-row">
                <input
                  id="tickSteps"
                  type="number"
                  min={1}
                  max={60}
                  value={tickSteps}
                  onChange={(event) => {
                    const value = Number(event.target.value);
                    const next = Number.isNaN(value) ? 1 : Math.min(60, Math.max(1, value));
                    setTickSteps(next);
                  }}
                />
                <button
                  type="button"
                  className="button primary"
                  onClick={() => advanceTick(tickSteps)}
                  disabled={busy}
                >
                  Run
                </button>
              </div>
            </div>

            <div className="control-block">
              <label>Autonomy</label>
              <div className="control-row">
                <button
                  type="button"
                  role="switch"
                  aria-checked={displayState.autonomy_enabled}
                  className={`toggle ${displayState.autonomy_enabled ? "on" : "off"}`}
                  onClick={() => toggleAutonomy(!displayState.autonomy_enabled)}
                  disabled={busy}
                >
                  <span className="toggle-thumb" />
                  <span>{displayState.autonomy_enabled ? "Enabled" : "Disabled"}</span>
                </button>
              </div>
            </div>

            <div className="control-block">
              <label>Inject fault</label>
              <div className="control-row">
                <select
                  value={faultType}
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
                  onClick={() => injectFault(faultType, faultTarget)}
                  disabled={busy}
                >
                  Inject
                </button>
              </div>
            </div>

            <div className="control-block">
              <label>Reset world</label>
              <div className="control-row">
                <label className="inline-check">
                  <input
                    type="checkbox"
                    checked={resetEvents}
                    onChange={(event) => setResetEvents(event.target.checked)}
                  />
                  Clear events
                </label>
                <button
                  type="button"
                  className="button outline"
                  onClick={() => reset(resetEvents)}
                  disabled={busy}
                >
                  Reset
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section>
        <div className="section-title">Server fleet</div>
        <div className="server-grid">
          {serverIds.map((id) => {
            const server = displayState.servers[id];
            const incident = isIncident(server);
            return (
              <div className={`card server ${incident ? "incident" : ""}`} key={id}>
                <div className="server-head">
                  <div>
                    <div className="card-title">{id}</div>
                    <div className="server-status">
                      {incident ? "Incident" : "Nominal"}
                    </div>
                  </div>
                  <div className={`cooling ${server.cooling ? "on" : "off"}`}>
                    Cooling {server.cooling ? "On" : "Off"}
                  </div>
                </div>

                <div className="metric">
                  <div className="metric-row">
                    <span>Load</span>
                    <strong>{formatPercent(server.load)}</strong>
                  </div>
                  <MetricBar value={server.load} max={100} tone="tone-ok" label={`${id} load`} />
                </div>

                <div className="metric">
                  <div className="metric-row">
                    <span>Temperature</span>
                    <strong>{formatTemp(server.temp)}</strong>
                  </div>
                  <MetricBar value={server.temp} max={100} tone="tone-warn" label={`${id} temperature`} />
                </div>

                <div className="metric">
                  <div className="metric-row">
                    <span>Error rate</span>
                    <strong>{formatPercent(server.error_rate)}</strong>
                  </div>
                  <MetricBar value={server.error_rate} max={20} tone="tone-danger" label={`${id} error rate`} />
                </div>

                <div className="metric">
                  <div className="metric-row">
                    <span>Health</span>
                    <strong>{formatPercent(server.health)}</strong>
                  </div>
                  <MetricBar value={server.health} max={100} tone="tone-ok" label={`${id} health`} />
                </div>

                <div className="metric">
                  <div className="metric-row">
                    <span>Power</span>
                    <strong>{formatPower(server.power)}</strong>
                  </div>
                  <MetricBar value={server.power} max={300} tone="tone-ink" label={`${id} power`} />
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="timeline">
        <div className="section-title">Event timeline</div>
        <div className="timeline-list">
          {events.length === 0 ? (
            <div className="empty">No events yet. Inject a fault to begin.</div>
          ) : (
            [...events].reverse().slice(0, 40).map((event) => (
              <div className={`event event-${event.type}`} key={event.id}>
                <div className="event-head">
                  <span className={`badge badge-${event.type}`}>{event.type}</span>
                  <span className="event-message">{event.message}</span>
                </div>
                <div className="event-meta">
                  <span>Tick {event.tick}</span>
                  <span>{formatTime(event.ts)}</span>
                </div>
                {renderPayload(event)}
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
