import { useEffect } from "react";
import { Bell, CheckCheck, Trash2, AlertTriangle, Info, Zap } from "lucide-react";
import api from "../services/api";
import { useAlertStore } from "../store/alertStore";
import { useToastStore } from "../store/toastStore";
import { formatDistanceToNow } from "date-fns";

export default function AlertsPage() {
  const { alerts, setAlerts, markRead, removeAlert } = useAlertStore();
  const { addToast } = useToastStore();

  useEffect(() => {
    // Sync with server on every visit so temp IDs from WS are replaced with real ones
    api.get("/alerts/").then((r) => setAlerts(r.data)).catch(() => {});
  }, [setAlerts]);

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

  const unreadCount = alerts.filter((a) => !a.is_read).length;

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Alerts</h1>
          <p className="text-gray-500 text-sm mt-1">
            {unreadCount > 0
              ? `${unreadCount} unread alert${unreadCount > 1 ? "s" : ""}`
              : "All caught up"}
          </p>
        </div>
        {unreadCount > 0 && (
          <button
            onClick={markAllRead}
            className="flex items-center gap-2 text-sm text-primary-600 hover:text-primary-700 font-medium"
          >
            <CheckCheck className="w-4 h-4" />
            Mark all read
          </button>
        )}
      </div>

      {alerts.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <Bell className="w-12 h-12 mx-auto text-gray-300 mb-3" />
          <p className="text-gray-500">No alerts</p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((alert) => (
            <div
              key={alert.id}
              className={`bg-white rounded-xl border p-4 flex items-start gap-4 transition-all ${
                alert.is_read ? "border-gray-100 opacity-70" : "border-gray-200 shadow-sm"
              }`}
            >
              <div className={`mt-0.5 flex-shrink-0 ${severityIconColor(alert.severity)}`}>
                <SeverityIcon severity={alert.severity} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span
                    className={`text-xs font-medium px-2 py-0.5 rounded-full ${severityBadge(alert.severity)}`}
                  >
                    {alert.severity}
                  </span>
                  <span className="text-xs text-gray-400 uppercase tracking-wide">
                    {alert.alert_type.replace(/_/g, " ")}
                  </span>
                </div>
                <p className={`text-sm ${alert.is_read ? "text-gray-500" : "text-gray-800 font-medium"}`}>
                  {alert.message}
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  {formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })}
                </p>
              </div>
              <div className="flex gap-1 flex-shrink-0">
                {!alert.is_read && (
                  <button
                    onClick={() => handleRead(alert.id)}
                    title="Mark as read"
                    className="p-1.5 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                  >
                    <CheckCheck className="w-4 h-4" />
                  </button>
                )}
                <button
                  onClick={() => handleDelete(alert.id)}
                  title="Dismiss"
                  className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SeverityIcon({ severity }: { severity: string }) {
  if (severity === "info") return <Info className="w-5 h-5" />;
  if (severity === "critical") return <Zap className="w-5 h-5" />;
  return <AlertTriangle className="w-5 h-5" />;
}

function severityIconColor(severity: string) {
  return (
    { info: "text-blue-500", warning: "text-yellow-500", error: "text-red-500", critical: "text-red-700" }[
      severity
    ] || "text-gray-400"
  );
}

function severityBadge(severity: string) {
  return (
    {
      info: "bg-blue-100 text-blue-700",
      warning: "bg-yellow-100 text-yellow-700",
      error: "bg-red-100 text-red-700",
      critical: "bg-red-200 text-red-800",
    }[severity] || "bg-gray-100 text-gray-600"
  );
}
