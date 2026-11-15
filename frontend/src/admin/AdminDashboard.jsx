import { Navigate, NavLink, Route, Routes } from "react-router";
import CreateUserForm from "./CreateUserForm.jsx";
import AdminIncidents from "./AdminIncidents.jsx";
import AdminComments from "./AdminComments.jsx";
import UpdateRoleTab from "./UpdateRoleTab.jsx";
import AccountStatusTab from "./AccountStatusTab.jsx";
import "./css/AdminDashboard.css";

const tabs = [
  { path: "/admin/create-account", label: "Create account", component: CreateUserForm },
  { path: "/admin/incidents", label: "All incidents", component: AdminIncidents },
  { path: "/admin/comments", label: "Comments", component: AdminComments },
  { path: "/admin/account-roles", label: "Update role", component: UpdateRoleTab },
  { path: "/admin/account-status", label: "Account status", component: AccountStatusTab },
];

export default function AdminDashboard({ currentUserId }) {
  return (
    <div className="admin-dashboard">
      <nav className="admin-tabs" aria-label="Admin dashboard">
        {tabs.map(({ path, label }) => (
          <NavLink key={path} to={path} end>
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="admin-panel">
        <Routes>
          {tabs.map(({ path, component: Page }) => (
            <Route
              key={path}
              path={path}
              element={<Page currentUserId={currentUserId} />}
            />
          ))}

          <Route path="*" element={<Navigate to="/admin/create-account" replace />} />
        </Routes>
      </div>
    </div>
  );
}