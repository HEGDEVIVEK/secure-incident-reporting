import { useState } from "react";
import CreateUserForm from "./CreateUserForm.jsx";
import AdminIncidents from "./AdminIncidents.jsx";
import AdminComments from "./AdminComments.jsx";
import UpdateRoleTab from "./UpdateRoleTab.jsx";
import AccountStatusTab from "./AccountStatusTab.jsx";
import "./css/AdminDashboard.css";

const tabs = [
    { id: "create", label: "Create account", component: CreateUserForm },
    { id: "incidents", label: "All incidents", component: AdminIncidents },
    { id: "comments", label: "Comments", component: AdminComments },
    { id: "roles", label: "Update role", component: UpdateRoleTab },
    { id: "status", label: "Account status", component: AccountStatusTab },
];

export default function AdminDashboard({ currentUserId }) {
    const [activeTabId, setActiveTabId] = useState("create");

    const activeTab = tabs.find((tab) => tab.id === activeTabId);
    const ActiveComponent = activeTab.component;

    return (
        <div className="admin-dashboard">
            <nav className="admin-tabs" aria-label="Admin dashboard">
                {tabs.map((tab) => (
                    <button
                        key={tab.id}
                        type="button"
                        aria-pressed={tab.id === activeTabId}
                        onClick={() => setActiveTabId(tab.id)}
                    >
                        {tab.label}
                    </button>
                ))}
            </nav>

            <div className="admin-panel">
                <ActiveComponent currentUserId={currentUserId} />
            </div>
        </div>
    );
}