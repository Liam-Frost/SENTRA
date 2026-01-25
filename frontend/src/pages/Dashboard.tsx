import NumberTicker from "../components/NumberTicker";
import AnimatedCircularProgress from "../components/AnimatedCircularProgress";
import AnimatedList from "../components/AnimatedList";
import EventCard from "../components/EventCard";
import MetricBar from "../components/MetricBar";
import type { EventRecord, ServerId, ServerState, WorldState } from "../types";
import { formatNumber, formatPercent, formatTemp } from "../utils/format";
import { getFleetStats } from "../utils/metrics";

type DashboardProps = {
  state: WorldState;
  events: EventRecord[];
  incidentCount: number;
  onOpenEvents: (eventId?: number) => void;
};

export default function Dashboard({
  state,
  events,
  incidentCount,
  onOpenEvents
}: DashboardProps) {
  const stats = getFleetStats(state);
  const recentEvents = [...events].reverse().slice(0, 3);
  const serverEntries = Object.entries(state.servers) as [ServerId, ServerState][];
  const totalLoad = serverEntries.reduce((sum, [, server]) => sum + server.load, 0);
  const loadSegments = serverEntries.map(([id, server]) => ({
    id,
    load: server.load,
    share: totalLoad > 0 ? (server.load / totalLoad) * 100 : 0,
    temp: server.temp,
    health: server.health
  }));

  const incidentTicks = events
    .filter((event) => event.type === "incident")
    .map((event) => event.tick);
  const lastIncidentTick = incidentTicks.length > 0 ? Math.max(...incidentTicks) : null;
  const stableTicks = lastIncidentTick === null ? state.tick : Math.max(0, state.tick - lastIncidentTick);

  const maxTempEntry = serverEntries.length > 0
    ? serverEntries.reduce(
        (max, [id, server]) => (server.temp > max.temp ? { id, temp: server.temp } : max),
        { id: serverEntries[0][0], temp: serverEntries[0][1].temp }
      )
    : { id: "S1" as ServerId, temp: 0 };
  const coolingUtilization = stats.serverCount > 0 ? (stats.coolingCount / stats.serverCount) * 100 : 0;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-eyebrow">Overview</div>
          <h2 className="page-title">Dashboard</h2>
          <p className="page-description">
            Live telemetry, health summary, and operational readiness across the
            micro data center.
          </p>
        </div>
        <div className="page-status">
          <div className="status-chip">
            Autonomy {state.autonomy_enabled ? "Enabled" : "Standby"}
          </div>
          <div className="status-chip">Incidents {incidentCount}</div>
          <div className="status-chip">Cooling {stats.coolingCount}/3</div>
        </div>
      </div>

      <section className="stats-grid">
        <div className="card stat-card stat-hero span-2x1">
          <div className="card-title">Incoming traffic</div>
          <div className="stat-value">
            <NumberTicker value={state.incoming_traffic} />
          </div>
          <div className="stat-sub">Requests / second</div>
          <div className="stat-row">
            <span>System tick</span>
            <NumberTicker value={state.tick} className="stat-inline" />
          </div>
        </div>

        <div className="card stat-card span-2x1 fleet-averages">
          <div className="card-title">Fleet averages</div>
          <div className="ring-grid">
            <AnimatedCircularProgress
              value={stats.avgLoad}
              max={100}
              label="Avg load"
              unit="%"
              size={140}
              strokeWidth={12}
            />
            <AnimatedCircularProgress
              value={stats.avgTemp}
              max={100}
              label="Avg temp"
              unit="C"
              size={140}
              strokeWidth={12}
            />
            <AnimatedCircularProgress
              value={stats.avgHealth}
              max={100}
              label="Avg health"
              unit="%"
              size={140}
              strokeWidth={12}
            />
          </div>
        </div>

        <div className="card stat-card span-2x1">
          <div className="card-title">Stability window</div>
          <div className="stat-value">
            <NumberTicker value={stableTicks} />
            <span className="stat-unit">ticks</span>
          </div>
          <div className="stat-sub">
            {lastIncidentTick === null
              ? "No incidents detected yet"
              : "Ticks since last incident"}
          </div>
          <div className="stat-row">
            <span>Last incident tick</span>
            <span className="stat-inline">
              {lastIncidentTick === null ? "-" : lastIncidentTick}
            </span>
          </div>
        </div>

        <div className="card stat-card span-2x1">
          <div className="card-title">Load distribution</div>
          <div className="stacked-bar">
            {loadSegments.map((segment) => (
              <div
                key={segment.id}
                className={`stacked-segment segment-${segment.id.toLowerCase()}`}
                style={{ width: `${segment.share}%` }}
                aria-label={`${segment.id} load ${formatPercent(segment.load)}`}
              />
            ))}
          </div>
          <div className="stacked-legend">
            {loadSegments.map((segment) => (
              <div className="legend-item" key={segment.id}>
                <span className="legend-label">
                  <span className={`legend-dot segment-${segment.id.toLowerCase()}`} />
                  {segment.id}
                </span>
                <strong>{formatPercent(segment.load)}</strong>
              </div>
            ))}
          </div>
          <div className="stat-row">
            <span>Peak temperature</span>
            <span className="stat-inline">
              {maxTempEntry.id} · {formatTemp(maxTempEntry.temp)}
            </span>
          </div>
        </div>

        <div className="card stat-card span-2x1">
          <div className="card-title">Operational health</div>
          <div className="metric">
            <div className="metric-row">
              <span>Average health</span>
              <strong>{formatPercent(stats.avgHealth)}</strong>
            </div>
            <MetricBar value={stats.avgHealth} max={100} tone="tone-ok" label="Average health" />
          </div>
          <div className="metric">
            <div className="metric-row">
              <span>Average error rate</span>
              <strong>{formatPercent(stats.avgError)}</strong>
            </div>
            <MetricBar value={stats.avgError} max={20} tone="tone-danger" label="Average error rate" />
          </div>
          <div className="metric">
            <div className="metric-row">
              <span>Cooling utilization</span>
              <strong>{formatPercent(coolingUtilization)}</strong>
            </div>
            <MetricBar
              value={coolingUtilization}
              max={100}
              tone="tone-warn"
              label="Cooling utilization"
            />
          </div>
        </div>

        <div className="card stat-card span-2x1">
          <div className="card-title">Power draw</div>
          <div className="stat-value">
            <NumberTicker
              value={stats.totalPower}
              format={(val) => formatNumber(val, 0)}
            />
            <span className="stat-unit">W</span>
          </div>
          <div className="stat-sub">Total rack consumption</div>
          <div className="stat-row">
            <span>Avg power / node</span>
            <span className="stat-inline">
              {stats.serverCount > 0
                ? `${formatNumber(stats.totalPower / stats.serverCount, 0)} W`
                : "-"}
            </span>
          </div>
        </div>

        <div className="card stat-card span-4x1">
          <div className="card-title">Recent events</div>
          {recentEvents.length === 0 ? (
            <div className="empty">No events yet. Inject a fault to begin.</div>
          ) : (
            <AnimatedList
              items={recentEvents}
              getKey={(event) => event.id}
              renderItem={(event) => (
                <button
                  type="button"
                  className="event-link"
                  onClick={() => onOpenEvents(event.id)}
                >
                  <EventCard event={event} variant="compact" />
                </button>
              )}
              itemClassName="event-compact-wrapper"
            />
          )}
          <button type="button" className="button outline" onClick={() => onOpenEvents()}>
            View full timeline
          </button>
        </div>
      </section>
    </div>
  );
}
