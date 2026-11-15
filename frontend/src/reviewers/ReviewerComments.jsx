import { useEffect, useState } from "react";
import IncidentCommentForm from "../shared/IncidentCommentForm.jsx";
import "./css/ReviewerComments.css";

// Use the exact value accepted by IncidentStatusUpdate in your FastAPI schema.
const UNDER_REVIEW_STATUS = "under-review";

const statusLabels = {
  open: "Open",
  "under-review": "Under review",
  under_review: "Under review",
  closed: "Closed",
};

export default function ReviewerComments() {
  const [incidents, setIncidents] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [savingStatus, setSavingStatus] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [statusError, setStatusError] = useState("");

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
  }, []);

  const selectedIncident = incidents.find((incident) => incident.id === selectedId);

  function handleSelect(event) {
    setSelectedId(event.target.value);
    setStatusMessage("");
    setStatusError("");
  }

  async function updateStatus(nextStatus) {
    if (!selectedIncident || savingStatus) return;

    const incidentId = selectedIncident.id;
    setSavingStatus(true);
    setStatusError("");
    setStatusMessage("");

    try {
      const response = await fetch(`/api/incidents/${incidentId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: nextStatus }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(
          typeof data?.detail === "string"
            ? data.detail
            : "Could not update the incident status."
        );
      }

      const updated = await response.json();

      setIncidents((previous) =>
        previous.map((incident) =>
          incident.id === incidentId
            ? { ...incident, status: updated.status }
            : incident
        )
      );

      setStatusMessage(`Status updated to ${statusLabels[updated.status]}.`);
    } catch (err) {
      setStatusError(err.message || "Could not reach the server.");
    } finally {
      setSavingStatus(false);
    }
  }

  return (
    <section className="reviewer-comments">
      <h2>Comments &amp; status</h2>

      {loading && <p role="status">Loading incidents…</p>}
      {loadError && <p role="alert">{loadError}</p>}

      {!loading && !loadError && incidents.length === 0 && (
        <p>No incidents available for review.</p>
      )}

      {incidents.length > 0 && (
        <label className="reviewer-incident-picker">
          Select an incident
          <select
            value={selectedId}
            onChange={handleSelect}
            disabled={savingStatus}
          >
            <option value="">Choose an incident</option>

            {incidents.map((incident) => (
              <option key={incident.id} value={incident.id}>
                {incident.title} · {statusLabels[incident.status]} · {incident.id.slice(-6)}
              </option>
            ))}
          </select>
        </label>
      )}

      {selectedIncident && (
        <article className="reviewer-comment-card">
          <h3>{selectedIncident.title}</h3>

          <p className="reviewer-comment-meta">
            Submitted by {selectedIncident.submitted_by_name || "Unknown user"}
            {" · "}
            <strong>{statusLabels[selectedIncident.status]}</strong>
          </p>

          <p className="reviewer-comment-description">
            {selectedIncident.description}
          </p>

          {selectedIncident.status !== "closed" && (
            <div className="reviewer-status-actions">
              {selectedIncident.status === "open" && (
                <button
                  type="button"
                  disabled={savingStatus}
                  onClick={() => updateStatus(UNDER_REVIEW_STATUS)}
                >
                  Start review
                </button>
              )}

              <button
                type="button"
                disabled={savingStatus}
                onClick={() => updateStatus("closed")}
              >
                Close incident
              </button>
            </div>
          )}

          {statusMessage && <p role="status">{statusMessage}</p>}
          {statusError && <p role="alert">{statusError}</p>}

          <IncidentCommentForm
            key={selectedIncident.id}
            incidentId={selectedIncident.id}
          />
        </article>
      )}
    </section>
  );
}