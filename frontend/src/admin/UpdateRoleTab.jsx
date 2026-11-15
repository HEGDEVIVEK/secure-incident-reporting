import AccountTable from "./AccountTable.jsx";
import "./css/UpdateRoleTab.css";

const roleOptions = [
    { value: "user", label: "User" },
    { value: "reviewer", label: "Reviewer" },
    { value: "admin", label: "Admin" },
];

function saveRole(userId, role) {
    return fetch(`/api/users/${userId}/role`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role }),
    });
}

export default function UpdateRoleTab({ currentUserId }) {
    return (
        <section className="update-role-tab">
            <h2>Update role</h2>

            <AccountTable
                currentUserId={currentUserId}
                field="role"
                label="Role"
                options={roleOptions}
                saveChange={saveRole}
            />
        </section>
    );
}