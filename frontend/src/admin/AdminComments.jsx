import { useEffect, useState } from "react";
import IncidentCommentForm from "../shared/IncidentCommentForm.jsx";
import "./css/AdminComments.css";

export default function AdminComments() {
    const [incidents, setIncidents] = useState([]);
    const [selectedId, setSelectedId] = useState("");
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

    const selectedIncident = incidents.find((incident) => incident.id === selectedId);

    return (
        <section className="admin-comments">
            <h2>Comments</h2>

            {loading && <p role="status">Loading incidents…</p>}
            {error && <p role="alert">{error}</p>}

            {!loading && !error && incidents.length === 0 && (
                <p>No incidents have been submitted yet.</p>
            )}

            {!loading && !error && incidents.length > 0 && (
                <label className="admin-incident-picker">
                    Select an incident
                    <select
                        value={selectedId}
                        onChange={(event) => setSelectedId(event.target.value)}
                    >
                        <option value="">Choose an incident</option>

                        {incidents.map((incident) => (
                            <option key={incident.id} value={incident.id}>
                                {incident.title} · {incident.id.slice(-6)}
                            </option>
                        ))}
                    </select>
                </label>
            )}

            {selectedIncident && (
                <article>
                    <h3>{selectedIncident.title}</h3>

                    <p className="admin-comment-meta">
                        Submitted by {selectedIncident.submitted_by_name || "Unknown user"}
                        {" · "}
                        {selectedIncident.status.replace("-", " ")}
                    </p>

                    <p className="admin-comment-description">
                        {selectedIncident.description}
                    </p>

                    <IncidentCommentForm
                        key={selectedIncident.id}
                        incidentId={selectedIncident.id}
                    />
                </article>
            )}
        </section>
    );
}