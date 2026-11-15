import { useEffect, useState } from "react";
import "./css/MyIncidents.css";

const statusLabels = {
    open: "Open",
    "under-review": "Under review",
    closed: "Closed",
};

export default function MyIncidents({ onRefresh }) {
    const [incidents, setIncidents] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        const controller = new AbortController();

        async function loadIncidents() {
            try {
                const response = await fetch("/api/incidents/mine", {
                    signal: controller.signal,
                });

                if (response.status === 401) {
                    setError("Your session has expired. Please sign in again.");
                    return;
                }

                if (!response.ok) {
                    setError("Could not load your incidents. Click Refresh to try again.");
                    return;
                }

                const data = await response.json();
                setIncidents(data);
            } catch {
                if (!controller.signal.aborted) {
                    setError("Could not reach the server. Click Refresh to try again.");
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

    return (
        <section className="my-incidents">
            <header className="my-incidents-header">
                <h2>My incidents</h2>
                <button type="button" onClick={onRefresh} disabled={isLoading}>
                    Refresh
                </button>
            </header>

            {isLoading && <p role="status">Loading your incidents…</p>}
            {error && <p role="alert">{error}</p>}

            {!isLoading && !error && incidents.length === 0 && (
                <p>You haven’t submitted any incidents yet.</p>
            )}

            {incidents.map((incident) => (
                <article key={incident.id} className="my-incident-card">
                    <header>
                        <h3>{incident.title}</h3>
                        <span className="incident-status" data-status={incident.status}>
                            {statusLabels[incident.status] ?? incident.status}
                        </span>
                    </header>

                    <p className="my-incident-text">{incident.description}</p>

                    <h4>Comments ({incident.comments.length})</h4>
                    {incident.comments.length === 0 ? (
                        <p className="no-comments">No comments yet.</p>
                    ) : (
                        <ul>
                            {incident.comments.map((comment) => (
                                <li key={comment.id}>
                                    <strong>{comment.username}</strong>
                                    <p className="my-incident-text">{comment.text}</p>
                                </li>
                            ))}
                        </ul>
                    )}
                </article>
            ))}
        </section>
    );
}