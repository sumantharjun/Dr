import { useEffect, useState } from "react";
import { Outlet, Navigate, useLocation } from "react-router-dom";
import { Menu } from "lucide-react";
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
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  // Close the mobile drawer whenever the route changes (e.g. back/forward
  // navigation, or a link tapped outside the sidebar).
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

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
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top header bar — hamburger (mobile) + theme toggle, visible on every page */}
        <header className="h-14 flex items-center gap-2 px-4 border-b border-gray-200 dark:border-gray-800 bg-white/70 dark:bg-gray-900/70 backdrop-blur sticky top-0 z-30">
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label="Open menu"
            className="lg:hidden p-2 -ml-2 rounded-lg text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex-1" />
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
