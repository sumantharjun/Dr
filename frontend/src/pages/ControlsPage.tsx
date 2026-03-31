import { useEffect, useState, useCallback } from "react";
import { Settings2, Droplet, Wind, Zap, FlaskConical, Thermometer } from "lucide-react";
import api from "../services/api";
import { Device, WashingCycle, DispenseLog } from "../types";
import { format } from "date-fns";
import { useDeviceSocket } from "../hooks/useDeviceSocket";
import { useToastStore } from "../store/toastStore";
import { useAlertStore } from "../store/alertStore";

const WASH_MODES = [
  { id: "full_cycle", label: "Full Cycle", description: "Wash, Dry, Sterilize & Fill", icon: Zap, color: "border-primary-300 hover:border-primary-500 hover:bg-primary-50", activeColor: "border-primary-500 bg-primary-50" },
  { id: "wash", label: "Wash", description: "Basic washing cycle", icon: Droplet, color: "border-blue-300 hover:border-blue-500 hover:bg-blue-50", activeColor: "border-blue-500 bg-blue-50" },
  { id: "deep_clean", label: "Deep Clean", description: "Wash, Dry & Sterilize", icon: Wind, color: "border-green-300 hover:border-green-500 hover:bg-green-50", activeColor: "border-green-500 bg-green-50" },
  { id: "dispense", label: "Dispense", description: "Dispense milk into bottle", icon: FlaskConical, color: "border-yellow-300 hover:border-yellow-500 hover:bg-yellow-50", activeColor: "border-yellow-500 bg-yellow-50" },
];

