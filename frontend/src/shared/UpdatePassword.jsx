import { useState } from "react";
import { Link } from "react-router";
import "./css/LoginPage.css";

export default function UpdatePassword() {
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isUpdated, setIsUpdated] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    if (isSubmitting) return;

    const form = new FormData(event.currentTarget);
    const newPassword = form.get("new_password");

    if (newPassword !== form.get("confirm_password")) {
      setError("The new passwords do not match. Please enter them again.");
      return;
    }

    setError("");
    setIsSubmitting(true);

    try {
      const response = await fetch("/api/update-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: form.get("username"),
          current_password: form.get("current_password"),
          new_password: newPassword,
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        setError(
          typeof data?.detail === "string"
            ? data.detail
            : "Could not update your password. Please check your entries."
        );
        return;
      }

      setIsUpdated(true);
    } catch {
      setError("Could not confirm the update. Try logging in with your new password.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <h1>{isUpdated ? "Password updated" : "Update password"}</h1>

      {isUpdated ? (
        <>
          <p role="status">Your password has been updated successfully.</p>
          <Link to="/login" replace>Log in again</Link>
        </>
      ) : (
        <>
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
              Current password
              <input
                name="current_password"
                type="password"
                autoComplete="current-password"
                maxLength={128}
                required
              />
            </label>

            <label>
              New password
              <input
                name="new_password"
                type="password"
                autoComplete="new-password"
                minLength={12}
                maxLength={128}
                aria-describedby="password-length"
                required
              />
              <small id="password-length">Use at least 12 characters. A short phrase works well.</small>
            </label>

            <label>
              Confirm new password
              <input
                name="confirm_password"
                type="password"
                autoComplete="new-password"
                minLength={12}
                maxLength={128}
                required
              />
            </label>

            {error && <p role="alert">{error}</p>}

            <button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Updating…" : "Update password"}
            </button>
          </form>

          <p><Link to="/login">Back to login</Link></p>
        </>
      )}
    </main>
  );
}