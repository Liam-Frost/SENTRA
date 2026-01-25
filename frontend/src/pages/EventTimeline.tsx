import { useEffect, useMemo, useState } from "react";

import AnimatedList from "../components/AnimatedList";
import EventCard from "../components/EventCard";
import type { EventRecord } from "../types";

type EventTimelineProps = {
  events: EventRecord[];
};

export default function EventTimeline({ events }: EventTimelineProps) {
  const ordered = useMemo(() => [...events].reverse(), [events]);
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null);

  useEffect(() => {
    const parseSelectedEvent = () => {
      const hash = window.location.hash;
      const idx = hash.indexOf("?");
      if (idx === -1) return null;
      const params = new URLSearchParams(hash.slice(idx + 1));
      const raw = params.get("event");
      const parsed = raw ? Number(raw) : NaN;
      return Number.isFinite(parsed) ? parsed : null;
    };

    const update = () => setSelectedEventId(parseSelectedEvent());
    update();
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);

  useEffect(() => {
    if (!selectedEventId) return;
    const el = document.getElementById(`event-${selectedEventId}`);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [ordered.length, selectedEventId]);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-eyebrow">Audit log</div>
          <h2 className="page-title">Event timeline</h2>
          <p className="page-description">
            Full record of incidents, actions, AI explanations, and system resets.
          </p>
        </div>
      </div>

      <div className="timeline">
        {ordered.length === 0 ? (
          <div className="empty">No events yet. Inject a fault to begin.</div>
        ) : (
          <AnimatedList
            items={ordered}
            getKey={(event) => event.id}
            renderItem={(event) => (
              <div
                id={`event-${event.id}`}
                className={`event-anchor ${
                  selectedEventId === event.id ? "is-target" : ""
                }`.trim()}
              >
                <EventCard event={event} />
              </div>
            )}
          />
        )}
      </div>
    </div>
  );
}
