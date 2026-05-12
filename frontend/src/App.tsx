import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout";
import ErrorBoundary from "./components/ErrorBoundary";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import DashboardPage from "./pages/DashboardPage";
import DevicesPage from "./pages/DevicesPage";
import FeedingPage from "./pages/FeedingPage";
import ControlsPage from "./pages/ControlsPage";
import AlertsPage from "./pages/AlertsPage";
import OrdersPage from "./pages/OrdersPage";
import ActivityPage from "./pages/ActivityPage";

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route element={<AppLayout />}>
            <Route path="/dashboard" element={<ErrorBoundary><DashboardPage /></ErrorBoundary>} />
            <Route path="/devices"   element={<ErrorBoundary><DevicesPage /></ErrorBoundary>} />
            <Route path="/feeding"   element={<ErrorBoundary><FeedingPage /></ErrorBoundary>} />
            <Route path="/controls"  element={<ErrorBoundary><ControlsPage /></ErrorBoundary>} />
            <Route path="/alerts"    element={<ErrorBoundary><AlertsPage /></ErrorBoundary>} />
            <Route path="/orders"    element={<ErrorBoundary><OrdersPage /></ErrorBoundary>} />
            <Route path="/activity"  element={<ErrorBoundary><ActivityPage /></ErrorBoundary>} />
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
