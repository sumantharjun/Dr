import { useEffect, useState } from "react";
import { Outlet, Navigate } from "react-router-dom";
import Sidebar from "./Sidebar";
import ToastContainer from "./ToastContainer";
import ThemeToggle from "../ThemeToggle";
import { useAuthStore } from "../../store/authStore";
import { useAlertStore } from "../../store/alertStore";
import { useThemeStore } from "../../store/themeStore";
import { useGlobalSocket } from "../../hooks/useGlobalSocket";
import api from "../../services/api";
import { Device } from "../../types";

export default function AppLayout() {
  const { token, user, setUser } = useAuthStore();
  const { setAlerts } = useAlertStore();
  const themeMode = useThemeStore((s) => s.theme);
  const [deviceIds, setDeviceIds] = useState<number[]>([]);

  // Keep the <html> `dark` class in lockstep with the store's theme. This is the
  // single source of truth, so the class can't drift from the toggle state
  // (e.g. after the early main.tsx apply or a dev HMR re-init).
  useEffect(() => {
    document.documentElement.classList.toggle("dark", themeMode === "dark");
  }, [themeMode]);

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
    <div className="flex min-h-screen bg-gray-50 dark:bg-gray-950">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top header bar — holds the theme toggle, visible on every page */}
        <header className="h-14 flex items-center justify-end gap-2 px-4 border-b border-gray-200 dark:border-gray-800 bg-white/70 dark:bg-gray-900/70 backdrop-blur sticky top-0 z-30">
          <ThemeToggle />
        </header>
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
      <ToastContainer />
    </div>
  );
}
