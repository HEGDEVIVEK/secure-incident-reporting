import IncidentList from "../shared/IncidentList.jsx";

export default function ReviewerIncidents() {
  return <IncidentList endpoint="/api/incidents" />;
}