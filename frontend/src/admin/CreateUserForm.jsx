import { useState } from "react";
import "./css/CreateUserForm.css";

export default function CreateUserForm() {
    const [message, setMessage] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);

    async function handleSubmit(event) {
        event.preventDefault();

        const form = event.currentTarget;
        const fields = new FormData(form);

        setMessage("");
        setIsSubmitting(true);

        try {
            const response = await fetch("/api/add_users", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    username: fields.get("username"),
                    password: fields.get("password"),
                    role: fields.get("role"),
                }),
            });

            if (!response.ok) {
                const errors = {
                    401: "Your session has expired. Please sign in again.",
                    403: "Admin access is required to create an account.",
                    409: "That username already exists. Choose another username.",
                    422: "Check the username, password length, and role.",
                };

                setMessage(errors[response.status] ?? "Could not create the account.");
                return;
            }

            const account = await response.json();
            form.reset();
            setMessage(`Created account for ${account.username}.`);
        } catch {
            setMessage("Could not confirm account creation. Check your connection.");
        } finally {
            setIsSubmitting(false);
        }
    }

    return (
        <section className="create-user">
            <h2>Create account</h2>

            <form onSubmit={handleSubmit}>
                <label>
                    Username
                    <input
                        name="username"
                        minLength={3}
                        maxLength={64}
                        pattern="[a-z0-9_]+"
                        title="Use 3–64 lowercase letters, numbers, or underscores."
                        required
                    />
                </label>

                <label>
                    Password (5–128 characters)
                    <input
                        name="password"
                        type="password"
                        autoComplete="new-password"
                        minLength={5}
                        maxLength={128}
                        required
                    />
                </label>

                <label>
                    Role
                    <select name="role" defaultValue="user">
                        <option value="user">User</option>
                        <option value="reviewer">Reviewer</option>
                        <option value="admin">Admin</option>
                    </select>
                </label>

                <button type="submit" disabled={isSubmitting}>
                    {isSubmitting ? "Creating…" : "Create account"}
                </button>
            </form>

            <p role="status">{message}</p>
        </section>
    );
}