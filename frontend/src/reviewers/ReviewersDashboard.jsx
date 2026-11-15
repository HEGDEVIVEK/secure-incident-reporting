import { Navigate, NavLink, Route, Routes } from "react-router";

import ReviewerIncidents from "./ReviewerIncidents.jsx";
import ReviewerComments from "./ReviewerComments.jsx";
import "./css/ReviewersDashboard.css";

export default function ReviewersDashboard() {
    return (
        <div className="reviewer-dashboard">
            <nav className="reviewer-tabs" aria-label="Reviewer dashboard">
                <NavLink to="/reviewer/incidents" end>
                    All incidents
                </NavLink>

                <NavLink to="/reviewer/comments" end>
                    Comments & status
                </NavLink>
            </nav>

            <div className="reviewer-panel">
                <Routes>

                    <Route 
                        path="/reviewer/incidents" 
                        element={<ReviewerIncidents />} 
                    />

                    <Route 
                        path="/reviewer/comments" 
                        element={<ReviewerComments />} 
                    />

                    <Route 
                        path="*" 
                        element={<Navigate to="/reviewer/incidents" replace />} 
                    />

                </Routes>
            </div>
        </div>
    );
}