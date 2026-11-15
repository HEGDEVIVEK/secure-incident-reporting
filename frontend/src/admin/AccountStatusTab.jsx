import AccountTable from "./AccountTable.jsx";
import "./css/AccountStatusTab.css";

const statusOptions = [
    { value: "true", label: "Active" },
    { value: "false", label: "Inactive" },
];

function saveStatus(userId, selectedValue) {
  return fetch(`/api/users/${userId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_active: selectedValue === "true" }),
  });
}

export default function AccountStatusTab({ currentUserId }) {
    return (
        <section className="account-status-tab">
            {/* <h2>Account status</h2> */}

            <AccountTable
                currentUserId={currentUserId}
                field="is_active"
                label="Status"
                options={statusOptions}
                saveChange={saveStatus}
            />
        </section>
    );
}