export default function ControlsPage() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [selectedDevice, setSelectedDevice] = useState<number | null>(null);
  const [selectedMode, setSelectedMode] = useState<string>("");
  const [washHistory, setWashHistory] = useState<WashingCycle[]>([]);
  const [dispenseHistory, setDispenseHistory] = useState<DispenseLog[]>([]);
  const [dispense, setDispense] = useState({ temperature_c: "37", volume_ml: "120" });
  const [washLoading, setWashLoading] = useState(false);
  const [dispenseLoading, setDispenseLoading] = useState(false);
  // Live progress from WebSocket
  const [activeCycle, setActiveCycle] = useState<{ id: number; progress: number; status: string } | null>(null);
  const [activeDispense, setActiveDispense] = useState<{ id: number; progress: number; status: string } | null>(null);

  const { addToast } = useToastStore();
  const { addAlert } = useAlertStore();

  const handleSocketMessage = useCallback((event: Record<string, unknown>) => {
    if (event.type === "wash_progress") {
      const progress = event.progress_pct as number;
      const status = event.status as string;
      const cycleId = event.cycle_id as number;
      setActiveCycle({ id: cycleId, progress, status });
      if (status === "completed") {
        addToast("Wash cycle completed!", "success");
        setActiveCycle(null);
        fetchHistory();
      } else if (status === "failed") {
        addToast("Wash cycle failed. Check device.", "error");
        setActiveCycle(null);
        fetchHistory();
      }
    } else if (event.type === "dispense_progress") {
      const progress = event.progress_pct as number;
      const status = event.status as string;
      const logId = event.log_id as number;
      setActiveDispense({ id: logId, progress, status });
      if (status === "completed") {
        addToast("Milk dispensed successfully!", "success");
        setActiveDispense(null);
        fetchHistory();
      } else if (status === "failed") {
        addToast("Dispense failed. Check device.", "error");
        setActiveDispense(null);
        fetchHistory();
      }
    } else if (event.type === "alert") {
      const severity = event.severity as "info" | "warning" | "error" | "critical";
      const message = event.message as string;
      addToast(message, severity === "critical" || severity === "error" ? "error" : "warning");
      // Also dispatch browser notification if permission granted
      if (Notification.permission === "granted") {
        new Notification("BabyFeeder Alert", { body: message, icon: "/baby-bottle.svg" });
      }
    }
  }, [addToast, addAlert]);

  useDeviceSocket(selectedDevice, handleSocketMessage);

  useEffect(() => {
    api.get("/devices/").then((r) => {
      setDevices(r.data);
      if (r.data.length > 0) setSelectedDevice(r.data[0].id);
    });
    fetchHistory();
  }, []);

  async function fetchHistory() {
    const [wash, disp] = await Promise.all([
      api.get("/washing/history"),
      api.get("/dispensing/history"),
    ]);
    setWashHistory(wash.data);
    setDispenseHistory(disp.data);
  }

  async function handleStartWash() {
    if (!selectedDevice || !selectedMode) return;
    setWashLoading(true);
    try {
      const { data } = await api.post("/washing/start", { device_id: selectedDevice, mode: selectedMode });
      setActiveCycle({ id: data.id, progress: 0, status: "pending" });
      addToast(`Wash cycle (${selectedMode.replace("_", " ")}) started`, "info");
      fetchHistory();
    } catch (err: any) {
      addToast(err.response?.data?.detail || "Failed to start wash cycle", "error");
    } finally {
      setWashLoading(false);
    }
  }

  async function handleDispense() {
    if (!selectedDevice) return;
    setDispenseLoading(true);
    try {
      const { data } = await api.post("/dispensing/", {
        device_id: selectedDevice,
        temperature_c: Number(dispense.temperature_c),
        volume_ml: Number(dispense.volume_ml),
      });
      setActiveDispense({ id: data.id, progress: 0, status: "pending" });
      addToast(`Dispensing ${dispense.volume_ml}ml at ${dispense.temperature_c}°C…`, "info");
      fetchHistory();
    } catch (err: any) {
      addToast(err.response?.data?.detail || "Failed to dispense", "error");
    } finally {
      setDispenseLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Device Controls</h1>
        <p className="text-gray-500 text-sm mt-1">Control washing cycles and milk dispensing</p>
      </div>

      {/* Device Selector */}
      {devices.length > 1 && (
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">Select Device</label>
          <select
            value={selectedDevice ?? ""}
            onChange={(e) => setSelectedDevice(Number(e.target.value))}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
          >
            {devices.map((d) => (
              <option key={d.id} value={d.id}>{d.device_name} ({d.status})</option>
            ))}
          </select>
        </div>
      )}

      {devices.length === 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 mb-6 text-sm text-yellow-700">
          No devices found. Please pair a device first.
        </div>
      )}

      {/* Live Progress Banners */}
      {activeCycle && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-blue-800">Wash cycle in progress…</p>
            <span className="text-sm font-bold text-blue-700">{activeCycle.progress}%</span>
          </div>
          <div className="w-full bg-blue-100 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all duration-500"
              style={{ width: `${activeCycle.progress}%` }}
            />
          </div>
        </div>
      )}

      {activeDispense && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-green-800">Dispensing milk…</p>
            <span className="text-sm font-bold text-green-700">{activeDispense.progress}%</span>
          </div>
          <div className="w-full bg-green-100 rounded-full h-2">
            <div
              className="bg-green-500 h-2 rounded-full transition-all duration-500"
              style={{ width: `${activeDispense.progress}%` }}
            />
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Washing */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Settings2 className="w-5 h-5 text-primary-600" />
            <h2 className="font-semibold text-gray-900">Washing Cycle</h2>
          </div>
          <p className="text-sm text-gray-500 mb-4">Select a washing mode to start.</p>
          <div className="grid grid-cols-2 gap-3 mb-4">
            {WASH_MODES.map((mode) => (
              <button
                key={mode.id}
                onClick={() => setSelectedMode(mode.id)}
                className={`border-2 rounded-xl p-3 text-left transition-all ${selectedMode === mode.id ? mode.activeColor : mode.color}`}
              >
                <mode.icon className="w-5 h-5 mb-1 text-gray-600" />
                <p className="text-sm font-semibold text-gray-800">{mode.label}</p>
                <p className="text-xs text-gray-500">{mode.description}</p>
              </button>
            ))}
          </div>
          <button
            onClick={handleStartWash}
            disabled={!selectedMode || !selectedDevice || washLoading || !!activeCycle}
            className="w-full bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white py-2.5 rounded-lg text-sm font-medium transition-colors"
          >
            {washLoading ? "Starting..." : activeCycle ? "Cycle running…" : "Start Wash Cycle"}
          </button>
        </div>

        {/* Milk Dispense */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Thermometer className="w-5 h-5 text-primary-600" />
            <h2 className="font-semibold text-gray-900">Milk Dispensing</h2>
          </div>
          <p className="text-sm text-gray-500 mb-4">Set temperature and volume, then dispense.</p>
          <div className="space-y-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Temperature (°C)</label>
              <input
                type="number" min="20" max="45" step="0.5"
                value={dispense.temperature_c}
                onChange={(e) => setDispense({ ...dispense, temperature_c: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
              />
              <p className="text-xs text-gray-400 mt-1">Recommended: 36–38°C (body temperature)</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Volume (ml)</label>
              <input
                type="number" min="10" max="300" step="5"
                value={dispense.volume_ml}
                onChange={(e) => setDispense({ ...dispense, volume_ml: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
              />
            </div>
          </div>
          <button
            onClick={handleDispense}
            disabled={!selectedDevice || dispenseLoading || !!activeDispense}
            className="w-full bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white py-2.5 rounded-lg text-sm font-medium transition-colors"
          >
            {dispenseLoading ? "Sending..." : activeDispense ? "Dispensing…" : "Dispense Milk"}
          </button>
        </div>
      </div>

      {/* Wash History */}
      <div className="mt-6 bg-white rounded-xl border border-gray-200">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">Recent Wash Cycles</h2>
        </div>
        {washHistory.length === 0 ? (
          <p className="text-center text-sm text-gray-400 py-8">No wash cycles yet</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-500 uppercase border-b border-gray-100">
                  <th className="px-5 py-3 text-left">Mode</th>
                  <th className="px-5 py-3 text-left">Status</th>
                  <th className="px-5 py-3 text-left">Progress</th>
                  <th className="px-5 py-3 text-left">Started</th>
                </tr>
              </thead>
              <tbody>
                {washHistory.slice(0, 10).map((c) => (
                  <tr key={c.id} className="border-b border-gray-50">
                    <td className="px-5 py-3 font-medium text-gray-800 capitalize">{c.mode.replace("_", " ")}</td>
                    <td className="px-5 py-3"><StatusBadge status={c.status} /></td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-16 bg-gray-100 rounded-full h-1.5">
                          <div className="bg-primary-500 h-1.5 rounded-full" style={{ width: `${c.progress_pct ?? 0}%` }} />
                        </div>
                        <span className="text-xs text-gray-500">{c.progress_pct ?? 0}%</span>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-gray-500">{format(new Date(c.started_at), "MMM d, h:mm a")}</td>
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

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pending: "bg-yellow-100 text-yellow-700",
    running: "bg-blue-100 text-blue-700",
    completed: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${map[status] || "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  );
}
