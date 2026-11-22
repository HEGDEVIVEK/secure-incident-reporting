import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { Navigate, Route, Routes } from "react-router";

import { SESSION_EXPIRED_EVENT } from "./shared/api.js";

import AdminDashboard from "./admin/AdminDashboard.jsx";
import ReviewersDashboard from "./reviewers/ReviewersDashboard.jsx";
import UserDashboard from "./users/UserDashboard.jsx";
import LoginPage from "./shared/LoginPage.jsx";
import UpdatePassword from "./shared/UpdatePassword.jsx";
import ThemeToggle from "./shared/ThemeToggle.jsx";
import "./App.css";

const roleLabels = { admin: "Admin", reviewer: "Reviewer", user: "User" };

export default function App() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [message, setMessage] = useState("");
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [sessionState, setSessionState] = useState("loading");
  const [restoreAttempt, setRestoreAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    async function restoreSession() {
      try {
        const response = await fetch("/api/me", {
          credentials: "same-origin",
          cache: "no-store",
          signal: controller.signal,
        });

        if (response.status === 401) {
          if (!controller.signal.aborted) {
            setUser(null);
            setSessionState("ready");
          }
          return;
        }

        if (!response.ok) {
          throw new Error("Session check failed");
        }

        const data = await response.json();

        if (!controller.signal.aborted) {
          setUser(data.user);
          setSessionState("ready");
        }
      } catch {
        if (!controller.signal.aborted) {
          setSessionState("error");
        }
      }
    }

    restoreSession();

    return () => controller.abort();
  }, [restoreAttempt]);

  useEffect(() => {
  function handleSessionExpired() {
    setUser(null);
    setMessage("Your session is no longer valid. Please sign in again.");
    setSessionState("ready");
    navigate("/login", { replace: true });
  }

  window.addEventListener(
    SESSION_EXPIRED_EVENT,
    handleSessionExpired
  );

  return () => {
    window.removeEventListener(
      SESSION_EXPIRED_EVENT,
      handleSessionExpired
    );
  };
}, [navigate]);

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
      navigate("/", { replace: true });
    } catch {
      setMessage("Could not reach the server. Please try again.");
    } finally {
      setIsSigningOut(false);
    }
  }

  if (!user) {
    if (sessionState === "loading") {
  return (
    <main className="login-page">
      <p role="status">Checking your session…</p>
    </main>
  );
}

    if (sessionState === "error") {
      return (
        <main className="login-page">
          <p role="alert">
            Could not check your session. Please try again.
          </p>

          <button
            type="button"
            onClick={() => {
              setSessionState("loading");
              setRestoreAttempt((attempt) => attempt + 1);
            }}
          >
            Retry
          </button>
        </main>
      );
    }

  return (
    <>
      <ThemeToggle className="theme-toggle-floating" />
      <Routes>
        <Route
          path="/login"
          element={<LoginPage onLogin={handleLogin} initialMessage={message} />}
        />
        <Route path="/update-password" element={<UpdatePassword />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </>
  );
}

  return (
    <>
      <header className="app-header">
        <div className="app-header-inner">
          <div className="app-header-identity">
            <h1>Secure Incident Reporting</h1>
          </div>

          <div className="app-header-account">
            <p>
              <strong>{user.username}</strong>
              <span className="app-role-badge" data-role={user.role}>
                {roleLabels[user.role] ?? user.role}
              </span>
            </p>

            <ThemeToggle className="theme-toggle-on-bar" />

            <button
              className="app-logout"
              type="button"
              onClick={handleLogout}
              disabled={isSigningOut}
            >
              {isSigningOut ? "Signing out…" : "Log out"}
            </button>
          </div>
        </div>
      </header>

      <main className="app-content">
        {message && (
          <p className="app-error" role="alert">
            {message}
          </p>
        )}

        {user.role === "admin" && <AdminDashboard currentUserId={user.id} />}
        {user.role === "reviewer" && <ReviewersDashboard />}
        {user.role === "user" && <UserDashboard />}
      </main>
    </>
  );
}