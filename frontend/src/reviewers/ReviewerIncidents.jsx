import { useEffect, useState } from "react";
import "./css/ReviewerIncidents.css";

const filters = [
  { value: "all", label: "All" },
  { value: "open", label: "Open" },
  { value: "under-review", label: "Under review" },
  { value: "closed", label: "Closed" },
];

export default function ReviewerIncidents() {
  const [incidents, setIncidents] = useState([]);
  const [filter, setFilter] = useState("all");
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

  const visibleIncidents = incidents.filter(
    (incident) =>
      filter === "all" || incident.status.replace("_", "-") === filter
  );

  return (
    <section className="reviewer-incidents">
      <h2>All incidents</h2>

      {loading && <p role="status">Loading incidents…</p>}
      {error && <p role="alert">{error}</p>}

      {!loading && !error && (
        <>
          <div
            className="reviewer-incident-filters"
            role="group"
            aria-label="Filter incidents by status"
          >
            {filters.map((item) => (
              <button
                key={item.value}
                type="button"
                aria-pressed={filter === item.value}
                onClick={() => setFilter(item.value)}
              >
                {item.label}
              </button>
            ))}
          </div>

          {visibleIncidents.length === 0 ? (
            <p role="status">
              {incidents.length === 0
                ? "No incidents have been submitted yet."
                : "No incidents match this status."}
            </p>
          ) : (
            <div className="reviewer-incident-grid">
              {visibleIncidents.map((incident) => {
                const status = incident.status.replace("_", "-");
                const label = filters.find((item) => item.value === status)?.label;

                return (
                  <article key={incident.id} className="reviewer-incident-card">
                    <div className="reviewer-incident-heading">
                      <h3>{incident.title}</h3>
                      <span className="reviewer-status-badge" data-status={status}>
                        {label || incident.status}
                      </span>
                    </div>

                    <p className="reviewer-incident-author">
                      Submitted by {incident.submitted_by_name || "Unknown user"}
                    </p>

                    <p className="reviewer-incident-description">
                      {incident.description}
                    </p>
                  </article>
                );
              })}
            </div>
          )}
        </>
      )}
    </section>
  );
}