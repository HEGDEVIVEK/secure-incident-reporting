import IncidentList from "../shared/IncidentList.jsx";

export default function MyIncidents() {
  return (
    <IncidentList
      endpoint="/api/incidents/mine"
      heading="My incidents"
      showSubmittedBy={false}
      emptyMessage="You haven’t submitted any incidents yet."
    />
  );
}