import { useEffect, useState, useCallback } from "react";
import { Settings2, Wind, Zap, Thermometer, Square, Sparkles } from "lucide-react";
import api from "../services/api";
import { Device, WashingCycle, DispenseLog } from "../types";
import { format, formatDistanceToNow } from "date-fns";
import { useToastStore } from "../store/toastStore";
import { useWsEventStore } from "../store/wsEventStore";

const WASH_MODES = [
  { id: "full_cycle",  label: "Full Cycle",  description: "Wash, Dry, Sterilize & Fill", icon: Zap,         color: "border-primary-300 hover:border-primary-500 hover:bg-primary-50",  activeColor: "border-primary-500 bg-primary-50"  },
  { id: "steam_dry",   label: "Steam & Dry", description: "Steam clean, then dry",        icon: Wind,        color: "border-green-300 hover:border-green-500 hover:bg-green-50",        activeColor: "border-green-500 bg-green-50"       },
  { id: "dry",         label: "Dry",         description: "Dry only",                     icon: Thermometer, color: "border-blue-300 hover:border-blue-500 hover:bg-blue-50",           activeColor: "border-blue-500 bg-blue-50"         },
];

export default function ControlsPage() {
  const [device, setDevice] = useState<Device | null>(null);
  const selectedDevice = device?.id ?? null;
  const [selectedMode, setSelectedMode] = useState<string>("");
  const [washHistory, setWashHistory] = useState<WashingCycle[]>([]);
  const [dispenseHistory, setDispenseHistory] = useState<DispenseLog[]>([]);
  const [dispense, setDispense] = useState({ temperature_c: "37", volume_ml: "120", scoop_number: "" });
  const [washLoading, setWashLoading] = useState(false);
  const [dispenseLoading, setDispenseLoading] = useState(false);
  const [stopLoading, setStopLoading] = useState<"wash" | "dispense" | null>(null);
  const [uvLoading, setUvLoading] = useState(false);

  const { addToast } = useToastStore();

  // Real-time progress from global WebSocket (via wsEventStore)
  const washProg = useWsEventStore((s) => (selectedDevice ? s.washProgress[selectedDevice] : null));
  const dispenseProg = useWsEventStore((s) => (selectedDevice ? s.dispenseProgress[selectedDevice] : null));

  const fetchHistory = useCallback(async () => {
    const [wash, disp] = await Promise.all([
      api.get("/washing/history"),
      api.get("/dispensing/history"),
    ]);
    setWashHistory(wash.data);
    setDispenseHistory(disp.data);

    // Hydrate any in-flight operation into the progress store so the live
    // card + Stop button appear even after a page reload (we can't rely on
    // having received the original WS start event). Only seed when the store
    // is empty for that device, so we never clobber a live update.
    const store = useWsEventStore.getState();
    const activeWash = (wash.data as WashingCycle[]).find(
      (c) => c.status === "pending" || c.status === "running"
    );
    if (activeWash && !store.washProgress[activeWash.device_id]) {
      store.setWashProgress(activeWash.device_id, {
        cycle_id: activeWash.id,
        progress: activeWash.progress_pct ?? 0,
        status: activeWash.status,
      });
    }
    const activeDisp = (disp.data as DispenseLog[]).find(
      (d) => d.status === "pending" || d.status === "dispensing"
    );
    if (activeDisp && !store.dispenseProgress[activeDisp.device_id]) {
      store.setDispenseProgress(activeDisp.device_id, {
        log_id: activeDisp.id,
        progress: activeDisp.progress_pct ?? 0,
        status: activeDisp.status,
      });
    }
  }, []);

  useEffect(() => {
    api.get("/devices/").then((r) => {
      setDevice(r.data[0] ?? null);
    });
    fetchHistory();
  }, [fetchHistory]);

  // Refresh history when wash cycle finishes and clear the progress indicator
  useEffect(() => {
    if (!washProg) return;
    if (washProg.status === "completed" || washProg.status === "failed") {
      fetchHistory();
      const timer = setTimeout(() => {
        if (selectedDevice) useWsEventStore.getState().setWashProgress(selectedDevice, null);
      }, 2500);
      return () => clearTimeout(timer);
    }
  }, [washProg?.status, selectedDevice, fetchHistory]); // eslint-disable-line react-hooks/exhaustive-deps

  // Refresh history when dispense finishes
  useEffect(() => {
    if (!dispenseProg) return;
    if (dispenseProg.status === "completed" || dispenseProg.status === "failed") {
      fetchHistory();
      const timer = setTimeout(() => {
        if (selectedDevice) useWsEventStore.getState().setDispenseProgress(selectedDevice, null);
      }, 2500);
      return () => clearTimeout(timer);
    }
  }, [dispenseProg?.status, selectedDevice, fetchHistory]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleStartWash() {
    if (!selectedDevice || !selectedMode) return;
    setWashLoading(true);
    try {
      const { data } = await api.post("/washing/start", { device_id: selectedDevice, mode: selectedMode });
      useWsEventStore.getState().setWashProgress(selectedDevice, {
        cycle_id: data.id,
        progress: 0,
        status: "pending",
      });
      addToast(`Wash (${selectedMode.replace(/_/g, " ")}) started`, "info");
      fetchHistory();
    } catch (err: unknown) {
      const resp = (err as { response?: { status?: number; data?: any } })?.response;
      // 409 means a cycle is already active — surface that as info, not an
      // error, and pin the live progress card to the existing cycle so the
      // user immediately sees the right state.
      if (resp?.status === 409 && resp.data?.active_cycle_id) {
        const d = resp.data;
        useWsEventStore.getState().setWashProgress(selectedDevice, {
          cycle_id: d.active_cycle_id,
          progress: 0,
          status: d.active_cycle_status ?? "pending",
        });
        const ago = d.active_cycle_started_at
          ? formatDistanceToNow(new Date(d.active_cycle_started_at), { addSuffix: true })
          : null;
        const mode = d.active_cycle_mode?.replace(/_/g, " ") ?? "cycle";
        const by = d.active_cycle_initiated_by === "device" ? "from device" : "from app";
        addToast(
          ago
            ? `Wash already running (${mode}, started ${by} ${ago})`
            : `Wash already running (${mode}, started ${by})`,
          "info",
        );
        fetchHistory();
      } else {
        const msg = resp?.data?.detail;
        addToast(msg || "Failed to start wash cycle", "error");
      }
    } finally {
      setWashLoading(false);
    }
  }

  async function handleUvStart() {
    if (!selectedDevice) return;
    setUvLoading(true);
    try {
      await api.post(`/devices/${selectedDevice}/command`, { command: "uv_start" });
      addToast("UV sterilization started", "info");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      addToast(msg || "Failed to start UV sterilization", "error");
    } finally {
      setUvLoading(false);
    }
  }

  async function handleDispense() {
    if (!selectedDevice) return;
    const temp = Number(dispense.temperature_c);
    const vol = Number(dispense.volume_ml);
    if (isNaN(temp) || isNaN(vol)) {
      addToast("Enter valid temperature and volume", "error");
      return;
    }
    // Scoops is optional — only send it if the user entered a value.
    const scoops = dispense.scoop_number.trim() === "" ? null : Number(dispense.scoop_number);
    if (scoops !== null && (isNaN(scoops) || scoops < 0)) {
      addToast("Enter a valid scoop count", "error");
      return;
    }
    setDispenseLoading(true);
    try {
      const { data } = await api.post("/dispensing/", {
        device_id: selectedDevice,
        temperature_c: temp,
        volume_ml: vol,
        scoop_number: scoops,
      });
      useWsEventStore.getState().setDispenseProgress(selectedDevice, {
        log_id: data.id,
        progress: 0,
        status: "pending",
      });
      addToast(`Dispensing ${vol}ml at ${temp}°C…`, "info");
      fetchHistory();
    } catch (err: unknown) {
      const resp = (err as { response?: { status?: number; data?: any } })?.response;
      if (resp?.status === 409 && resp.data?.active_log_id) {
        const d = resp.data;
        useWsEventStore.getState().setDispenseProgress(selectedDevice, {
          log_id: d.active_log_id,
          progress: 0,
          status: d.active_log_status ?? "pending",
        });
        const ago = d.active_log_created_at
          ? formatDistanceToNow(new Date(d.active_log_created_at), { addSuffix: true })
          : null;
        addToast(
          ago
            ? `Dispense already running (${d.active_log_volume_ml ?? "?"}ml @ ${d.active_log_temperature_c ?? "?"}°C, started ${ago})`
            : `Dispense already running (${d.active_log_volume_ml ?? "?"}ml @ ${d.active_log_temperature_c ?? "?"}°C)`,
          "info",
        );
        fetchHistory();
      } else {
        const msg = resp?.data?.detail;
        addToast(msg || "Failed to dispense", "error");
      }
    } finally {
      setDispenseLoading(false);
    }
  }

  async function handleStop(type: "wash" | "dispense") {
    if (!selectedDevice) return;
    setStopLoading(type);
    // Prefer the cancel endpoint: it resets the DB row (so the device is
    // unblocked even when it's offline) AND fires the stop command. Fall back
    // to a bare command only if we don't have an active id to cancel.
    const activeId = type === "wash" ? washProg?.cycle_id : dispenseProg?.log_id;
    try {
      if (activeId) {
        const path = type === "wash" ? "washing" : "dispensing";
        await api.patch(`/${path}/${activeId}/cancel`);
        // Optimistically reflect the reset; the WS broadcast will confirm it.
        if (type === "wash") {
          useWsEventStore.getState().setWashProgress(selectedDevice, {
            cycle_id: activeId,
            progress: washProg?.progress ?? 0,
            status: "failed",
          });
        } else {
          useWsEventStore.getState().setDispenseProgress(selectedDevice, {
            log_id: activeId,
            progress: dispenseProg?.progress ?? 0,
            status: "failed",
          });
        }
        addToast(`${type === "wash" ? "Wash" : "Dispense"} cancelled`, "info");
        fetchHistory();
      } else {
        await api.post(`/devices/${selectedDevice}/command`, {
          command: type === "wash" ? "stop_wash" : "stop_dispense",
        });
        addToast(`Stop command sent to device`, "info");
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      addToast(msg || "Failed to stop", "error");
    } finally {
      setStopLoading(null);
    }
  }

  const washIsActive = !!washProg && washProg.status !== "completed" && washProg.status !== "failed";
  const dispenseIsActive = !!dispenseProg && dispenseProg.status !== "completed" && dispenseProg.status !== "failed";

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Device Controls</h1>
        <p className="text-gray-500 text-sm mt-1">Send commands and monitor your device in real time</p>
      </div>

      {/* Single-device status bar */}
      {device ? (
        <div className="mb-6 flex items-center gap-3 px-4 py-3 bg-white border border-gray-200 rounded-xl">
          <span
            className={`w-2 h-2 rounded-full ${
              device.status === "online" ? "bg-green-500" : "bg-gray-400"
            }`}
          />
          <span className="text-sm font-medium text-gray-800">{device.device_name}</span>
          <span className="text-xs font-mono text-gray-400 ml-2">{device.mac_address}</span>
          <span className="ml-auto text-xs text-gray-500 capitalize">{device.status}</span>
        </div>
      ) : (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 mb-6 text-sm text-yellow-700">
          No device paired yet. Go to <span className="font-medium">Device</span> to pair one.
        </div>
      )}

      {/* Live progress — Wash */}
      {washProg && (
        <div className={`rounded-xl p-4 mb-4 border ${
          washProg.status === "failed"
            ? "bg-red-50 border-red-200"
            : washProg.status === "completed"
            ? "bg-green-50 border-green-200"
            : "bg-blue-50 border-blue-200"
        }`}>
          <div className="flex items-center justify-between mb-2">
            <p className={`text-sm font-medium ${
              washProg.status === "failed" ? "text-red-800"
              : washProg.status === "completed" ? "text-green-800"
              : "text-blue-800"
            }`}>
              {washProg.status === "completed"
                ? "Wash cycle complete"
                : washProg.status === "failed"
                ? "Wash cycle failed"
                : "Wash cycle in progress…"}
            </p>
            <div className="flex items-center gap-3">
              <span className={`text-sm font-bold ${
                washProg.status === "failed" ? "text-red-700"
                : washProg.status === "completed" ? "text-green-700"
                : "text-blue-700"
              }`}>
                {washProg.progress}%
              </span>
              {washIsActive && (
                <button
                  onClick={() => handleStop("wash")}
                  disabled={stopLoading === "wash"}
                  title="Stop wash cycle"
                  className="flex items-center gap-1 text-xs text-red-600 hover:text-red-800 border border-red-200 hover:border-red-400 rounded-lg px-2 py-1 disabled:opacity-50 transition-colors"
                >
                  <Square className="w-3 h-3 fill-current" />
                  {stopLoading === "wash" ? "Stopping…" : "Stop"}
                </button>
              )}
            </div>
          </div>
          <div className="w-full bg-blue-100 rounded-full h-2">
            <div
              className={`h-2 rounded-full transition-all duration-500 ${
                washProg.status === "failed" ? "bg-red-500"
                : washProg.status === "completed" ? "bg-green-500"
                : "bg-blue-500"
              }`}
              style={{ width: `${washProg.progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Live progress — Dispense */}
      {dispenseProg && (
        <div className={`rounded-xl p-4 mb-4 border ${
          dispenseProg.status === "failed"
            ? "bg-red-50 border-red-200"
            : dispenseProg.status === "completed"
            ? "bg-green-50 border-green-200"
            : "bg-emerald-50 border-emerald-200"
        }`}>
          <div className="flex items-center justify-between mb-2">
            <p className={`text-sm font-medium ${
              dispenseProg.status === "failed" ? "text-red-800"
              : dispenseProg.status === "completed" ? "text-green-800"
              : "text-emerald-800"
            }`}>
              {dispenseProg.status === "completed"
                ? "Milk dispensed"
                : dispenseProg.status === "failed"
                ? "Dispense failed"
                : "Dispensing milk…"}
            </p>
            <div className="flex items-center gap-3">
              <span className={`text-sm font-bold ${
                dispenseProg.status === "failed" ? "text-red-700"
                : dispenseProg.status === "completed" ? "text-green-700"
                : "text-emerald-700"
              }`}>
                {dispenseProg.progress}%
              </span>
              {dispenseIsActive && (
                <button
                  onClick={() => handleStop("dispense")}
                  disabled={stopLoading === "dispense"}
                  title="Stop dispensing"
                  className="flex items-center gap-1 text-xs text-red-600 hover:text-red-800 border border-red-200 hover:border-red-400 rounded-lg px-2 py-1 disabled:opacity-50 transition-colors"
                >
                  <Square className="w-3 h-3 fill-current" />
                  {stopLoading === "dispense" ? "Stopping…" : "Stop"}
                </button>
              )}
            </div>
          </div>
          <div className="w-full bg-emerald-100 rounded-full h-2">
            <div
              className={`h-2 rounded-full transition-all duration-500 ${
                dispenseProg.status === "failed" ? "bg-red-500"
                : dispenseProg.status === "completed" ? "bg-green-500"
                : "bg-emerald-500"
              }`}
              style={{ width: `${dispenseProg.progress}%` }}
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
          <p className="text-sm text-gray-500 mb-4">Select a mode to start.</p>
          <div className="grid grid-cols-2 gap-3 mb-4">
            {WASH_MODES.map((mode) => (
              <button
                key={mode.id}
                onClick={() => setSelectedMode(mode.id)}
                disabled={washIsActive}
                className={`border-2 rounded-xl p-3 text-left transition-all disabled:opacity-40 ${
                  selectedMode === mode.id ? mode.activeColor : mode.color
                }`}
              >
                <mode.icon className="w-5 h-5 mb-1 text-gray-600" />
                <p className="text-sm font-semibold text-gray-800">{mode.label}</p>
                <p className="text-xs text-gray-500">{mode.description}</p>
              </button>
            ))}
          </div>
          <button
            onClick={handleStartWash}
            disabled={!selectedMode || !selectedDevice || washLoading || washIsActive}
            className="w-full bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white py-2.5 rounded-lg text-sm font-medium transition-colors"
          >
            {washLoading ? "Starting…" : washIsActive ? "Cycle running…" : "Start Wash Cycle"}
          </button>
          <button
            onClick={handleUvStart}
            disabled={!selectedDevice || uvLoading}
            title="Send a UV sterilization start command to the device"
            className="w-full mt-2 flex items-center justify-center gap-2 border border-purple-300 text-purple-700 hover:bg-purple-50 disabled:opacity-50 py-2.5 rounded-lg text-sm font-medium transition-colors"
          >
            <Sparkles className="w-4 h-4" />
            {uvLoading ? "Starting UV…" : "Start UV Sterilization"}
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
                disabled={dispenseIsActive}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none disabled:opacity-50"
              />
              <p className="text-xs text-gray-400 mt-1">Recommended: 36–38°C (body temperature)</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Volume (ml)</label>
              <input
                type="number" min="10" max="300" step="5"
                value={dispense.volume_ml}
                onChange={(e) => setDispense({ ...dispense, volume_ml: e.target.value })}
                disabled={dispenseIsActive}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none disabled:opacity-50"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Scoops <span className="text-gray-400 text-xs">(optional)</span>
              </label>
              <input
                type="number" min="0" max="20" step="1"
                value={dispense.scoop_number}
                onChange={(e) => setDispense({ ...dispense, scoop_number: e.target.value })}
                disabled={dispenseIsActive}
                placeholder="e.g. 2"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none disabled:opacity-50"
              />
              <p className="text-xs text-gray-400 mt-1">Number of formula scoops</p>
            </div>
          </div>
          <button
            onClick={handleDispense}
            disabled={!selectedDevice || dispenseLoading || dispenseIsActive}
            className="w-full bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white py-2.5 rounded-lg text-sm font-medium transition-colors"
          >
            {dispenseLoading ? "Sending…" : dispenseIsActive ? "Dispensing…" : "Dispense Milk"}
          </button>
        </div>
      </div>

      {/* Logs — wash cycles & dispenses side by side */}
      <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Wash History */}
      <div className="bg-white rounded-xl border border-gray-200">
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
                    <td className="px-5 py-3 font-medium text-gray-800 capitalize">{c.mode.replace(/_/g, " ")}</td>
                    <td className="px-5 py-3"><StatusBadge status={c.status} /></td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-16 bg-gray-100 rounded-full h-1.5">
                          <div className="bg-primary-500 h-1.5 rounded-full" style={{ width: `${c.progress_pct ?? 0}%` }} />
                        </div>
                        <span className="text-xs text-gray-500">{c.progress_pct ?? 0}%</span>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-gray-500">{format(new Date(c.started_at), "dd MMM, HH:mm")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Dispense History */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">Recent Dispense Logs</h2>
        </div>
        {dispenseHistory.length === 0 ? (
          <p className="text-center text-sm text-gray-400 py-8">No dispense logs yet</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-500 uppercase border-b border-gray-100">
                  <th className="px-5 py-3 text-left">Volume</th>
                  <th className="px-5 py-3 text-left">Temp</th>
                  <th className="px-5 py-3 text-left">Scoops</th>
                  <th className="px-5 py-3 text-left">Status</th>
                  <th className="px-5 py-3 text-left">Time</th>
                </tr>
              </thead>
              <tbody>
                {dispenseHistory.slice(0, 10).map((d) => (
                  <tr key={d.id} className="border-b border-gray-50">
                    <td className="px-5 py-3 font-medium text-gray-800">{d.volume_ml} ml</td>
                    <td className="px-5 py-3 text-gray-600">{d.temperature_c}°C</td>
                    <td className="px-5 py-3 text-gray-600">{d.scoop_number ?? "—"}</td>
                    <td className="px-5 py-3"><StatusBadge status={d.status} /></td>
                    <td className="px-5 py-3 text-gray-500">{format(new Date(d.created_at), "dd MMM, HH:mm")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pending:    "bg-yellow-100 text-yellow-700",
    running:    "bg-blue-100 text-blue-700",
    dispensing: "bg-blue-100 text-blue-700",
    completed:  "bg-green-100 text-green-700",
    failed:     "bg-red-100 text-red-700",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${map[status] || "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  );
}
