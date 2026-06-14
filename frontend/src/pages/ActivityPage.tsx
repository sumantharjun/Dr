import { useEffect, useState, useCallback } from "react";
import { Activity, Cpu, RefreshCw, Clock } from "lucide-react";
import api from "../services/api";
import { Device, ActivityLog } from "../types";
import { formatDistanceToNow, format } from "date-fns";

const EVENT_META: Record<string, { label: string; dot: string; badge: string }> = {
  wash_started:        { label: "Wash Started",         dot: "bg-blue-500",   badge: "bg-blue-100 text-blue-700" },
  wash_completed:      { label: "Wash Completed",       dot: "bg-green-500",  badge: "bg-green-100 text-green-700" },
  wash_failed:         { label: "Wash Failed",          dot: "bg-red-500",    badge: "bg-red-100 text-red-700" },
  dispense_started:    { label: "Dispense Started",     dot: "bg-purple-500", badge: "bg-purple-100 text-purple-700" },
  dispense_completed:  { label: "Dispense Completed",   dot: "bg-green-500",  badge: "bg-green-100 text-green-700" },
  dispense_failed:     { label: "Dispense Failed",      dot: "bg-red-500",    badge: "bg-red-100 text-red-700" },
  alert_triggered:     { label: "Alert Triggered",      dot: "bg-red-400",    badge: "bg-red-100 text-red-700" },
  network_reconnected: { label: "Network Reconnected",  dot: "bg-yellow-500", badge: "bg-yellow-100 text-yellow-700" },
  device_online:       { label: "Device Online",        dot: "bg-green-500",  badge: "bg-green-100 text-green-700" },
  device_offline:      { label: "Device Offline",       dot: "bg-gray-400",   badge: "bg-gray-100 text-gray-600" },
  feeding_logged:      { label: "Feeding Logged",       dot: "bg-sky-500",    badge: "bg-sky-100 text-sky-700" },
};

function getMeta(eventType: string) {
  return (
    EVENT_META[eventType] ?? {
      label: eventType.replace(/_/g, " "),
      dot: "bg-gray-400",
      badge: "bg-gray-100 text-gray-600",
    }
  );
}

export default function ActivityPage() {
  const [device, setDevice] = useState<Device | null>(null);
  const selectedId = device?.id ?? null;
  const [logs, setLogs] = useState<ActivityLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/devices/").then((r) => {
      setDevice(r.data[0] ?? null);
    });
  }, []);

  const fetchLogs = useCallback(async () => {
    if (!selectedId) return;
    setLoading(true);
    setError("");
    try {
      const { data } = await api.get(`/activity/${selectedId}?limit=100`);
      setLogs(data);
    } catch {
      setError("Failed to load activity logs.");
    } finally {
      setLoading(false);
    }
  }, [selectedId]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const selectedDevice = device;

  return (
    <div className="p-4 sm:p-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Activity Log</h1>
          <p className="text-gray-500 text-sm mt-1">Device event history and activity timeline</p>
        </div>
        <button
          onClick={fetchLogs}
          disabled={loading}
          className="flex items-center gap-2 text-sm text-primary-600 hover:text-primary-700 font-medium disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* No device */}
      {!device && (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <Cpu className="w-12 h-12 mx-auto text-gray-300 mb-3" />
          <p className="text-gray-500">No device paired. Pair your device to see activity logs.</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl p-4 mb-4">
          {error}
        </div>
      )}

      {/* Device info bar */}
      {selectedDevice && (
        <div className="flex items-center gap-3 mb-4 px-4 py-3 bg-gray-50 rounded-xl border border-gray-100">
          <Cpu className="w-4 h-4 text-gray-400" />
          <span className="text-sm font-medium text-gray-700">{selectedDevice.device_name}</span>
          <span className="text-xs font-mono text-gray-400">{selectedDevice.mac_address}</span>
          <span
            className={`ml-auto text-xs px-2 py-0.5 rounded-full font-medium ${
              selectedDevice.status === "online"
                ? "bg-green-100 text-green-700"
                : "bg-gray-100 text-gray-500"
            }`}
          >
            {selectedDevice.status}
          </span>
        </div>
      )}

      {/* Empty state */}
      {device && !loading && logs.length === 0 && !error && (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <Activity className="w-12 h-12 mx-auto text-gray-300 mb-3" />
          <p className="text-gray-500 font-medium">No activity recorded yet</p>
          <p className="text-gray-400 text-sm mt-1">Events will appear here once the device starts reporting.</p>
        </div>
      )}

      {/* Activity timeline */}
      {logs.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="divide-y divide-gray-50">
            {logs.map((log, idx) => {
              const meta = getMeta(log.event_type);
              const isFirst = idx === 0;
              const isLast = idx === logs.length - 1;

              return (
                <div key={log.id} className="flex items-start gap-4 px-5 py-4 hover:bg-gray-50 transition-colors">
                  {/* Timeline dot + line */}
                  <div className="flex flex-col items-center flex-shrink-0 pt-1">
                    <div className={`w-2.5 h-2.5 rounded-full ${meta.dot} ring-2 ring-white`} />
                    {!isLast && <div className="w-px flex-1 bg-gray-100 mt-1 min-h-[1.5rem]" />}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0 pb-1">
                    <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full capitalize ${meta.badge}`}>
                        {meta.label}
                      </span>
                    </div>
                    {log.description && (
                      <p className="text-sm text-gray-700 mt-0.5 leading-snug">{log.description}</p>
                    )}
                  </div>

                  {/* Timestamps */}
                  <div className="flex-shrink-0 text-right pt-0.5">
                    <p className="text-xs text-gray-400">
                      {formatDistanceToNow(new Date(log.recorded_at), { addSuffix: true })}
                    </p>
                    <p className="text-xs text-gray-300 mt-0.5 flex items-center gap-1 justify-end">
                      <Clock className="w-3 h-3" />
                      {format(new Date(log.recorded_at), "dd MMM, HH:mm")}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Footer */}
          <div className="px-5 py-3 bg-gray-50 border-t border-gray-100 text-xs text-gray-400">
            Showing last {logs.length} event{logs.length !== 1 ? "s" : ""}
          </div>
        </div>
      )}
    </div>
  );
}
