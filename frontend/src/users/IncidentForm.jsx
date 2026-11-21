import { useState } from "react";
import "./css/IncidentForm.css";

import { apiFetch } from "../shared/api.js";

export default function IncidentForm({ onIncidentCreated }) {
    const [message, setMessage] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);

    async function handleSubmit(event) {
        event.preventDefault();

        const form = event.currentTarget;
        const fields = new FormData(form);
        const title = fields.get("title").trim();
        const priority = fields.get("priority");
        const description = fields.get("description").trim();

        if (!title || !description) {
            setMessage("Enter a title and description for the incident.");
            return;
        }

        setMessage("");
        setIsSubmitting(true);

        try {
            const response = await apiFetch("/api/add_incidents", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title, description, priority }),
            });

            if (response.status === 401) {
                setMessage("Your session has expired. Please sign in again.");
                return;
            }

            if (!response.ok) {
                setMessage("Could not submit the incident. Please check the form and try again.");
                return;
            }

            const incident = await response.json();
            form.reset();
            setMessage(`Incident submitted. Reference ID: ${incident.id}.`);
            onIncidentCreated();
        } catch {
            setMessage("Could not confirm submission. Check your connection.");
        } finally {
            setIsSubmitting(false);
        }
    }

    return (
        <section className="incident-form">
            {/* <h2>Report an incident</h2> */}

            <form onSubmit={handleSubmit}>
                <label htmlFor="incident-title">Title</label>
                <input
                    id="incident-title"
                    name="title"
                    maxLength={200}
                    placeholder="Briefly summarize the incident"
                    required
                />

                <label htmlFor="incident-description">Description</label>
                <textarea
                    id="incident-description"
                    name="description"
                    rows={6}
                    maxLength={5000}
                    placeholder="Describe what happened"
                    required
                />

                <label htmlFor="incident-priority">Priority</label>
                <select id="incident-priority" name="priority" defaultValue="" required>
                    <option value="" disabled>Select priority</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                </select>

                <button type="submit" disabled={isSubmitting}>
                    {isSubmitting ? "Submitting…" : "Submit incident"}
                </button>
            </form>

            <p role="status">{message}</p>
        </section>
    );
}