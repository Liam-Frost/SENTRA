import AnimatedList from "../components/AnimatedList";
import EventCard from "../components/EventCard";
import type { EventRecord } from "../types";

type EventTimelineProps = {
  events: EventRecord[];
};

export default function EventTimeline({ events }: EventTimelineProps) {
  const ordered = [...events].reverse();

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
            renderItem={(event) => <EventCard event={event} />}
          />
        )}
      </div>
    </div>
  );
}
