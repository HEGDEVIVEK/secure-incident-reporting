import { useState } from "react";

import AdminDashboard from "./admin/AdminDashboard.jsx";
import ReviewersDashboard from "./reviewers/ReviewersDashboard.jsx";
import UserDashboard from "./users/UserDashboard.jsx";
import LoginPage from "./shared/LoginPage.jsx";


import "./App.css";

export default function App() {
  const [user, setUser] = useState(null);
  const [message, setMessage] = useState("");
  const [isSigningOut, setIsSigningOut] = useState(false);

  function handleLogin(signedInUser) {
    setMessage("");
    setUser(signedInUser);
  }

  async function handleLogout() {
    setMessage("");
    setIsSigningOut(true);

    try {
      const response = await fetch("/api/logout", { method: "POST" });

      if (!response.ok) {
        setMessage("Could not confirm logout. Please try again.");
        return;
      }

      setMessage("You have signed out.");
      setUser(null);
    } catch {
      setMessage("Could not reach the server. Please try again.");
    } finally {
      setIsSigningOut(false);
    }
  }

  if (!user) {
    return <LoginPage onLogin={handleLogin} initialMessage={message} />;
  }

  return (
    <>
      <header className="app-header">
        <div className="app-header-inner">
          <div className="app-header-identity">
            <h1>Incident Reporting</h1>
            <p><strong>{user.username}</strong></p>
          </div>

          <button
            className="app-logout"
            type="button"
            onClick={handleLogout}
            disabled={isSigningOut}
          >
            {isSigningOut ? "Signing out…" : "Log out"}
          </button>
        </div>
      </header>

      <main className="app-content">
        {message && <p className="app-error" role="alert">{message}</p>}

        {user.role === "admin" && <AdminDashboard currentUserId={user.id} />}
        {user.role === "reviewer" && <ReviewersDashboard />}
        {user.role === "user" && <UserDashboard />}
      </main>
    </>
  );
}