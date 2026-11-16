import { useEffect, useState } from "react";
import "./css/IncidentList.css";

const statusLabels = {
  all: "All incidents",
  open: "Open",
  "under-review": "Under review",
  closed: "Closed",
};

export default function IncidentList({
  endpoint,
  heading = "All incidents",
  showSubmittedBy = true,
  emptyMessage = "No incidents have been submitted yet.",
}) {
  const [incidents, setIncidents] = useState([]);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    async function loadIncidents() {
      setLoading(true);
      setError("");
      setIncidents([]);

      try {
        const response = await fetch(endpoint, {
          signal: controller.signal,
          cache: "no-store",
        });

        if (response.status === 401) {
          throw new Error("Your session has expired. Please sign in again.");
        }

        if (response.status === 403) {
          throw new Error("You do not have permission to view these incidents.");
        }

        if (!response.ok) {
          throw new Error("Could not load incidents. Please try again.");
        }

        const data = await response.json();

        if (!controller.signal.aborted) {
          setIncidents(data);
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(err.message || "Could not reach the server.");
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    loadIncidents();
    return () => controller.abort();
  }, [endpoint, retryCount]);

  const dateTimeFormatter = new Intl.DateTimeFormat("en-US", {
  year: "numeric",
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
  timeZoneName: "short",
});

function renderDateTime(value) {
  if (!value) return "Date unavailable";

  // The backend stores UTC. Some timestamps may arrive without a timezone suffix.
  const hasTimeZone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value);
  const date = new Date(hasTimeZone ? value : `${value}Z`);

  if (Number.isNaN(date.getTime())) return "Date unavailable";

  return (
    <time dateTime={date.toISOString()}>
      {dateTimeFormatter.format(date)}
    </time>
  );
}

  const visibleIncidents =
    filter === "all"
      ? incidents
      : incidents.filter(
          (incident) => incident.status.replace("_", "-") === filter
        );

  return (
    <section className="incident-list">
      <div className="incident-list-heading">
        {/* <h2>{heading}</h2> */}

        {!loading && !error && (
          <label className="incident-list-filter">
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M3 4h18l-7 8v6l-4 2v-8L3 4Z" />
            </svg>

            <select
              aria-label="Filter incidents by status"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            >
              {Object.entries(statusLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {loading && <p role="status">Loading incidents…</p>}

      {error && (
        <div className="incident-list-error">
          <p role="alert">{error}</p>
          <button
            type="button"
            onClick={() => setRetryCount((count) => count + 1)}
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && visibleIncidents.length === 0 && (
        <p className="incident-list-empty" role="status">
          {incidents.length === 0
            ? emptyMessage
            : `No incidents with the status “${statusLabels[filter]}”.`}
        </p>
      )}

      {!loading && !error && visibleIncidents.length > 0 && (
        <div className="incident-list-grid">
          {visibleIncidents.map((incident) => {
            const status = incident.status.replace("_", "-");
            const comments = incident.comments ?? [];

            return (
              <article key={incident.id} className="incident-card">
                <header className="incident-card-heading">
                  <h3>{incident.title}</h3>
                  <span className="incident-card-status" data-status={status}>
                    {statusLabels[status] ?? incident.status}
                  </span>
                </header>

                <p className="incident-card-meta">
                  {showSubmittedBy && (
                    <>
                      Submitted by{" "}
                      <strong>{incident.submitted_by_name || "Unknown user"}</strong>
                      {" · "}
                    </>
                  )}
                  Incident ID - <code>{incident.id.slice(-6)}</code>
                </p>

                <p className="incident-card-created">
                  Created {renderDateTime(incident.created_at)}
                </p>

                <div
                  className="incident-card-description"
                  role="region"
                  aria-label={`Description of ${incident.title}`}
                  tabIndex={0}
                >
                  <p>{incident.description}</p>
                </div>

                <details className="incident-card-comments">
                  <summary>Comments ({comments.length})</summary>

                  {comments.length === 0 ? (
                    <p className="incident-card-comments-empty">No comments yet.</p>
                  ) : (
                    <ul
                      className="incident-card-comment-list"
                      aria-label={`Comments on ${incident.title}`}
                      tabIndex={0}
                    >
                      {comments.map((comment) => (
                        <li key={comment.id}>
                          <div className="incident-card-comment-heading">
                            <strong>{comment.username || "Unknown user"}</strong>
                            <span className="incident-card-comment-time">
                              {renderDateTime(comment.created_at)}
                            </span>
                          </div>
                          <p>{comment.text}</p>
                        </li>
                      ))}
                    </ul>
                  )}
                </details>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}