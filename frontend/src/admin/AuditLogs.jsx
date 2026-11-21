import { useEffect, useState } from "react";
import "./css/AuditLogs.css";

import { apiFetch } from "../shared/api.js";

// Read-only view of the audit trail (FR-11, FR-12). The API has no endpoint
// to edit or delete entries, and this page only reads them.

const actionLabels = {
  user_created: "User created",
  user_account_updated: "Account updated",
  password_changed: "Password changed",
  incident_created: "Incident created",
  incident_status_changed: "Status changed",
  comment_created: "Comment added",
};

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
  second: "2-digit",
  timeZoneName: "short",
});

function renderTimestamp(value) {
  if (!value) return "Unknown time";
  const hasTimeZone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value);
  const date = new Date(hasTimeZone ? value : `${value}Z`);
  if (Number.isNaN(date.getTime())) return "Unknown time";
  return <time dateTime={date.toISOString()}>{dateFormatter.format(date)}</time>;
}

function shortId(id) {
  return id ? String(id).slice(-6) : "";
}

function describeTarget(entry) {
  const name = entry.target_username ?? entry.target_title ?? entry.incident_title;
  const type = entry.target_type === "comment" ? "incident" : entry.target_type;
  const id = entry.target_type === "comment" ? entry.incident_id : entry.target_id;
  return { type, name, id: shortId(id) };
}

function describeDetails(entry) {
  if (entry.action === "incident_status_changed") {
    const from = statusLabels[entry.old_status] ?? entry.old_status;
    const to = statusLabels[entry.new_status] ?? entry.new_status;
    return `${from} → ${to}`;
  }

  if (entry.action === "user_account_updated" && entry.changes) {
    const parts = [];
    if (entry.changes.role) {
      parts.push(`Role: ${entry.changes.role.old} → ${entry.changes.role.new}`);
    }
    if (entry.changes.is_active) {
      const label = (active) => (active ? "Active" : "Inactive");
      parts.push(
        `Status: ${label(entry.changes.is_active.old)} → ${label(entry.changes.is_active.new)}`
      );
    }
    return parts.join(", ");
  }

  if (entry.action === "comment_created") {
    return `Comment ${shortId(entry.target_id)}`;
  }

  return "";
}

export default function AuditLogs() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshCount, setRefreshCount] = useState(0);
  const [actionFilter, setActionFilter] = useState("all");
  const [search, setSearch] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function loadEntries() {
      setLoading(true);
      setError("");

      try {
        const response = await apiFetch("/api/audit-logs", {
          signal: controller.signal,
          cache: "no-store",
        });

        if (response.status === 401) {
          throw new Error("Your session has expired. Please sign in again.");
        }
        if (response.status === 403) {
          throw new Error("Admin access is required to view the audit log.");
        }
        if (!response.ok) {
          throw new Error("Could not load the audit log. Please try again.");
        }

        const data = await response.json();
        if (!controller.signal.aborted) setEntries(data);
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(err.message || "Could not reach the server.");
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    loadEntries();
    return () => controller.abort();
  }, [refreshCount]);

  const query = search.trim().toLowerCase();
  const visibleEntries = entries.filter((entry) => {
    if (actionFilter !== "all" && entry.action !== actionFilter) return false;
    if (!query) return true;
    const target = describeTarget(entry);
    return [entry.username, target.name, target.id]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query));
  });

  return (
    <section className="audit-logs">
      <div className="audit-logs-intro">
        <p>
          Append-only record of key actions, newest first (latest 200). Entries
          cannot be edited or deleted from the application.
        </p>
        <button
          type="button"
          className="audit-logs-refresh"
          onClick={() => setRefreshCount((count) => count + 1)}
          disabled={loading}
        >
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      <div className="audit-logs-toolbar">
        <label>
          Action
          <select
            value={actionFilter}
            onChange={(event) => setActionFilter(event.target.value)}
          >
            <option value="all">All actions</option>
            {Object.entries(actionLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label>
          Search
          <input
            type="search"
            placeholder="Username, target, or ID"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
      </div>

      {error && (
        <div className="audit-logs-error">
          <p role="alert">{error}</p>
          <button type="button" onClick={() => setRefreshCount((count) => count + 1)}>
            Retry
          </button>
        </div>
      )}

      {!loading && !error && visibleEntries.length === 0 && (
        <p role="status">
          {entries.length === 0 ? "No audit entries yet." : "No entries match the filters."}
        </p>
      )}

      {!error && visibleEntries.length > 0 && (
        <div
          className="audit-logs-scroll"
          role="region"
          aria-label="Audit log entries"
          tabIndex={0}
        >
          <table className="audit-logs-table">
            <thead>
              <tr>
                <th scope="col">Time</th>
                <th scope="col">Action</th>
                <th scope="col">Performed by</th>
                <th scope="col">Target</th>
                <th scope="col">Details</th>
              </tr>
            </thead>
            <tbody>
              {visibleEntries.map((entry) => {
                const target = describeTarget(entry);
                return (
                  <tr key={entry.id}>
                    <td className="audit-logs-time">{renderTimestamp(entry.timestamp)}</td>
                    <td>
                      <span className="audit-logs-action" data-action={entry.action}>
                        {actionLabels[entry.action] ?? entry.action}
                      </span>
                    </td>
                    <td>
                      <strong>{entry.username ?? "Unknown"}</strong>
                      <span className="audit-logs-id">ID {shortId(entry.user_id)}</span>
                    </td>
                    <td>
                      <span className="audit-logs-target-type">{target.type}</span>{" "}
                      {target.name && <strong>{target.name}</strong>}
                      {target.id && <span className="audit-logs-id">ID {target.id}</span>}
                    </td>
                    <td>{describeDetails(entry)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
