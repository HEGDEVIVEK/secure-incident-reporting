import { useState } from "react";
import "./IncidentCommentForm.css";

export default function IncidentCommentForm({ incidentId }) {
    const [message, setMessage] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);

    async function handleSubmit(event) {
        event.preventDefault();

        const form = event.currentTarget;
        const text = new FormData(form).get("text").trim();

        if (!text) {
            setMessage("Enter a comment before submitting.");
            return;
        }

        setMessage("");
        setIsSubmitting(true);

        try {
            const response = await fetch(`/api/incidents/${incidentId}/comments`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text }),
            });

            if (!response.ok) {
                const error = await response.json().catch(() => null);
                setMessage(
                    typeof error?.detail === "string"
                        ? error.detail
                        : "Could not save the comment. Please check the text and try again."
                );
                return;
            }

            form.reset();
            setMessage("Comment added.");
        } catch {
            setMessage("Could not confirm whether the comment was saved.");
        } finally {
            setIsSubmitting(false);
        }
    }

    return (
        <form className="incident-comment-form" onSubmit={handleSubmit}>
            <label htmlFor={`comment-${incidentId}`}>Add a comment</label>

            <textarea
                id={`comment-${incidentId}`}
                name="text"
                rows={3}
                maxLength={2000}
                required
            />

            <button type="submit" disabled={isSubmitting}>
                {isSubmitting ? "Saving…" : "Save comment"}
            </button>

            <p role="status">{message}</p>
        </form>
    );
}