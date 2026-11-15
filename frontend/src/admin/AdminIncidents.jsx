import { useEffect, useState } from "react";
import "./css/AdminIncidents.css";

const statusLabels = {
    open: "Open",
    "under-review": "Under review",
    closed: "Closed",
};

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
                setIncidents(data);
            } catch (err) {
                if (!controller.signal.aborted) {
                    setError(err.message);
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
        <section className="admin-incidents">
            <h2>All incidents</h2>

            {loading && <p role="status">Loading incidents…</p>}
            {error && <p role="alert">{error}</p>}

            {!loading && !error && incidents.length === 0 && (
                <p>No incidents have been submitted yet.</p>
            )}

            {incidents.map((incident) => (
                <article key={incident.id} className="admin-incident-card">
                    <header>
                        <h3>{incident.title}</h3>

                        <span className="admin-incident-status" data-status={incident.status}>
                            {statusLabels[incident.status] ?? incident.status}
                        </span>
                    </header>

                    <p className="admin-incident-submitter">
                        Submitted by {incident.submitted_by_name || "Unknown user"}
                    </p>

                    <p className="admin-incident-description">{incident.description}</p>
                </article>
            ))}
        </section>
    );
}