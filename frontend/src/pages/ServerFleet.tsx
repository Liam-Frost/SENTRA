import type { ServerId, WorldState } from "../types";
import MetricBar from "../components/MetricBar";
import { formatPercent, formatPower, formatTemp } from "../utils/format";
import { isIncident } from "../utils/metrics";

const serverIds: ServerId[] = ["S1", "S2", "S3"];

type ServerFleetProps = {
  state: WorldState;
};

export default function ServerFleet({ state }: ServerFleetProps) {
  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-eyebrow">Inventory</div>
          <h2 className="page-title">Server fleet</h2>
          <p className="page-description">
            Detailed health and performance metrics for every server node.
          </p>
        </div>
        <div className="page-status">
          <div className="status-chip">Live nodes {serverIds.length}</div>
          <div className="status-chip">
            Cooling {serverIds.filter((id) => state.servers[id].cooling).length}/3
          </div>
        </div>
      </div>

      <div className="server-grid">
        {serverIds.map((id) => {
          const server = state.servers[id];
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
                <MetricBar
                  value={server.error_rate}
                  max={20}
                  tone="tone-danger"
                  label={`${id} error rate`}
                />
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
    </div>
  );
}
