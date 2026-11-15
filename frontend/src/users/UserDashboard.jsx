import { useState } from "react";
import IncidentForm from "./IncidentForm.jsx";
import MyIncidents from "./MyIncidents.jsx";
import "./UserDashboard.css";

export default function UserDashboard() {
    const [listVersion, setListVersion] = useState(0);

    function refreshIncidents() {
        setListVersion((version) => version + 1);
    }

    return (
        <div className="user-dashboard">
            <IncidentForm
                onIncidentCreated={refreshIncidents}
            />

            <MyIncidents
                key={listVersion}
                onRefresh={refreshIncidents}
            />
        </div>
    );
}