import { useEffect, useId, useRef, useState } from "react";
import "./css/IncidentComments.css";

import { apiFetch } from "./api.js";

const statusLabels = {
  open: "Open",
  "under-review": "Under review",
  closed: "Closed",
};

const priorityLabels = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

const filterGroups = [
  { key: "status", title: "Incident status", options: statusLabels },
  { key: "priority", title: "Incident priority", options: priorityLabels },
];

const emptyFilters = { status: [], priority: [] };

const dateFormatter = new Intl.DateTimeFormat("en-US", {
  year: "numeric",
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
  timeZoneName: "short",
});

function normalizeStatus(value) {
  return (value ?? "").trim().toLowerCase().replace(/[\s_]+/g, "-");
}

function normalizePriority(value) {
  return (value ?? "").trim().toLowerCase();
}

function renderDateTime(value) {
  if (!value) return "Date unavailable";

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

  const [filters, setFilters] = useState(emptyFilters);
  const [draftFilters, setDraftFilters] = useState(emptyFilters);
  const [filterOpen, setFilterOpen] = useState(false);

  const filterWrapper = useRef(null);
  const filterButton = useRef(null);
  const filterPanelId = useId();
  const incidentSelectId = useId();
  const commentInputId = useId();

  const isSaving = savingAction !== null;
  const activeFilterCount = filters.status.length + filters.priority.length;

  const filteredIncidents = incidents.filter((incident) => {
    const status = normalizeStatus(incident.status);
    const priority = normalizePriority(incident.priority);

    const matchesStatus =
      filters.status.length === 0 || filters.status.includes(status);

    const matchesPriority =
      filters.priority.length === 0 || filters.priority.includes(priority);

    return matchesStatus && matchesPriority;
  });

  const selectedIncident = incidents.find((item) => item.id === selectedId);
  const comments = selectedIncident?.comments ?? [];
  const status = normalizeStatus(selectedIncident?.status);
  const priority = normalizePriority(selectedIncident?.priority);

  // Keep the current incident available after its status changes,
  // even if its updated status falls outside the applied filters.
  const selectedOutsideFilters =
    selectedIncident &&
    !filteredIncidents.some((incident) => incident.id === selectedId);

  useEffect(() => {
    const controller = new AbortController();

    async function loadIncidents() {
      setLoadError("");

      try {
        const response = await apiFetch("/api/incidents", {
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

  useEffect(() => {
    if (!filterOpen) return;

    function handleOutsideClick(event) {
      if (!filterWrapper.current?.contains(event.target)) {
        setFilterOpen(false);
      }
    }

    document.addEventListener("pointerdown", handleOutsideClick);
    return () =>
      document.removeEventListener("pointerdown", handleOutsideClick);
  }, [filterOpen]);

  function refreshIncidents() {
    setRefreshVersion((version) => version + 1);
  }

  function clearFeedback() {
    setMessage("");
    setActionError("");
  }

  function handleSelect(event) {
    setSelectedId(event.target.value);
    setCommentText("");
    clearFeedback();
  }

  function toggleFilterPanel() {
    if (!filterOpen) {
      setDraftFilters(filters);
    }
    setFilterOpen((previous) => !previous);
  }

  function toggleFilter(group, value, checked) {
    setDraftFilters((previous) => ({
      ...previous,
      [group]: checked
        ? [...previous[group], value]
        : previous[group].filter((item) => item !== value),
    }));
  }

  function closeFilterPanel() {
    setFilterOpen(false);
    filterButton.current?.focus();
  }

  function applyFilters() {
    setFilters(draftFilters);
    setSelectedId("");
    setCommentText("");
    clearFeedback();
    closeFilterPanel();
  }

  async function handleCommentSubmit(event) {
    event.preventDefault();

    if (!selectedIncident || isSaving) return;

    const text = commentText.trim();
    clearFeedback();

    if (!text) {
      setActionError("Enter a comment before submitting.");
      return;
    }

    setSavingAction("comment");

    try {
      const response = await apiFetch(
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
    clearFeedback();

    try {
      const response = await apiFetch(`/api/incidents/${incidentId}/status`, {
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
      const savedStatus = normalizeStatus(updated.status);

      setIncidents((previous) =>
        previous.map((incident) =>
          incident.id === incidentId
            ? { ...incident, status: updated.status }
            : incident
        )
      );

      setMessage(`Status updated to ${statusLabels[savedStatus] ?? savedStatus}.`);
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
        <div className="incident-discussion-picker-heading">
          <label htmlFor={incidentSelectId}>Select an incident</label>

          {!loading && !loadError && (
            <div
              className="discussion-filter"
              ref={filterWrapper}
              onBlur={(event) => {
                if (!event.currentTarget.contains(event.relatedTarget)) {
                  setFilterOpen(false);
                }
              }}
              onKeyDown={(event) => {
                if (filterOpen && event.key === "Escape") {
                  event.stopPropagation();
                  closeFilterPanel();
                }
              }}
            >
              <button
                type="button"
                className="discussion-filter-trigger"
                ref={filterButton}
                disabled={isSaving}
                aria-expanded={filterOpen}
                aria-controls={filterPanelId}
                onClick={toggleFilterPanel}
              >
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
                Filter by status and priority
                {activeFilterCount > 0 && ` (${activeFilterCount})`}
              </button>

              <div
                className="discussion-filter-panel"
                id={filterPanelId}
                hidden={!filterOpen}
              >
                {filterGroups.map(({ key, title, options }) => (
                  <fieldset key={key} disabled={isSaving}>
                    <legend>{title}</legend>

                    {Object.entries(options).map(([value, label]) => (
                      <label className="discussion-filter-option" key={value}>
                        <input
                          type="checkbox"
                          checked={draftFilters[key].includes(value)}
                          onChange={(event) =>
                            toggleFilter(key, value, event.target.checked)
                          }
                        />
                        {label}
                      </label>
                    ))}
                  </fieldset>
                ))}

                <div className="discussion-filter-footer">
                  <button
                    type="button"
                    className="discussion-filter-clear"
                    disabled={isSaving}
                    onClick={() => setDraftFilters(emptyFilters)}
                  >
                    Clear
                  </button>
                  <button
                    type="button"
                    className="discussion-filter-done"
                    disabled={isSaving}
                    onClick={applyFilters}
                  >
                    Done
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        <select
          id={incidentSelectId}
          value={selectedId}
          onChange={handleSelect}
          disabled={
            loading ||
            isSaving ||
            (filteredIncidents.length === 0 && !selectedIncident)
          }
        >
          <option value="" disabled>
            {loading ? "Loading incidents…" : "Choose an incident"}
          </option>

          {selectedOutsideFilters && (
            <option value={selectedIncident.id}>
              {selectedIncident.title} · {selectedIncident.id.slice(-6)}
              {" · Current selection"}
            </option>
          )}

          {filteredIncidents.map((incident) => (
            <option key={incident.id} value={incident.id}>
              {incident.title} · {incident.id.slice(-6)}
            </option>
          ))}
        </select>

        {!loading && !loadError && filteredIncidents.length === 0 && (
          <p className="incident-discussion-empty" role="status">
            {incidents.length === 0
              ? "No incidents have been submitted yet."
              : "No incidents match the selected filters."}
          </p>
        )}

        {selectedOutsideFilters && (
          <p className="incident-discussion-empty">
            The selected incident now falls outside the applied filters.
          </p>
        )}

        {loadError && (
          <div className="incident-discussion-load-error">
            <p role="alert">{loadError}</p>
            <button type="button" onClick={refreshIncidents} disabled={isSaving}>
              Retry
            </button>
          </div>
        )}
      </div>

      {selectedIncident && (
        <article className="incident-discussion-card" key={selectedIncident.id}>
          <header className="incident-discussion-header">
            <div>
              <h3>{selectedIncident.title}</h3>
              <p>
                Submitted by{" "}
                <strong>
                  {selectedIncident.submitted_by_name || "Unknown user"}
                </strong>
                {" · "}Incident ID - <code>{selectedIncident.id.slice(-6)}</code>
              </p>
              <p>Created {renderDateTime(selectedIncident.created_at)}</p>
              <p>
                Priority{" "}
                <strong>{priorityLabels[priority] ?? "Unassigned"}</strong>
              </p>
            </div>

            <span className="incident-discussion-status" data-status={status}>
              {statusLabels[status] ?? selectedIncident.status}
            </span>
          </header>

          <section className="incident-discussion-description">
            <h4>Description</h4>
            <p>{selectedIncident.description}</p>
          </section>

          {canChangeStatus && (
            <div className="incident-discussion-actions">
              {status !== "open" && (
                <button
                  type="button"
                  disabled={isSaving}
                  onClick={() => updateStatus("open")}
                >
                  {status === "closed" ? "Reopen incident" : "Return to Open"}
                </button>
              )}

              {status === "open" && (
                <button
                  type="button"
                  disabled={isSaving}
                  onClick={() => updateStatus("under-review")}
                >
                  Start review
                </button>
              )}

              {status !== "closed" && (
                <button
                  type="button"
                  disabled={isSaving}
                  onClick={() => updateStatus("closed")}
                >
                  Close incident
                </button>
              )}
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
            <form className="incident-comment-form" onSubmit={handleCommentSubmit}>
              <label htmlFor={commentInputId}>Add a comment</label>
              <textarea
                id={commentInputId}
                name="text"
                rows={3}
                maxLength={2000}
                value={commentText}
                onChange={(event) => setCommentText(event.target.value)}
                disabled={isSaving}
                required
              />
              <button type="submit" disabled={isSaving}>
                {savingAction === "comment" ? "Saving…" : "Save comment"}
              </button>
            </form>
          </div>
        </article>
      )}

      {message && <p className="discussion-success" role="status">{message}</p>}
      {actionError && <p className="discussion-error" role="alert">{actionError}</p>}
    </section>
  );
}