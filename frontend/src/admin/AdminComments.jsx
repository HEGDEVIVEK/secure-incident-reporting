import { useEffect, useState } from "react";
import IncidentCommentForm from "../shared/IncidentCommentForm.jsx";
import "./css/AdminComments.css";

const statusLabels = {
  open: "Open",
  "under-review": "Under review",
  closed: "Closed",
};

export default function AdminComments() {
  const [incidents, setIncidents] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshVersion, setRefreshVersion] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    async function loadIncidents() {
      setError("");

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
  }, [refreshVersion]);

  function refreshIncidents() {
    setRefreshVersion((version) => version + 1);
  }

  const selectedIncident = incidents.find((item) => item.id === selectedId);
  const comments = selectedIncident?.comments ?? [];
  const status = selectedIncident?.status.replace("_", "-");

  return (
    <section className="admin-discussion">
      {/* <h2>Comments</h2> */}

      <div className="admin-discussion-picker">
        <label htmlFor="admin-discussion-select">Select an incident</label>

        <select
          id="admin-discussion-select"
          value={selectedId}
          onChange={(event) => setSelectedId(event.target.value)}
          disabled={loading || incidents.length === 0}
        >
          <option value="">
            {loading ? "Loading incidents…" : "Choose an incident"}
          </option>

          {incidents.map((incident) => (
            <option key={incident.id} value={incident.id}>
              {incident.title} · {incident.id.slice(-6)}
            </option>
          ))}
        </select>

        {!loading && !error && incidents.length === 0 && (
          <p>No incidents have been submitted yet.</p>
        )}
        {error && <p role="alert">{error}</p>}
      </div>

      {selectedIncident && (
        <article className="admin-discussion-card" key={selectedIncident.id}>
          <div className="admin-discussion-header">
            <div>
              <h3>{selectedIncident.title}</h3>
              <p>
                Submitted by{" "}
                <strong>{selectedIncident.submitted_by_name || "Unknown user"}</strong>
                {" · "}
                Incident ID <code>{selectedIncident.id.slice(-6)}</code>
              </p>
            </div>

            <span className="admin-discussion-status" data-status={status}>
              {statusLabels[status] ?? selectedIncident.status}
            </span>
          </div>

          <section className="admin-discussion-description">
            <h4>Description</h4>
            <p>{selectedIncident.description}</p>
          </section>

          <details className="admin-discussion-history" open>
            <summary>Previous comments ({comments.length})</summary>

            {comments.length === 0 ? (
              <p className="admin-discussion-empty">No comments yet.</p>
            ) : (
              <ul>
                {comments.map((comment) => (
                  <li key={comment.id}>
                    <strong>{comment.username || "Unknown user"}</strong>
                    <p>{comment.text}</p>
                  </li>
                ))}
              </ul>
            )}
          </details>

          <div className="admin-discussion-compose">
            <IncidentCommentForm
              incidentId={selectedIncident.id}
              onCommentSaved={refreshIncidents}
            />
          </div>
        </article>
      )}
    </section>
  );
}