import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, CheckCheck, Trash2 } from "lucide-react";
import { clsx } from "clsx";
import api from "../../services/api";
import { useAlertStore } from "../../store/alertStore";
import { useToastStore } from "../../store/toastStore";
import { alertMeta } from "../../types/alerts";
import { AlertTypeIcon, severityIconColor } from "../alerts/AlertIcon";
import { formatDistanceToNow } from "date-fns";

const MAX_ITEMS = 8;

export default function AlertBell() {
  const { alerts, markRead, removeAlert } = useAlertStore();
  const { addToast } = useToastStore();
  const navigate = useNavigate();

  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  const unreadCount = alerts.filter((a) => !a.is_read).length;
  const visible = alerts.slice(0, MAX_ITEMS);

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  async function handleRead(id: number) {
    try {
      await api.put(`/alerts/${id}/read`);
      markRead(id);
    } catch {
      addToast("Failed to mark alert as read", "error");
    }
  }

  async function handleDelete(id: number) {
    try {
      await api.delete(`/alerts/${id}`);
      removeAlert(id);
    } catch {
      addToast("Failed to dismiss alert", "error");
    }
  }

  async function markAllRead() {
    const unread = alerts.filter((a) => !a.is_read);
    if (unread.length === 0) return;
    try {
      await Promise.all(unread.map((a) => api.put(`/alerts/${a.id}/read`)));
      unread.forEach((a) => markRead(a.id));
    } catch {
      addToast("Failed to mark all as read", "error");
    }
  }

  return (
    <div className="relative" ref={wrapRef}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="Alerts"
        className="relative flex items-center justify-center w-9 h-9 rounded-lg text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 && (
          <span className="absolute top-0.5 right-0.5 bg-red-500 text-white text-[10px] rounded-full min-w-[16px] h-4 px-0.5 flex items-center justify-center">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 max-w-[calc(100vw-2rem)] bg-white border border-gray-200 rounded-xl shadow-lg overflow-hidden z-40">
          <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-gray-100">
            <p className="text-sm font-semibold text-gray-800">Alerts</p>
            {unreadCount > 0 && (
              <button
                onClick={markAllRead}
                className="flex items-center gap-1 text-xs text-primary-600 hover:text-primary-700 font-medium"
              >
                <CheckCheck className="w-3.5 h-3.5" />
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-96 overflow-y-auto">
            {visible.length === 0 ? (
              <div className="px-4 py-10 text-center">
                <Bell className="w-8 h-8 mx-auto text-gray-300 mb-2" />
                <p className="text-sm text-gray-500">No alerts</p>
              </div>
            ) : (
              visible.map((alert) => (
                <div
                  key={alert.id}
                  className={clsx(
                    "flex items-start gap-3 px-4 py-3 border-b border-gray-50 last:border-b-0",
                    !alert.is_read && "bg-primary-50/40"
                  )}
                >
                  <div className={clsx("mt-0.5 flex-shrink-0", severityIconColor(alert.severity))}>
                    <AlertTypeIcon alertType={alert.alert_type} severity={alert.severity} className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className={clsx("text-xs", alert.is_read ? "text-gray-500" : "text-gray-800 font-medium")}>
                      {alert.message}
                    </p>
                    <p className="text-[11px] text-gray-400 mt-0.5">
                      {alertMeta(alert.alert_type).label} ·{" "}
                      {formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })}
                    </p>
                  </div>
                  <div className="flex gap-0.5 flex-shrink-0">
                    {!alert.is_read && (
                      <button
                        onClick={() => handleRead(alert.id)}
                        title="Mark as read"
                        className="p-1 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-md"
                      >
                        <CheckCheck className="w-3.5 h-3.5" />
                      </button>
                    )}
                    <button
                      onClick={() => handleDelete(alert.id)}
                      title="Dismiss"
                      className="p-1 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-md"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>

          <button
            onClick={() => {
              setOpen(false);
              navigate("/alerts");
            }}
            className="w-full text-center text-xs font-medium text-primary-600 hover:text-primary-700 hover:bg-gray-50 py-2.5 border-t border-gray-100"
          >
            View all alerts
          </button>
        </div>
      )}
    </div>
  );
}
