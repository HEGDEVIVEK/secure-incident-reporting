import { useEffect, useState } from "react";
import "./css/AccountTable.css";

function AccountRow({
    user,
    currentUserId,
    field,
    label,
    options,
    saveChange,
    onSaved,
}) {
    const savedValue = String(user[field]);
    const [selectedValue, setSelectedValue] = useState(savedValue);
    const [isSaving, setIsSaving] = useState(false);
    const [message, setMessage] = useState("");

    const isOwnAccount = user.id === currentUserId;
    const hasChanges = selectedValue !== savedValue;
    const savedLabel = options.find((option) => option.value === savedValue)?.label;

    async function handleUpdate() {
        setIsSaving(true);
        setMessage("");

        try {
            const response = await saveChange(user.id, selectedValue);
            const data = await response.json().catch(() => null);

            if (!response.ok) {
                setMessage(
                    typeof data?.detail === "string"
                        ? data.detail
                        : "Could not update this account."
                );
                return;
            }

            if (data?.[field] === undefined) {
                setMessage("Could not confirm the saved value. Reopen this tab to check.");
                return;
            }

            onSaved(user.id, data[field]);
            setSelectedValue(String(data[field]));
            setMessage("Updated.");
        } catch {
            setMessage("Could not confirm the update. Check your connection.");
        } finally {
            setIsSaving(false);
        }
    }

    return (
        <tr>
            <th scope="row">{user.username}</th>

            <td>
                {isOwnAccount ? (
                    savedLabel
                ) : (
                    <select
                        aria-label={`${label} for ${user.username}`}
                        value={selectedValue}
                        disabled={isSaving}
                        onChange={(event) => {
                            setSelectedValue(event.target.value);
                            setMessage("");
                        }}
                    >
                        {options.map((option) => (
                            <option key={option.value} value={option.value}>
                                {option.label}
                            </option>
                        ))}
                    </select>
                )}
            </td>

            <td className="account-table-action">
                {!isOwnAccount && hasChanges && (
                    <button
                        type="button"
                        onClick={handleUpdate}
                        disabled={isSaving}
                        aria-label={`Update ${label.toLowerCase()} for ${user.username}`}
                    >
                        {isSaving ? "Updating…" : "Update"}
                    </button>
                )}

                <span role="status">{message}</span>
            </td>
        </tr>
    );
}

export default function AccountTable({
    currentUserId,
    field,
    label,
    options,
    saveChange,
}) {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        const controller = new AbortController();

        async function loadUsers() {
            try {
                const response = await fetch("/api/list_users", {
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
                setUsers(data);
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

        loadUsers();
        return () => controller.abort();
    }, []);

    function handleSaved(userId, savedValue) {
        setUsers((current) =>
            current.map((user) =>
                user.id === userId ? { ...user, [field]: savedValue } : user
            )
        );
    }

    if (loading) return <p role="status">Loading accounts…</p>;
    if (error) return <p role="alert">{error}</p>;
    if (users.length === 0) return <p>No user accounts found.</p>;

    return (
        <div className="account-table-scroll">
            <table className="account-table">
                <thead>
                    <tr>
                        <th scope="col">Username</th>
                        <th scope="col">{label}</th>
                        <th scope="col">Action</th>
                    </tr>
                </thead>

                <tbody>
                    {users.map((user) => (
                        <AccountRow
                            key={user.id}
                            user={user}
                            currentUserId={currentUserId}
                            field={field}
                            label={label}
                            options={options}
                            saveChange={saveChange}
                            onSaved={handleSaved}
                        />
                    ))}
                </tbody>
            </table>
        </div>
    );
}