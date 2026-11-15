import { useEffect, useState } from "react";
import "./css/AdminIncidents.css";

const statusLabels = {
  open: "Open",
  "under-review": "Under review",
  closed: "Closed",
};

function IncidentCard({ incident }) {
  const status = incident.status.replace("_", "-");
  const comments = incident.comments ?? [];

  return (
    <article className="admin-report-card">
      <header className="admin-report-header">
        <h3>{incident.title}</h3>

        <span className="admin-report-status" data-status={status}>
          {statusLabels[status] ?? incident.status}
        </span>
      </header>

      <p className="admin-report-author">
        Submitted by <strong>{incident.submitted_by_name || "Unknown user"}</strong>
        {" · "}
        Incident ID <code>{incident.id.slice(-6)}</code>
      </p>

      <div className="admin-report-description" tabIndex={0} aria-label="Incident description">
        <p>{incident.description}</p>
      </div>

      <details className="admin-report-comments">
        <summary>
          Comments <span>({comments.length})</span>
        </summary>

        {comments.length === 0 ? (
          <p className="admin-report-empty">No comments yet.</p>
        ) : (
          <ul className="admin-report-comment-list">
            {comments.map((comment) => (
              <li key={comment.id}>
                <strong>{comment.username || "Unknown user"}</strong>
                <p>{comment.text}</p>
              </li>
            ))}
          </ul>
        )}
      </details>
    </article>
  );
}

export default function AdminIncidents() {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function loadIncidents() {
      try {
        const response = await fetch("/api/incidents", {
          signal: controller.signal,
          cache: "no-store",
        });

        if (!response.ok) {
          const data = await response.json().catch(() => null);
          throw new Error(
            typeof data?.detail === "string"
              ? data.detail
              : "Could not load incidents."
          );
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
  }, []);

  return (
    <section className="admin-reports">
      {/* <h2>All incidents</h2> */}

      {loading && <p role="status">Loading incidents…</p>}
      {error && <p role="alert">{error}</p>}

      {!loading && !error && incidents.length === 0 && (
        <p>No incidents have been submitted yet.</p>
      )}

      {incidents.length > 0 && (
        <div className="admin-report-grid">
          {incidents.map((incident) => (
            <IncidentCard key={incident.id} incident={incident} />
          ))}
        </div>
      )}
    </section>
  );
}