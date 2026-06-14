import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Droplets, Cpu, Bell, Clock, Zap, Waves, AlertTriangle } from "lucide-react";
import api from "../services/api";
import { Device, FeedingSchedule, DeviceAlert } from "../types";
import { formatDistanceToNow } from "date-fns";
import { useAuthStore } from "../store/authStore";
import { useBabyStore } from "../store/babyStore";
import Mascot from "../components/Mascot";

interface MetricsSummary {
  total_cycles: number;
  total_power_kwh: number;
  total_water_liters: number;
  power_saved_kwh: number;
  water_saved_liters: number;
}

function SkeletonCard() {
  return (
    <div className="bg-white rounded-xl p-5 border border-gray-200 flex items-center gap-4 animate-pulse">
      <div className="w-12 h-12 rounded-xl bg-gray-200" />
      <div className="space-y-2">
        <div className="h-3 w-20 bg-gray-200 rounded" />
        <div className="h-5 w-28 bg-gray-200 rounded" />
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, color, to }: {
  icon: React.ElementType; label: string; value: string | number; color: string; to: string;
}) {
  return (
    <Link
      to={to}
      className="bg-white rounded-xl p-5 border border-gray-200 hover:shadow-md transition-shadow flex items-center gap-4"
    >
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${color}`}>
        <Icon className="w-6 h-6 text-white" />
      </div>
      <div>
        <p className="text-sm text-gray-500">{label}</p>
        <p className="text-xl font-bold text-gray-900">{value}</p>
      </div>
    </Link>
  );
}

export default function DashboardPage() {
  const { user } = useAuthStore();
  const { baby } = useBabyStore();
  const [devices, setDevices] = useState<Device[]>([]);
  const [schedule, setSchedule] = useState<FeedingSchedule | null>(null);
  const [alerts, setAlerts] = useState<DeviceAlert[]>([]);
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get("/devices/").then((r) => setDevices(r.data)),
      api.get("/feeding/schedule").then((r) => setSchedule(r.data)),
      api.get("/alerts/").then((r) => setAlerts(r.data)),
      api.get("/metrics/summary").then((r) => setMetrics(r.data)).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  const device = devices[0] ?? null;
  const deviceLabel = !device
    ? "Not paired"
    : device.status === "online"
    ? "Online"
    : "Offline";
  const unreadAlerts = alerts.filter((a) => !a.is_read).length;

  return (
    <div className="p-4 sm:p-6 max-w-5xl mx-auto">
      <div className="mb-6 flex items-center gap-4">
        <Mascot variant="auto" size={72} className="flex-shrink-0 hidden sm:block" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Good {getGreeting()}, {user?.full_name?.split(" ")[0]}
          </h1>
          <p className="text-gray-500 text-sm mt-1">
            {baby?.name
              ? `Here's what's happening with ${baby.name}.`
              : "Here's what's happening with your baby's feeding."}
          </p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {loading ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : (
          <>
            <StatCard
              icon={Cpu}
              label="Device"
              value={deviceLabel}
              color={
                !device
                  ? "bg-gray-400"
                  : device.status === "online"
                  ? "bg-green-500"
                  : "bg-gray-400"
              }
              to="/devices"
            />
            <StatCard
              icon={Droplets}
              label="Last Feed"
              value={
                schedule?.last_feed_time
                  ? formatDistanceToNow(new Date(schedule.last_feed_time), { addSuffix: true })
                  : "No data"
              }
              color="bg-primary-500"
              to="/feeding"
            />
            <StatCard
              icon={Clock}
              label="Next Feed Due"
              value={
                schedule?.next_feed_due
                  ? formatDistanceToNow(new Date(schedule.next_feed_due), { addSuffix: true })
                  : "—"
              }
              color="bg-green-500"
              to="/feeding"
            />
            <StatCard
              icon={Bell}
              label="Unread Alerts"
              value={unreadAlerts}
              color={unreadAlerts > 0 ? "bg-red-500" : "bg-gray-400"}
              to="/alerts"
            />
          </>
        )}
      </div>

      {/* Environmental savings */}
      {!loading && metrics && (metrics.power_saved_kwh > 0 || metrics.water_saved_liters > 0) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
          <div className="bg-gradient-to-br from-yellow-50 to-amber-50 border border-yellow-200 rounded-xl p-5 flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-yellow-400 flex items-center justify-center">
              <Zap className="w-6 h-6 text-white" />
            </div>
            <div>
              <p className="text-sm text-yellow-700">Energy Saved</p>
              <p className="text-xl font-bold text-yellow-900">{metrics.power_saved_kwh.toFixed(2)} kWh</p>
              <p className="text-xs text-yellow-600">across {metrics.total_cycles} wash cycles</p>
            </div>
          </div>
          <div className="bg-gradient-to-br from-blue-50 to-cyan-50 border border-blue-200 rounded-xl p-5 flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-blue-400 flex items-center justify-center">
              <Waves className="w-6 h-6 text-white" />
            </div>
            <div>
              <p className="text-sm text-blue-700">Water Saved</p>
              <p className="text-xl font-bold text-blue-900">{metrics.water_saved_liters.toFixed(1)} L</p>
              <p className="text-xs text-blue-600">vs standard sterilizer baseline</p>
            </div>
          </div>
        </div>
      )}

      {/* Device & Alert panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-900">Device</h2>
            <Link to="/devices" className="text-sm text-primary-600 hover:underline">Manage</Link>
          </div>
          {loading ? (
            <div className="space-y-3">
              {[1, 2].map((i) => (
                <div key={i} className="flex items-center justify-between animate-pulse">
                  <div className="space-y-1.5">
                    <div className="h-3 w-32 bg-gray-200 rounded" />
                    <div className="h-2.5 w-24 bg-gray-100 rounded" />
                  </div>
                  <div className="h-5 w-16 bg-gray-200 rounded-full" />
                </div>
              ))}
            </div>
          ) : devices.length === 0 ? (
            <div className="text-center py-8 text-gray-400">
              <Cpu className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No device paired yet</p>
              <Link to="/devices" className="text-primary-600 text-sm hover:underline mt-1 block">
                Pair your device
              </Link>
            </div>
          ) : (
            <ul className="space-y-3">
              {devices.slice(0, 1).map((d) => (
                <li key={d.id} className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-800">{d.device_name}</p>
                    <p className="text-xs text-gray-400">{d.mac_address}</p>
                  </div>
                  <StatusBadge status={d.status} />
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-900">Recent Alerts</h2>
            <Link to="/alerts" className="text-sm text-primary-600 hover:underline">View all</Link>
          </div>
          {loading ? (
            <div className="space-y-3">
              {[1, 2].map((i) => (
                <div key={i} className="flex items-start gap-3 animate-pulse">
                  <div className="w-4 h-4 mt-0.5 bg-gray-200 rounded-full flex-shrink-0" />
                  <div className="space-y-1.5 flex-1">
                    <div className="h-3 w-full bg-gray-200 rounded" />
                    <div className="h-2.5 w-20 bg-gray-100 rounded" />
                  </div>
                </div>
              ))}
            </div>
          ) : alerts.length === 0 ? (
            <div className="text-center py-8 text-gray-400">
              <Bell className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No alerts</p>
            </div>
          ) : (
            <ul className="space-y-3">
              {alerts.slice(0, 5).map((a) => (
                <li key={a.id} className="flex items-start gap-3">
                  <AlertTriangle
                    className={`w-4 h-4 mt-0.5 flex-shrink-0 ${severityColor(a.severity)}`}
                  />
                  <div>
                    <p className={`text-sm font-medium ${a.is_read ? "text-gray-500" : "text-gray-900"}`}>
                      {a.message}
                    </p>
                    <p className="text-xs text-gray-400">
                      {formatDistanceToNow(new Date(a.created_at), { addSuffix: true })}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: Device["status"] }) {
  const map: Record<string, string> = {
    online:  "bg-green-100 text-green-700",
    offline: "bg-gray-100 text-gray-500",
    pairing: "bg-yellow-100 text-yellow-700",
    error:   "bg-red-100 text-red-700",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${map[status] || map.offline}`}>
      {status}
    </span>
  );
}

function severityColor(severity: string) {
  return (
    { info: "text-blue-500", warning: "text-yellow-500", error: "text-red-500", critical: "text-red-700" }[severity]
    || "text-gray-500"
  );
}

function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return "morning";
  if (h < 17) return "afternoon";
  return "evening";
}
