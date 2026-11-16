import IncidentList from "../shared/IncidentList.jsx";

export default function AdminIncidents() {
  return <IncidentList endpoint="/api/incidents" />;
}