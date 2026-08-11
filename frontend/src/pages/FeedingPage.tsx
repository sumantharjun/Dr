import { useEffect, useState, useCallback } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line,
} from "recharts";
import { Plus, Droplets, Clock, Scale, BarChart3 } from "lucide-react";
import { clsx } from "clsx";
import { PanelSkeleton, Skeleton } from "../components/Skeleton";
import DateTimeField, { toWire } from "../components/DateTimeField";
import api from "../services/api";
import { Device, FeedingAnalytics, FeedingLog, FeedingSchedule, MilkType } from "../types";
import { format, formatDistanceToNow } from "date-fns";
import { useToastStore } from "../store/toastStore";
import { useWsEventStore } from "../store/wsEventStore";
import { useBabyStore, useSelectedBaby } from "../store/babyStore";

/**
 * Single source for the milk-type options and their presentation — the form
 * select and the history badge read from the same list, so a new type added to
 * the backend enum only needs adding here once.
 * Values must match `VALID_MILK_TYPES` in `backend/app/schemas/feeding.py`.
 */
const MILK_TYPES: { value: MilkType; label: string; className: string }[] = [
  { value: "breast_milk", label: "Breast Milk", className: "bg-pink-100 text-pink-700"     },
  { value: "formula",     label: "Formula",     className: "bg-amber-100 text-amber-700"   },
  { value: "cow_milk",    label: "Cow's Milk",  className: "bg-sky-100 text-sky-700"       },
  { value: "mixed",       label: "Mixed",       className: "bg-violet-100 text-violet-700" },
  { value: "other",       label: "Other",       className: "bg-gray-100 text-gray-600"     },
];

