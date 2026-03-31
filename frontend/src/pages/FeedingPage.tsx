import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line,
} from "recharts";
import { Plus, Droplets, Clock } from "lucide-react";
import api from "../services/api";
import { Device, FeedingAnalytics, FeedingLog, FeedingSchedule } from "../types";
import { format, formatDistanceToNow } from "date-fns";

export default function FeedingPage() {
  const [logs, setLogs] = useState<FeedingLog[]>([]);
  const [analytics, setAnalytics] = useState<FeedingAnalytics[]>([]);
  const [schedule, setSchedule] = useState<FeedingSchedule | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    device_id: "",
    milk_consumed_ml: "",
    method: "manual",
    notes: "",
    feed_time: new Date().toISOString().slice(0, 16),
  });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchAll();
  }, []);

  async function fetchAll() {
    const [logsRes, analyticsRes, scheduleRes, devicesRes] = await Promise.all([
      api.get("/feeding/logs"),
      api.get("/feeding/analytics?days=7"),
      api.get("/feeding/schedule"),
      api.get("/devices/"),
    ]);
    setLogs(logsRes.data);
    setAnalytics(analyticsRes.data);
    setSchedule(scheduleRes.data);
    setDevices(devicesRes.data);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.post("/feeding/logs", {
        device_id: form.device_id ? Number(form.device_id) : null,
        milk_consumed_ml: form.milk_consumed_ml ? Number(form.milk_consumed_ml) : null,
        method: form.method,
        notes: form.notes || null,
        feed_time: new Date(form.feed_time).toISOString(),
      });
      setShowForm(false);
      fetchAll();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Feeding</h1>
          <p className="text-gray-500 text-sm mt-1">Track and monitor your baby's feeding</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 bg-primary-600 hover:bg-primary-700 text-white text-sm font-medium px-4 py-2.5 rounded-lg"
        >
          <Plus className="w-4 h-4" /> Log Feeding
        </button>
      </div>

      {/* Schedule card */}
      {schedule && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          <ScheduleCard
            icon={Droplets}
            label="Last Feed"
            value={schedule.last_feed_time
              ? formatDistanceToNow(new Date(schedule.last_feed_time), { addSuffix: true })
              : "No data"}
            color="text-primary-600 bg-primary-50"
          />
          <ScheduleCard
            icon={Clock}
            label="Time Since Last Feed"
            value={schedule.minutes_since_last_feed != null
              ? `${Math.floor(schedule.minutes_since_last_feed / 60)}h ${schedule.minutes_since_last_feed % 60}m`
              : "—"}
            color="text-blue-600 bg-blue-50"
          />
          <ScheduleCard
            icon={Clock}
            label="Next Feed Due"
            value={schedule.next_feed_due
              ? formatDistanceToNow(new Date(schedule.next_feed_due), { addSuffix: true })
              : "—"}
            color="text-green-600 bg-green-50"
          />
        </div>
      )}

      {/* Analytics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="font-semibold text-gray-900 mb-4">Daily Milk Intake (ml) — Last 7 Days</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={analytics}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v) => v.slice(5)} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: any) => [`${v} ml`, "Intake"]} />
              <Bar dataKey="total_ml" fill="#a62cd4" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="font-semibold text-gray-900 mb-4">Feeding Count — Last 7 Days</h2>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={analytics}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v) => v.slice(5)} />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
              <Tooltip formatter={(v: any) => [v, "Feeds"]} />
              <Line type="monotone" dataKey="feed_count" stroke="#a62cd4" strokeWidth={2} dot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Manual Entry Form */}
      {showForm && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl">
            <h2 className="font-bold text-lg text-gray-900 mb-4">Log Feeding</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Time</label>
                <input
                  type="datetime-local"
                  value={form.feed_time}
                  onChange={(e) => setForm({ ...form, feed_time: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Milk Amount (ml)</label>
                <input
                  type="number"
                  min="0"
                  step="0.5"
                  value={form.milk_consumed_ml}
                  onChange={(e) => setForm({ ...form, milk_consumed_ml: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
                  placeholder="e.g. 120"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Method</label>
                <select
                  value={form.method}
                  onChange={(e) => setForm({ ...form, method: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
                >
                  <option value="manual">Bottle (Manual)</option>
                  <option value="device">Device</option>
                  <option value="breast">Breastfeeding</option>
                  <option value="other">Other</option>
                </select>
              </div>
              {devices.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Device (optional)</label>
                  <select
                    value={form.device_id}
                    onChange={(e) => setForm({ ...form, device_id: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
                  >
                    <option value="">None</option>
                    {devices.map((d) => (
                      <option key={d.id} value={d.id}>{d.device_name}</option>
                    ))}
                  </select>
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
                <textarea
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  rows={2}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none resize-none"
                  placeholder="Optional notes..."
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="flex-1 border border-gray-300 rounded-lg py-2.5 text-sm hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex-1 bg-primary-600 text-white rounded-lg py-2.5 text-sm hover:bg-primary-700 disabled:opacity-50"
                >
                  {submitting ? "Saving..." : "Save"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Feeding Log Table */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="px-5 py-4 border-b border-gray-200">
          <h2 className="font-semibold text-gray-900">Feeding History</h2>
        </div>
        {logs.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <Droplets className="w-10 h-10 mx-auto mb-2 opacity-40" />
            <p className="text-sm">No feeding logs yet</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-500 uppercase border-b border-gray-100">
                  <th className="px-5 py-3 text-left">Time</th>
                  <th className="px-5 py-3 text-left">Amount</th>
                  <th className="px-5 py-3 text-left">Method</th>
                  <th className="px-5 py-3 text-left">Notes</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="px-5 py-3 text-gray-700">
                      {format(new Date(log.feed_time), "MMM d, h:mm a")}
                    </td>
                    <td className="px-5 py-3 font-medium text-gray-900">
                      {log.milk_consumed_ml != null ? `${log.milk_consumed_ml} ml` : "—"}
                    </td>
                    <td className="px-5 py-3">
                      <MethodBadge method={log.method} />
                    </td>
                    <td className="px-5 py-3 text-gray-500 max-w-xs truncate">{log.notes || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function ScheduleCard({ icon: Icon, label, value, color }: any) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-3">
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-xs text-gray-500">{label}</p>
        <p className="text-sm font-semibold text-gray-900">{value}</p>
      </div>
    </div>
  );
}

function MethodBadge({ method }: { method: string }) {
  const map: Record<string, string> = {
    device: "bg-primary-100 text-primary-700",
    manual: "bg-blue-100 text-blue-700",
    breast: "bg-pink-100 text-pink-700",
    other: "bg-gray-100 text-gray-600",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${map[method] || map.other}`}>
      {method}
    </span>
  );
}
