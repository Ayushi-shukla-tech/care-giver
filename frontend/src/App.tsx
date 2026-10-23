import { Navigate, Route, Routes } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import PatientListPage from "./pages/PatientListPage";
import PatientDetailPage from "./pages/PatientDetailPage";
import PairPage from "./pages/PairPage";
import PatientTodayPage from "./pages/PatientTodayPage";
import PrescriptionsPage from "./pages/PrescriptionsPage";
import { getToken } from "./api";

function RequireAuth({ children }: { children: React.ReactNode }) {
  return getToken() ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/pair" element={<PairPage />} />
      <Route path="/patient/today" element={<PatientTodayPage />} />
      <Route
        path="/patients"
        element={
          <RequireAuth>
            <PatientListPage />
          </RequireAuth>
        }
      />
      <Route
        path="/patients/:id"
        element={
          <RequireAuth>
            <PatientDetailPage />
          </RequireAuth>
        }
      />
      <Route
        path="/patients/:id/prescriptions"
        element={
          <RequireAuth>
            <PrescriptionsPage />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
