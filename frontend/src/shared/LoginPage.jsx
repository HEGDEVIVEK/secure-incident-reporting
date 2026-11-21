import { useState } from "react";
import { Link } from "react-router";
import "./css/LoginPage.css";

export default function LoginPage({ onLogin, initialMessage = "" }) {
    const [message, setMessage] = useState(initialMessage);
    const [isSubmitting, setIsSubmitting] = useState(false);

    async function handleSubmit(event) {
        event.preventDefault();

        const form = new FormData(event.currentTarget);
        setMessage("");
        setIsSubmitting(true);

        try {
            const response = await fetch("/api/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    username: form.get("username"),
                    password: form.get("password"),
                }),
            });

            if (response.status === 401) {
                setMessage("Invalid username or password.");
                return;
            }

            if (response.status === 429) {
                setMessage("Too many failed attempts. Please wait 15 minutes and try again.");
                return;
            }

            if (!response.ok) {
                setMessage("Unable to sign in. Please try again.");
                return;
            }

            const data = await response.json();
            onLogin(data.user);
        } catch {
            setMessage("Could not reach the server. Please try again.");
        } finally {
            setIsSubmitting(false);
        }
    }

    return (
        <main className="login-page">
            <h1>Incident Reporting Login</h1>

            <form onSubmit={handleSubmit}>
                <label>
                    Username
                    <input
                        name="username"
                        autoComplete="username"
                        maxLength={64}
                        required
                    />
                </label>

                <label>
                    Password
                    <input
                        name="password"
                        type="password"
                        autoComplete="current-password"
                        maxLength={128}
                        required
                    />
                </label>

                <button type="submit" disabled={isSubmitting}>
                    {isSubmitting ? "Signing in…" : "Log in"}
                </button>
            </form>

            <Link className="login-change-password" to="/update-password">
                Change password
            </Link>

            <p role="status">{message}</p>
        </main>
    );
}