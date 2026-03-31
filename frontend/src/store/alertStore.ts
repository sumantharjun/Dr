import { create } from "zustand";
import { DeviceAlert } from "../types";

interface AlertState {
  alerts: DeviceAlert[];
  setAlerts: (alerts: DeviceAlert[]) => void;
  addAlert: (alert: DeviceAlert) => void;
  markRead: (id: number) => void;
  removeAlert: (id: number) => void;
  unreadCount: () => number;
}

export const useAlertStore = create<AlertState>((set, get) => ({
  alerts: [],
  setAlerts: (alerts) => set({ alerts }),
  addAlert: (alert) => set((s) => ({ alerts: [alert, ...s.alerts] })),
  markRead: (id) =>
    set((s) => ({
      alerts: s.alerts.map((a) => (a.id === id ? { ...a, is_read: true } : a)),
    })),
  removeAlert: (id) => set((s) => ({ alerts: s.alerts.filter((a) => a.id !== id) })),
  unreadCount: () => get().alerts.filter((a) => !a.is_read).length,
}));
