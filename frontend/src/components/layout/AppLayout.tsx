import { useEffect, useState } from "react";
import { Outlet, Navigate } from "react-router-dom";
import Sidebar from "./Sidebar";
import ToastContainer from "./ToastContainer";
import { useAuthStore } from "../../store/authStore";
import { useAlertStore } from "../../store/alertStore";
import { useGlobalSocket } from "../../hooks/useGlobalSocket";
import api from "../../services/api";
import { Device } from "../../types";

export default function AppLayout() {
  const { token, user, setUser } = useAuthStore();
  const { setAlerts } = useAlertStore();
  const [deviceIds, setDeviceIds] = useState<number[]>([]);

  // Single global WebSocket pool for all devices — lives for the entire session
  useGlobalSocket(deviceIds);

  useEffect(() => {
    if (!token) return;

    // Restore user profile after page refresh if missing from localStorage
    if (!user) {
      api.get("/auth/me").then((r) => setUser(r.data)).catch(() => {});
    }

    // Load all devices and start WebSocket connections for each
    api
      .get("/devices/")
      .then((r) => setDeviceIds(r.data.map((d: Device) => d.id)))
      .catch(() => {});

    // Populate the alert store so the sidebar badge is accurate immediately
    api.get("/alerts/").then((r) => setAlerts(r.data)).catch(() => {});

    // Request browser push-notification permission once
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!token) return <Navigate to="/login" replace />;

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
      <ToastContainer />
    </div>
  );
}
