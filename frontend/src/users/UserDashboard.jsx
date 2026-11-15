import { useState } from "react";
import { Navigate, NavLink, Route, Routes } from "react-router";

import IncidentForm from "./IncidentForm.jsx";
import MyIncidents from "./MyIncidents.jsx";
import "./css/UserDashboard.css";

export default function UserDashboard() {
  const [listVersion, setListVersion] = useState(0);

  function refreshIncidents() {
    setListVersion((version) => version + 1);
  }

  return (
    <div className="user-dashboard">
      <nav className="user-tabs" aria-label="User dashboard">
        <NavLink to="/user/report" end>
          Report an incident
        </NavLink>

        <NavLink to="/user/incidents" end>
          My incidents
        </NavLink>
      </nav>

      <div className="user-panel">
        <Routes>
            
          <Route
            path="/user/report"
            element={<IncidentForm onIncidentCreated={refreshIncidents} />}
          />

          <Route
            path="/user/incidents"
            element={<MyIncidents key={listVersion} onRefresh={refreshIncidents} />}
          />

          <Route path="*" element={<Navigate to="/user/report" replace />} />
        </Routes>
      </div>
    </div>
  );
}