export default function FeedingPage() {
  const [logs, setLogs] = useState<FeedingLog[]>([]);
  const [analytics, setAnalytics] = useState<FeedingAnalytics[]>([]);
  const [schedule, setSchedule] = useState<FeedingSchedule | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    baby_id: "",
    milk_consumed_ml: "",
    method: "manual",
    // Deliberately blank: milk type is required, and pre-selecting a value
    // would let a mis-typed feed be saved by simply not touching the field.
    milk_type: "",
    notes: "",
    feed_time: toWire(new Date()),
  });
  const [submitting, setSubmitting] = useState(false);
  const [loadingSchedule, setLoadingSchedule] = useState(true);
  const [loadingAnalytics, setLoadingAnalytics] = useState(true);
  const [loadingLogs, setLoadingLogs] = useState(true);

  const { addToast } = useToastStore();
  const babies = useBabyStore((s) => s.babies);
  const selectedBabyId = useBabyStore((s) => s.selectedId);
  const selectedBaby = useSelectedBaby();
  const weightReadings = useWsEventStore((s) => s.weightReadings);
  const lastFeedingEvent = useWsEventStore((s) => s.lastFeedingEvent);

  // Fired independently rather than as one Promise.all: the schedule cards only
  // need /feeding/schedule, and batching made them wait on the 7-day analytics
  // aggregation and the log list too.
  // Stamp the time when the modal opens, not when the page mounts. `form` is
  // initialised once at mount, so reusing that value would show whenever the
  // page happened to load rather than now.
  const openForm = useCallback(() => {
    setForm((f) => ({
      ...f,
      feed_time: toWire(new Date()),
      // Default to whoever the header is showing — almost always right, and
      // still changeable in the form.
      baby_id: selectedBabyId ? String(selectedBabyId) : "",
    }));
    setShowForm(true);
  }, [selectedBabyId]);

  const fetchAll = useCallback(() => {
    if (selectedBabyId === null) return;
    // Scoped to one baby throughout: twins are on independent schedules, and a
    // combined intake chart or "next feed due" describes neither of them.
    const forBaby = `baby_id=${selectedBabyId}`;
    api.get(`/feeding/schedule?${forBaby}`).then((r) => setSchedule(r.data)).catch(() => {}).finally(() => setLoadingSchedule(false));
    api.get(`/feeding/analytics?days=7&${forBaby}`).then((r) => setAnalytics(r.data)).catch(() => {}).finally(() => setLoadingAnalytics(false));
    api.get(`/feeding/logs?${forBaby}`).then((r) => setLogs(r.data)).catch(() => {}).finally(() => setLoadingLogs(false));
    api.get("/devices/").then((r) => setDevices(r.data)).catch(() => {});
  }, [selectedBabyId]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // Auto-refresh when device posts a new feeding log
  useEffect(() => {
    const hasEvent = Object.values(lastFeedingEvent).some(Boolean);
    if (hasEvent) {
      fetchAll();
      addToast("New feeding logged by device", "info");
    }
  }, [JSON.stringify(lastFeedingEvent)]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.post("/feeding/logs", {
        baby_id: Number(form.baby_id),
        device_id: devices[0]?.id ?? null,
        milk_consumed_ml: form.milk_consumed_ml ? Number(form.milk_consumed_ml) : null,
        method: form.method,
        milk_type: form.milk_type,
        notes: form.notes || null,
        // Send the user's wall-clock time as-is (no UTC conversion). Server
        // stores everything as naive IST per `now_ist()` convention; converting
        // here would offset every feed by the local-to-UTC delta.
        feed_time: form.feed_time,
      });
      setShowForm(false);
      setForm({
        baby_id: selectedBabyId ? String(selectedBabyId) : "",
        milk_consumed_ml: "",
        method: "manual",
        milk_type: "",
        notes: "",
        feed_time: toWire(new Date()),
      });
      addToast("Feeding log saved", "success");
      fetchAll();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      addToast(msg || "Failed to save feeding log", "error");
    } finally {
      setSubmitting(false);
    }
  }

  // Find any live weight reading across devices
  const liveWeightEntry = Object.entries(weightReadings).find(([, v]) => v !== null);
  const liveWeight = liveWeightEntry ? liveWeightEntry[1] : null;
  const liveDeviceId = liveWeightEntry ? Number(liveWeightEntry[0]) : null;
  const liveDevice = devices.find((d) => d.id === liveDeviceId);

  return (
    <div className="p-4 sm:p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between gap-3 mb-6">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-gray-900">Feeding</h1>
          <p className="text-gray-500 text-sm mt-1">
            {babies.length > 1 && selectedBaby
              ? `Tracking ${selectedBaby.name} — switch babies in the header.`
              : "Track and monitor your baby's feeding"}
          </p>
        </div>
        <button
          onClick={openForm}
          className="flex items-center gap-2 bg-primary-600 hover:bg-primary-700 text-white text-sm font-medium px-4 py-2.5 rounded-lg transition-colors flex-shrink-0 whitespace-nowrap"
        >
          <Plus className="w-4 h-4" /> Log Feeding
        </button>
      </div>

      {/* Live weight reading banner */}
      {liveWeight !== null && (
        <div className="bg-sky-50 border border-sky-200 rounded-xl p-4 mb-4 flex items-center gap-3">
          <Scale className="w-5 h-5 text-sky-600 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-sky-800">
              Live scale reading{liveDevice ? ` — ${liveDevice.device_name}` : ""}
            </p>
            <p className="text-xl font-bold text-sky-900">{liveWeight.toFixed(1)} g</p>
          </div>
        </div>
      )}

      {/* Schedule cards */}
      {loadingSchedule && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          <PanelSkeleton />
          <PanelSkeleton />
          <PanelSkeleton />
        </div>
      )}
      {!loadingSchedule && schedule && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          <ScheduleCard
            icon={Droplets}
            label="Last Feed"
            value={
              schedule.last_feed_time
                ? formatDistanceToNow(new Date(schedule.last_feed_time), { addSuffix: true })
                : "—"
            }
            color="text-primary-600 bg-primary-50"
          />
          <ScheduleCard
            icon={Clock}
            label="Time Since Last Feed"
            value={
              schedule.minutes_since_last_feed != null
                ? `${Math.floor(schedule.minutes_since_last_feed / 60)}h ${schedule.minutes_since_last_feed % 60}m`
                : "—"
            }
            color="text-blue-600 bg-blue-50"
          />
          <ScheduleCard
            icon={Clock}
            label="Next Feed Due"
            value={
              schedule.next_feed_due
                ? formatDistanceToNow(new Date(schedule.next_feed_due), { addSuffix: true })
                : "—"
            }
            color="text-green-600 bg-green-50"
          />
        </div>
      )}

      {/* Analytics charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="font-semibold text-gray-900 mb-4">Daily Milk Intake (ml) — Last 7 Days</h2>
          {loadingAnalytics ? (
            <ChartSkeleton />
          ) : analytics.length === 0 ? (
            <EmptyState
              className="h-[200px]"
              icon={BarChart3}
              title="No feeding data yet"
              description="Log a feed to see daily intake here."
              actionLabel="Log Feeding"
              onAction={openForm}
            />
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={analytics}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v) => v.slice(5)} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v: unknown) => [`${v} ml`, "Intake"]} />
                <Bar dataKey="total_ml" fill="#a62cd4" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="font-semibold text-gray-900 mb-4">Feeding Count — Last 7 Days</h2>
          {loadingAnalytics ? (
            <ChartSkeleton />
          ) : analytics.length === 0 ? (
            <EmptyState
              className="h-[200px]"
              icon={BarChart3}
              title="No feeds in the last 7 days"
              description="Log a feed to start building your 7-day trend."
              actionLabel="Log Feeding"
              onAction={openForm}
            />
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={analytics}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v) => v.slice(5)} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip formatter={(v: number) => [v, "Feeds"]} />
                <Line type="monotone" dataKey="feed_count" stroke="#a62cd4" strokeWidth={2} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Manual entry modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl max-h-[90vh] overflow-y-auto">
            <h2 className="font-bold text-lg text-gray-900 mb-4">Log Feeding</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Only shown when there's an actual choice; with one baby the
                  field would be a single-option select asking nothing. */}
              {babies.length > 1 && (
                <div>
                  <label htmlFor="feed-baby" className="block text-sm font-medium text-gray-700 mb-1">
                    Baby <span className="text-red-500" aria-hidden="true">*</span>
                  </label>
                  <select
                    id="feed-baby"
                    required
                    value={form.baby_id}
                    onChange={(e) => setForm({ ...form, baby_id: e.target.value })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
                  >
                    <option value="" disabled>Select baby…</option>
                    {babies.map((b) => (
                      <option key={b.id} value={b.id}>{b.name}</option>
                    ))}
                  </select>
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Time</label>
                <DateTimeField
                  value={form.feed_time}
                  onChange={(v) => setForm({ ...form, feed_time: v })}
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
                <label htmlFor="milk-type" className="block text-sm font-medium text-gray-700 mb-1">
                  Milk Type <span className="text-red-500" aria-hidden="true">*</span>
                </label>
                <select
                  id="milk-type"
                  required
                  value={form.milk_type}
                  onChange={(e) => setForm({ ...form, milk_type: e.target.value })}
                  className={clsx(
                    "w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none",
                    // Grey the placeholder so an unfilled required field reads
                    // as unfilled, not as a chosen value. gray-500 rather than
                    // gray-400: this is the control's actual selected text, not
                    // a true ::placeholder, so it needs to clear 4.5:1 (gray-400
                    // measures 2.54:1 on white).
                    form.milk_type ? "border-gray-300 text-gray-900" : "border-gray-300 text-gray-500",
                  )}
                >
                  <option value="" disabled>Select milk type…</option>
                  {MILK_TYPES.map((t) => (
                    <option key={t.value} value={t.value} className="text-gray-900">
                      {t.label}
                    </option>
                  ))}
                </select>
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
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
                <textarea
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  rows={2}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none resize-none"
                  placeholder="Optional notes…"
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="flex-1 border border-gray-300 rounded-lg py-2.5 text-sm hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex-1 bg-primary-600 text-white rounded-lg py-2.5 text-sm hover:bg-primary-700 disabled:opacity-50 transition-colors"
                >
                  {submitting ? "Saving…" : "Save"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Feeding history table */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="px-5 py-4 border-b border-gray-200">
          <h2 className="font-semibold text-gray-900">Feeding History</h2>
        </div>
        {loadingLogs ? (
          <TableSkeleton />
        ) : logs.length === 0 ? (
          <EmptyState
            className="py-12"
            icon={Droplets}
            title="No feeding logs yet"
            description="Record your first feed to start tracking intake."
            actionLabel="Log Feeding"
            onAction={openForm}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-500 uppercase border-b border-gray-100">
                  <th className="px-5 py-3 text-left">Time</th>
                  <th className="px-5 py-3 text-left">Amount</th>
                  <th className="px-5 py-3 text-left">Milk Type</th>
                  <th className="px-5 py-3 text-left">Method</th>
                  <th className="px-5 py-3 text-left">Notes</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                    <td className="px-5 py-3 text-gray-700">
                      {format(new Date(log.feed_time), "dd MMM, HH:mm")}
                    </td>
                    <td className="px-5 py-3 font-medium text-gray-900">
                      {log.milk_consumed_ml != null ? `${log.milk_consumed_ml} ml` : "—"}
                    </td>
                    <td className="px-5 py-3">
                      <MilkTypeBadge milkType={log.milk_type} />
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

function ScheduleCard({ icon: Icon, label, value, color }: {
  icon: React.ElementType; label: string; value: string; color: string;
}) {
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

// Static class strings — Tailwind only picks up arbitrary values it can see in
// the source, so these can't be built from a template literal.
const BAR_HEIGHTS = ["h-[45%]", "h-[70%]", "h-[35%]", "h-[85%]", "h-[55%]", "h-[75%]", "h-[60%]"];

/** Chart placeholder. Same 200px height as the chart and EmptyState so the card never resizes. */
function ChartSkeleton() {
  return (
    <div className="h-[200px] flex items-end gap-3 px-2 pb-6">
      {BAR_HEIGHTS.map((h, i) => (
        <Skeleton key={i} className={`flex-1 ${h}`} />
      ))}
    </div>
  );
}

/** Row placeholders for the feeding history table. */
function TableSkeleton() {
  return (
    <div className="divide-y divide-gray-100">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="flex items-center gap-4 px-5 py-3.5">
          <Skeleton className="h-3.5 w-32" />
          <Skeleton className="h-3.5 w-16" />
          <Skeleton className="h-3.5 w-24" />
          <Skeleton className="h-3.5 w-20" />
          <Skeleton className="h-3.5 flex-1" />
        </div>
      ))}
    </div>
  );
}

/**
 * Empty state that prompts an action instead of just reporting absence.
 * `onAction` is optional — omit it to render the message without a button.
 */
function EmptyState({ icon: Icon, title, description, actionLabel, onAction, className }: {
  icon: React.ElementType;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}) {
  return (
    <div
      className={clsx(
        "flex flex-col items-center justify-center text-center gap-1.5 px-4",
        className,
      )}
    >
      <Icon className="w-8 h-8 text-gray-300" />
      <p className="text-sm font-medium text-gray-500">{title}</p>
      <p className="text-xs text-gray-400 max-w-[15rem]">{description}</p>
      {onAction && actionLabel && (
        <button
          onClick={onAction}
          className="mt-2 flex items-center gap-1.5 bg-primary-600 hover:bg-primary-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" /> {actionLabel}
        </button>
      )}
    </div>
  );
}

/**
 * Renders "—" rather than a badge when the type is unknown (pre-existing logs,
 * device-reported feeds), so absent data doesn't masquerade as a recorded value.
 */
function MilkTypeBadge({ milkType }: { milkType: MilkType | null }) {
  const meta = MILK_TYPES.find((t) => t.value === milkType);
  if (!meta) return <span className="text-gray-400">—</span>;
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${meta.className}`}>
      {meta.label}
    </span>
  );
}

function MethodBadge({ method }: { method: string }) {
  const map: Record<string, string> = {
    device: "bg-primary-100 text-primary-700",
    manual: "bg-blue-100 text-blue-700",
    breast: "bg-pink-100 text-pink-700",
    other:  "bg-gray-100 text-gray-600",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${map[method] || map.other}`}>
      {method}
    </span>
  );
}
