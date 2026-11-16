import { useEffect, useState } from "react";
import "./css/IncidentComments.css";

const statusLabels = {
  open: "Open",
  "under-review": "Under review",
  closed: "Closed",
};

const dateFormatter = new Intl.DateTimeFormat("en-US", {
  year: "numeric",
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
  timeZoneName: "short",
});

function renderDateTime(value) {
  if (!value) return "Date unavailable";

  // The backend stores UTC, including timestamps returned without a suffix.
  const hasTimeZone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value);
  const date = new Date(hasTimeZone ? value : `${value}Z`);

  if (Number.isNaN(date.getTime())) return "Date unavailable";

  return <time dateTime={date.toISOString()}>{dateFormatter.format(date)}</time>;
}

export default function IncidentComments({ canChangeStatus = false }) {
  const [incidents, setIncidents] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [refreshVersion, setRefreshVersion] = useState(0);

  const [commentText, setCommentText] = useState("");
  const [savingAction, setSavingAction] = useState(null);
  const [message, setMessage] = useState("");
  const [actionError, setActionError] = useState("");

  const isSaving = savingAction !== null;
  const selectedIncident = incidents.find((item) => item.id === selectedId);
  const comments = selectedIncident?.comments ?? [];
  const status = selectedIncident?.status.replace("_", "-");

  useEffect(() => {
    const controller = new AbortController();

    async function loadIncidents() {
      setLoadError("");

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
          setLoadError(err.message || "Could not reach the server.");
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

  function handleSelect(event) {
    setSelectedId(event.target.value);
    setCommentText("");
    setMessage("");
    setActionError("");
  }

  async function handleCommentSubmit(event) {
    event.preventDefault();

    if (!selectedIncident || isSaving) return;

    const text = commentText.trim();
    setMessage("");
    setActionError("");

    if (!text) {
      setActionError("Enter a comment before submitting.");
      return;
    }

    setSavingAction("comment");

    try {
      const response = await fetch(
        `/api/incidents/${selectedIncident.id}/comments`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
        }
      );

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        setActionError(
          typeof data?.detail === "string"
            ? data.detail
            : "Could not save the comment. Please check the text and try again."
        );
        return;
      }

      setCommentText("");
      setMessage("Comment added.");
      refreshIncidents();
    } catch {
      setActionError("Could not confirm whether the comment was saved.");
    } finally {
      setSavingAction(null);
    }
  }

  async function updateStatus(nextStatus) {
    if (!canChangeStatus || !selectedIncident || isSaving) return;

    const incidentId = selectedIncident.id;
    setSavingAction("status");
    setMessage("");
    setActionError("");

    try {
      const response = await fetch(`/api/incidents/${incidentId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: nextStatus }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        setActionError(
          typeof data?.detail === "string"
            ? data.detail
            : "Could not update the incident status."
        );
        return;
      }

      const updated = await response.json();
      const savedStatus = updated.status.replace("_", "-");

      setIncidents((previous) =>
        previous.map((incident) =>
          incident.id === incidentId
            ? { ...incident, status: updated.status }
            : incident
        )
      );

      setMessage(`Status updated to ${statusLabels[savedStatus]}.`);
      refreshIncidents();
    } catch {
      setActionError("Could not confirm whether the status was updated.");
    } finally {
      setSavingAction(null);
    }
  }

  return (
    <section className="incident-discussion">
      <div className="incident-discussion-picker">
        <label htmlFor="discussion-incident">Select an incident</label>

        <select
          id="discussion-incident"
          value={selectedId}
          onChange={handleSelect}
          disabled={loading || isSaving || incidents.length === 0}
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

        {!loading && !loadError && incidents.length === 0 && (
          <p>No incidents have been submitted yet.</p>
        )}
{/* 
        {loadError && (
          <div>
            <p role="alert">{loadError}</p>
            <button type="button" onClick={refreshIncidents}>
              Retry
            </button>
          </div>
        )} */}
      </div>

      {selectedIncident && (
        <article className="incident-discussion-card" key={selectedIncident.id}>
          <header className="incident-discussion-header">
            <div>
              <h3>{selectedIncident.title}</h3>

              <p>
                Submitted by{" "}
                <strong>{selectedIncident.submitted_by_name || "Unknown user"}</strong>
                {" · "}
                Incident ID - <code>{selectedIncident.id.slice(-6)}</code>
              </p>

              <p className="incident-card-created">Created {renderDateTime(selectedIncident.created_at)}</p>
            </div>

            <span className="incident-discussion-status" data-status={status}>
              {statusLabels[status] ?? selectedIncident.status}
            </span>
          </header>

          <section className="incident-discussion-description">
            <h4>Description</h4>
            <p>{selectedIncident.description}</p>
          </section>

          {canChangeStatus && status !== "closed" && (
            <div className="incident-discussion-actions">
              {status === "open" && (
                <button
                  type="button"
                  disabled={isSaving}
                  onClick={() => updateStatus("under-review")}
                >
                  Start review
                </button>
              )}

              <button
                type="button"
                disabled={isSaving}
                onClick={() => updateStatus("closed")}
              >
                Close incident
              </button>
            </div>
          )}

          <details className="incident-discussion-history" open>
            <summary>Previous comments ({comments.length})</summary>

            {comments.length === 0 ? (
              <p className="incident-discussion-empty">No comments yet.</p>
            ) : (
              <ul>
                {comments.map((comment) => (
                  <li key={comment.id}>
                    <div className="incident-discussion-comment-meta">
                      <strong>{comment.username || "Unknown user"}</strong>
                      {renderDateTime(comment.created_at)}
                    </div>
                    <p>{comment.text}</p>
                  </li>
                ))}
              </ul>
            )}
          </details>

          <div className="incident-discussion-compose">
            <form
              className="incident-comment-form"
              onSubmit={handleCommentSubmit}
            >
              <label htmlFor="discussion-comment">Add a comment</label>

              <textarea
                id="discussion-comment"
                name="text"
                rows={3}
                maxLength={2000}
                value={commentText}
                onChange={(event) => setCommentText(event.target.value)}
                disabled={savingAction === "comment"}
                required
              />

              <button type="submit" disabled={isSaving}>
                {savingAction === "comment" ? "Saving…" : "Save comment"}
              </button>
            </form>
          </div>

          {message && <p role="status">{message}</p>}
          {actionError && <p role="alert">{actionError}</p>}
        </article>
      )}
    </section>
  );
}