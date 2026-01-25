import type { EventRecord } from "../types";
import { formatTime } from "../utils/format";

type EventCardProps = {
  event: EventRecord;
  variant?: "full" | "compact";
};

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

export default function EventCard({ event, variant = "full" }: EventCardProps) {
  return (
    <div className={`event event-${event.type} ${variant === "compact" ? "event-compact" : ""}`.trim()}>
      <div className="event-head">
        <span className={`badge badge-${event.type}`}>{event.type}</span>
        <span className="event-message">{event.message}</span>
      </div>
      <div className="event-meta">
        <span>Tick {event.tick}</span>
        <span>{formatTime(event.ts)}</span>
      </div>
      {variant === "full" ? renderPayload(event) : null}
    </div>
  );
}
