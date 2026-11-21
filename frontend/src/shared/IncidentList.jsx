import { useEffect, useId, useRef, useState } from "react";
import "./css/IncidentList.css";

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
  { key: "status", title: "Incident status", labels: statusLabels },
  { key: "priority", title: "Incident priority", labels: priorityLabels },
];

const emptyFilters = { status: [], priority: [] };

function normalizeStatus(status) {
  return (status ?? "").trim().toLowerCase().replace(/[\s_]+/g, "-");
}

function matchesIncident(incident, filters, query) {
  const status = normalizeStatus(incident.status);
  const priority = (incident.priority ?? "").trim().toLowerCase();
  const matchesStatus = !filters.status.length || filters.status.includes(status);
  const matchesPriority = !filters.priority.length || filters.priority.includes(priority);
  const matchesSearch = !query ||
    incident.title.toLowerCase().includes(query) ||
    incident.id.toLowerCase().includes(query);
  return matchesStatus && matchesPriority && matchesSearch;
}

function FilterMenu({ filters, onApply }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(filters);
  const wrapper = useRef(null);
  const trigger = useRef(null);
  const panelId = useId();
  const count = filters.status.length + filters.priority.length;

  useEffect(() => {
    if (!open) return;
    function closeOutside(event) {
      if (!wrapper.current?.contains(event.target)) setOpen(false);
    }
    document.addEventListener("pointerdown", closeOutside);
    return () => document.removeEventListener("pointerdown", closeOutside);
  }, [open]);

  function toggleOption(group, value, checked) {
    setDraft(previous => ({
      ...previous,
      [group]: checked
        ? [...previous[group], value]
        : previous[group].filter(item => item !== value),
    }));
  }

  function closeAndFocus() {
    setOpen(false);
    trigger.current?.focus();
  }

  return (
    <div className="incident-filter-menu" ref={wrapper}

      onBlur={event => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
      
      onKeyDown={event => {
        if (open && event.key === "Escape") {
          event.stopPropagation();
          closeAndFocus();
        }
      }}
    >
      <button type="button" className="incident-filter-trigger" ref={trigger}
        aria-expanded={open} aria-controls={panelId}
        onClick={() => {
          if (!open) setDraft(filters);
          setOpen(!open);
        }}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
          strokeLinejoin="round" aria-hidden="true">
          <path d="M3 4h18l-7 8v6l-4 2v-8L3 4Z" />
        </svg>
        Filter by status and priority{count > 0 && ` (${count})`}
      </button>

      <div className="incident-filter-panel" id={panelId} hidden={!open}>
        {filterGroups.map(({ key, title, labels }) => (
          <fieldset key={key}>
            <legend>{title}</legend>
            {Object.entries(labels).map(([value, label]) => (
              <label key={value}>
                <input type="checkbox" checked={draft[key].includes(value)}
                  onChange={event => toggleOption(key, value, event.target.checked)} />
                {label}
              </label>
            ))}
          </fieldset>
        ))}
        <div className="incident-filter-actions">
          <button type="button" className="incident-filter-clear"
            onClick={() => setDraft(emptyFilters)}>Clear</button>
          <button type="button" className="incident-filter-done" onClick={() => {
            onApply(draft);
            closeAndFocus();
          }}>Done</button>
        </div>
      </div>
    </div>
  );
}

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
  const hasTimeZone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value);
  const date = new Date(hasTimeZone ? value : `${value}Z`);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return <time dateTime={date.toISOString()}>{dateTimeFormatter.format(date)}</time>;
}

export default function IncidentList({
  endpoint,
  heading = "All incidents",
  showSubmittedBy = true,
  emptyMessage = "No incidents have been submitted yet.",
}) {
  const [incidents, setIncidents] = useState([]);
  const [filters, setFilters] = useState(emptyFilters);
  const [search, setSearch] = useState("");
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
        const response = await apiFetch(endpoint, {
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
        if (!controller.signal.aborted) setIncidents(data);
      } catch (err) {
        if (!controller.signal.aborted) setError(err.message || "Could not reach the server.");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    loadIncidents();
    return () => controller.abort();
  }, [endpoint, retryCount]);

  const query = search.trim().toLowerCase();
  const visibleIncidents = incidents.filter(incident => matchesIncident(incident, filters, query));

  // Count incidents per status for the summary row.
  const statusCounts = incidents.reduce((counts, incident) => {
    const status = normalizeStatus(incident.status);
    counts[status] = (counts[status] ?? 0) + 1;
    return counts;
  }, {});

  // Clicking a summary chip shows only that status; clicking it again clears it.
  function toggleStatusChip(status) {
    setFilters(previous => ({
      ...previous,
      status: previous.status.length === 1 && previous.status[0] === status ? [] : [status],
    }));
  }

  return (
    <section className="incident-list" aria-label={heading}>

      {!loading && !error && incidents.length > 0 && (
        <div className="incident-summary" aria-label="Incidents by status">
          <span className="incident-summary-total">
            <strong>{incidents.length}</strong> total
          </span>
          {Object.entries(statusLabels).map(([status, label]) => (
            <button
              key={status}
              type="button"
              className="incident-summary-chip"
              data-status={status}
              aria-pressed={filters.status.length === 1 && filters.status[0] === status}
              onClick={() => toggleStatusChip(status)}
            >
              <strong>{statusCounts[status] ?? 0}</strong> {label}
            </button>
          ))}
        </div>
      )}

      {!loading && !error && (
        <div className="incident-list-toolbar">
          <input type="search" className="incident-list-search"
            aria-label="Search incidents by title or ID" placeholder="Search by title or ID"
            value={search} onChange={event => setSearch(event.target.value)} />
          <FilterMenu filters={filters} onApply={setFilters} />
        </div>
      )}

      {loading && <p role="status">Loading incidents…</p>}
      {error && (
        <div className="incident-list-error">
          <p role="alert">{error}</p>
          <button type="button" onClick={() => setRetryCount(count => count + 1)}>Retry</button>
        </div>
      )}

      {!loading && !error && visibleIncidents.length === 0 && (
        <p className="incident-list-empty" role="status">
          {incidents.length === 0 ? emptyMessage : "No incidents match your search and filters."}
        </p>
      )}

      {!loading && !error && visibleIncidents.length > 0 && (
        <div className="incident-list-grid">
          {visibleIncidents.map(incident => {

            const status = normalizeStatus(incident.status);
            const priority = (incident.priority ?? "").trim().toLowerCase();
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
                    <>Submitted by <strong>{incident.submitted_by_name || "Unknown user"}</strong>{" · "}</>
                  )}
                  Incident ID - <code>{incident.id.slice(-6)}</code>
                  {" · "}Priority: <strong>{priorityLabels[priority] ?? "Unassigned"}</strong>
                </p>

                <p className="incident-card-created">Created {renderDateTime(incident.created_at)}</p>
                <div className="incident-card-description" role="region"
                  aria-label={`Description of ${incident.title}`} tabIndex={0}>
                  <p>{incident.description}</p>
                </div>

                <details className="incident-card-comments">
                  <summary>Comments ({comments.length})</summary>
                  {comments.length === 0 ? (
                    <p className="incident-card-comments-empty">No comments yet.</p>
                  ) : (
                    <ul className="incident-card-comment-list"
                      aria-label={`Comments on ${incident.title}`} tabIndex={0}>
                      {comments.map(comment => (
                        <li key={comment.id}>
                          <div className="incident-card-comment-heading">
                            <strong>{comment.username || "Unknown user"}</strong>
                            <span className="incident-card-comment-time">{renderDateTime(comment.created_at)}</span>
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
