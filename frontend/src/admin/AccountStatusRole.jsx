import { useEffect, useState } from "react";
import "./css/AccountStatusRole.css";

import { apiFetch } from "../shared/api.js";

const roleOptions = [
  { value: "user", label: "User" },
  { value: "reviewer", label: "Reviewer" },
  { value: "admin", label: "Admin" },
];

function AccountRow({ user, currentUserId, onSaved }) {
  const [role, setRole] = useState(user.role);
  const [isActive, setIsActive] = useState(user.is_active);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const isOwnAccount = user.id === currentUserId;
  const hasChanges = role !== user.role || isActive !== user.is_active;

  const roleLabel =
    roleOptions.find((option) => option.value === user.role)?.label ??
    user.role;

  function clearFeedback() {
    setMessage("");
    setError("");
  }

  async function handleUpdate() {
    if (isOwnAccount || isSaving || !hasChanges) return;

    setIsSaving(true);
    clearFeedback();

    try {
      const response = await apiFetch(`/api/users/${user.id}/status-role`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          role,
          is_active: isActive,
        }),
      });

      const data = await response.json().catch(() => null);

      if (!response.ok) {
        setError(
          typeof data?.detail === "string"
            ? data.detail
            : "Could not update this account."
        );
        return;
      }

      const validRole = roleOptions.some(
        (option) => option.value === data?.role
      );

      if (
        data?.id !== user.id ||
        !validRole ||
        typeof data?.is_active !== "boolean"
      ) {
        setError(
          "Could not confirm the saved values. Reopen this tab to check."
        );
        return;
      }

      onSaved(user.id, {
        role: data.role,
        is_active: data.is_active,
      });

      setRole(data.role);
      setIsActive(data.is_active);
      setMessage("Updated.");
    } catch {
      setError("Could not confirm the update. Check your connection.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <tr>
      <th scope="row">
        {user.username}
        {isOwnAccount && (
          <span className="account-table-you">You</span>
        )}
      </th>

      <td>
        {isOwnAccount ? (
          roleLabel
        ) : (
          <select
            aria-label={`Role for ${user.username}`}
            value={role}
            disabled={isSaving}
            onChange={(event) => {
              setRole(event.target.value);
              clearFeedback();
            }}
          >
            {roleOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        )}
      </td>

      <td>
        {isOwnAccount ? (
          user.is_active ? "Active" : "Inactive"
        ) : (
          <select
            aria-label={`Status for ${user.username}`}
            value={String(isActive)}
            disabled={isSaving}
            onChange={(event) => {
              setIsActive(event.target.value === "true");
              clearFeedback();
            }}
          >
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        )}
      </td>

      <td className="account-table-action">
        {isOwnAccount ? (
          <span className="account-table-protected">Protected</span>
        ) : (
          <>
            {hasChanges && (
              <button
                type="button"
                onClick={handleUpdate}
                disabled={isSaving}
                aria-label={`Update account for ${user.username}`}
              >
                {isSaving ? "Updating…" : "Update"}
              </button>
            )}

            {message && (
              <span className="account-table-success" role="status">
                {message}
              </span>
            )}

            {error && (
              <span className="account-table-error" role="alert">
                {error}
              </span>
            )}
          </>
        )}
      </td>
    </tr>
  );
}

export default function AccountStatusRole({ currentUserId }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retryCount, setRetryCount] = useState(0);
  const [roleFilter, setRoleFilter] = useState("all");

  useEffect(() => {
    const controller = new AbortController();

    async function loadUsers() {
      setLoading(true);
      setError("");

      try {
        const response = await apiFetch("/api/list_users", {
          signal: controller.signal,
          cache: "no-store",
        });

        if (!response.ok) {
          const data = await response.json().catch(() => null);

          throw new Error(
            typeof data?.detail === "string"
              ? data.detail
              : "Could not load user accounts."
          );
        }

        const data = await response.json();

        if (!controller.signal.aborted) {
          setUsers(data);
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(err.message || "Could not reach the server.");
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    loadUsers();
    return () => controller.abort();
  }, [retryCount]);

  function handleSaved(userId, changes) {
    setUsers((previous) =>
      previous.map((user) =>
        user.id === userId ? { ...user, ...changes } : user
      )
    );
  }

  const filteredUsers = users.filter(
  (user) => roleFilter === "all" || user.role === roleFilter
);

  if (loading) {
    return <p role="status">Loading accounts…</p>;
  }

  if (error) {
    return (
      <div>
        <p role="alert">{error}</p>
        <button
          type="button"
          onClick={() => setRetryCount((count) => count + 1)}
        >
          Retry
        </button>
      </div>
    );
  }

  if (users.length === 0) {
    return <p>No user accounts found.</p>;
  }

  return (
    <section className="account-status-role">
        <div className="account-role-filter">
            <label htmlFor="account-role-filter">Filter by role</label>

            <select
                id="account-role-filter"
                value={roleFilter}
                onChange={(event) => setRoleFilter(event.target.value)}
            >
                <option value="all" >All users</option>
                <option value="admin">Admin</option>
                <option value="user">User</option>
                <option value="reviewer">Reviewer</option>
            </select>
        </div>
      <div
        className="account-table-scroll"
        role="region"
        aria-label="User account management"
        tabIndex={0}
      >
        <table className="account-table">
          <thead>
            <tr>
              <th scope="col">Username</th>
              <th scope="col">Role</th>
              <th scope="col">Status</th>
              <th scope="col">Action</th>
            </tr>
          </thead>

        <tbody>
            {filteredUsers.map((user) => (
                <AccountRow
                key={user.id}
                user={user}
                currentUserId={currentUserId}
                onSaved={handleSaved}
                />
            ))}

            {filteredUsers.length === 0 && (
                <tr>
                <td colSpan={4}>
                    <p role="status">No accounts match the selected role.</p>
                </td>
                </tr>
            )}
        </tbody>

        </table>
      </div>
    </section>
  );
}