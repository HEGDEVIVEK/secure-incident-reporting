import { useEffect, useState } from "react";
import IncidentCommentForm from "../shared/IncidentCommentForm.jsx";
import "./ReviewersDashboard.css";

const filters = [
    { value: "all", label: "All active" },
    { value: "open", label: "Open" },
    { value: "under-review", label: "Under review" },
];

const statusLabels = {
    open: "Open",
    "under-review": "Under review",
    closed: "Closed",
};

function IncidentCard({ incident, onStatusChanged }) {
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState("");

    async function updateStatus(nextStatus) {
        setError("");
        setIsSaving(true);

        try {
            const response = await fetch(`/api/incidents/${incident.id}/status`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ status: nextStatus }),
            });

            if (!response.ok) {
                const data = await response.json().catch(() => null);
                setError(
                    typeof data?.detail === "string"
                        ? data.detail
                        : "Could not update the incident status."
                );
                return;
            }

            const updated = await response.json();
            onStatusChanged(updated.id, updated.status);
        } catch {
            setError("Could not confirm the update. Check your connection.");
        } finally {
            setIsSaving(false);
        }
    }

    return (
        <article className="review-card">
            <header className="review-card-header">
                <div>
                    <h3>{incident.title}</h3>
                    <p className="review-submitter">
                        Submitted by {incident.submitted_by_name || "Unknown user"}
                    </p>
                </div>

                <span className="review-status" data-status={incident.status}>
                    {statusLabels[incident.status]}
                </span>
            </header>

            <p className="review-description">{incident.description}</p>

            <div className="review-actions">
                {incident.status === "open" && (
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
                    className="review-close"
                    disabled={isSaving}
                    onClick={() => updateStatus("closed")}
                >
                    Close incident
                </button>
            </div>

            {error && <p role="alert">{error}</p>}

            <IncidentCommentForm incidentId={incident.id} />
        </article>
    );
}

export default function ReviewersDashboard() {
    const [incidents, setIncidents] = useState([]);
    const [filter, setFilter] = useState("all");
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState("");
    const [notice, setNotice] = useState("");

    useEffect(() => {
        const controller = new AbortController();

        async function loadIncidents() {
            try {
                const response = await fetch("/api/incidents", {
                    signal: controller.signal,
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
                setIncidents(data);
            } catch (err) {
                if (!controller.signal.aborted) {
                    setError(err.message || "Could not load incidents.");
                }
            } finally {
                if (!controller.signal.aborted) {
                    setIsLoading(false);
                }
            }
        }

        loadIncidents();
        return () => controller.abort();
    }, []);

    function handleStatusChanged(id, status) {
        const incident = incidents.find((item) => item.id === id);
        setNotice(`${incident?.title ?? "Incident"} — ${statusLabels[status]}.`);

        setIncidents((current) => {
            if (status === "closed") {
                return current.filter((item) => item.id !== id);
            }

            return current.map((item) =>
                item.id === id ? { ...item, status } : item
            );
        });
    }

    const visibleIncidents = incidents.filter(
        (incident) => filter === "all" || incident.status === filter
    );

    return (
        <section className="reviewers-dashboard">
            <h2>Incident review</h2>

            {isLoading && <p role="status">Loading incidents…</p>}
            {error && <p role="alert">{error}</p>}

            {!isLoading && !error && (
                <>
                    <div className="review-filters" role="group" aria-label="Filter incidents">
                        {filters.map(({ value, label }) => {
                            const count = value === "all"
                                ? incidents.length
                                : incidents.filter((item) => item.status === value).length;

                            return (
                                <button
                                    key={value}
                                    type="button"
                                    aria-pressed={filter === value}
                                    onClick={() => setFilter(value)}
                                >
                                    {label} <span>{count}</span>
                                </button>
                            );
                        })}
                    </div>

                    <p className="review-notice" role="status">{notice}</p>

                    {visibleIncidents.length === 0 && (
                        <p className="review-empty">No incidents in this view.</p>
                    )}

                    {visibleIncidents.map((incident) => (
                        <IncidentCard
                            key={incident.id}
                            incident={incident}
                            onStatusChanged={handleStatusChanged}
                        />
                    ))}
                </>
            )}
        </section>
    );
}