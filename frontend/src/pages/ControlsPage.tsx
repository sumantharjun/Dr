import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { Settings2, Wind, Zap, Thermometer, Square, Sparkles, Check } from "lucide-react";
import { clsx } from "clsx";
import ConfirmDialog from "../components/ConfirmDialog";
import api from "../services/api";
import { Device, WashingCycle, DispenseLog, UvCycle } from "../types";
import { format, formatDistanceToNow } from "date-fns";
import { useToastStore } from "../store/toastStore";
import { useWsEventStore } from "../store/wsEventStore";

// Selected modes are filled rather than tinted. A `-50` tint reads as near-white
// in both themes, and dark mode inverts the grey label on top of it to near-white
// too, so the text vanished. Filled `-700` + white text keeps AA contrast in both
// themes, and hover only moves the border so it can't mimic the selected state.
const WASH_MODES = [
  { id: "full_cycle",  label: "Full Cycle",  description: "Wash, Dry, Sterilize & Fill", icon: Zap,         idle: "border-primary-200 hover:border-primary-500 hover:bg-gray-50", active: "border-primary-700 bg-primary-700" },
  { id: "steam_dry",   label: "Steam & Dry", description: "Steam clean, then dry",        icon: Wind,        idle: "border-green-200 hover:border-green-500 hover:bg-gray-50",     active: "border-green-700 bg-green-700"     },
  { id: "dry",         label: "Dry",         description: "Dry only",                     icon: Thermometer, idle: "border-blue-200 hover:border-blue-500 hover:bg-gray-50",       active: "border-blue-700 bg-blue-700"       },
];

export default function ControlsPage() {
  const [device, setDevice] = useState<Device | null>(null);
  const selectedDevice = device?.id ?? null;
  const [selectedMode, setSelectedMode] = useState<string>("");
  // Which physical action is awaiting confirmation, if any. Stops are confirmed
  // as well as starts: cancelling resets the cycle rather than pausing it, so a
  // mis-tapped Stop costs the whole run.
  const [confirming, setConfirming] = useState<
    null | "wash" | "dispense" | "uv" | "stop_wash" | "stop_dispense" | "stop_uv"
  >(null);
  const [washHistory, setWashHistory] = useState<WashingCycle[]>([]);
  const [dispenseHistory, setDispenseHistory] = useState<DispenseLog[]>([]);
  const [uvHistory, setUvHistory] = useState<UvCycle[]>([]);
  const [dispense, setDispense] = useState({ temperature_c: "37", volume_ml: "120", scoop_number: "" });
  const [washLoading, setWashLoading] = useState(false);
  const [dispenseLoading, setDispenseLoading] = useState(false);
  const [stopLoading, setStopLoading] = useState<"wash" | "dispense" | null>(null);
  const [uvLoading, setUvLoading] = useState(false);
  const [uvStopLoading, setUvStopLoading] = useState(false);

  const { addToast } = useToastStore();

  // Real-time progress from global WebSocket (via wsEventStore)
  const washProg = useWsEventStore((s) => (selectedDevice ? s.washProgress[selectedDevice] : null));
  const dispenseProg = useWsEventStore((s) => (selectedDevice ? s.dispenseProgress[selectedDevice] : null));
  const uvProg = useWsEventStore((s) => (selectedDevice ? s.uvProgress[selectedDevice] : null));

  const fetchHistory = useCallback(async () => {
    const [wash, disp, uvRes] = await Promise.all([
      api.get("/washing/history"),
      api.get("/dispensing/history"),
      api.get("/uv/history"),
    ]);
    setWashHistory(wash.data);
    setDispenseHistory(disp.data);
    setUvHistory(uvRes.data);

    // Hydrate an in-flight UV cycle so the live status shows after a reload.
    const sUv = useWsEventStore.getState();
    const activeUv = (uvRes.data as UvCycle[]).find((c) => c.status === "started");
    if (activeUv && !sUv.uvProgress[activeUv.device_id]) {
      sUv.setUvProgress(activeUv.device_id, { uv_cycle_id: activeUv.id, status: "started" });
    }

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
      const { data } = await api.post("/uv/start", { device_id: selectedDevice });
      useWsEventStore.getState().setUvProgress(selectedDevice, { uv_cycle_id: data.id, status: "started" });
      addToast("UV sterilization started", "info");
      fetchHistory();
    } catch (err: unknown) {
      const resp = (err as { response?: { status?: number; data?: any } })?.response;
      if (resp?.status === 409 && resp.data?.active_uv_cycle_id) {
        useWsEventStore.getState().setUvProgress(selectedDevice, {
          uv_cycle_id: resp.data.active_uv_cycle_id,
          status: resp.data.active_uv_status ?? "started",
        });
        addToast("UV sterilization is already running", "info");
      } else {
        addToast(resp?.data?.detail || "Failed to start UV sterilization", "error");
      }
    } finally {
      setUvLoading(false);
    }
  }

  async function handleUvCancel() {
    if (!selectedDevice || !uvProg?.uv_cycle_id) return;
    setUvStopLoading(true);
    try {
      await api.patch(`/uv/${uvProg.uv_cycle_id}/cancel`);
      useWsEventStore.getState().setUvProgress(selectedDevice, { uv_cycle_id: uvProg.uv_cycle_id, status: "failed" });
      addToast("UV sterilization stopped", "info");
      fetchHistory();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      addToast(msg || "Failed to stop UV", "error");
    } finally {
      setUvStopLoading(false);
    }
  }

  /**
   * Parse and validate the dispense form, toasting on the first problem.
   * Split out from handleDispense so validation runs *before* the confirmation
   * prompt — asking "are you sure?" and only then rejecting the input is a poor
   * sequence to put the user through.
   */
  function parseDispense() {
    const temp = Number(dispense.temperature_c);
    const vol = Number(dispense.volume_ml);
    if (isNaN(temp) || isNaN(vol)) {
      addToast("Enter valid temperature and volume", "error");
      return null;
    }
    // Scoops is optional — only send it if the user entered a value.
    const scoops = dispense.scoop_number.trim() === "" ? null : Number(dispense.scoop_number);
    if (scoops !== null && (isNaN(scoops) || scoops < 0)) {
      addToast("Enter a valid scoop count", "error");
      return null;
    }
    return { temp, vol, scoops };
  }

  async function handleDispense() {
    if (!selectedDevice) return;
    const parsed = parseDispense();
    if (!parsed) return;
    const { temp, vol, scoops } = parsed;
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

  function requestDispense() {
    if (!selectedDevice) return;
    if (!parseDispense()) return; // reject bad input before prompting
    setConfirming("dispense");
  }

  function runConfirmed() {
    const action = confirming;
    setConfirming(null);
    if (action === "wash") handleStartWash();
    else if (action === "dispense") handleDispense();
    else if (action === "uv") handleUvStart();
    else if (action === "stop_wash") handleStop("wash");
    else if (action === "stop_dispense") handleStop("dispense");
    else if (action === "stop_uv") handleUvCancel();
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

  // Confirmation copy states exactly what the hardware will do, so the prompt
  // carries information rather than just adding a click.
  const modeMeta = WASH_MODES.find((m) => m.id === selectedMode);
  const CONFIRMATIONS = {
    wash: {
      icon: Settings2,
      tone: "primary" as const,
      title: `Start the ${modeMeta?.label ?? "wash"} cycle?`,
      message: `${modeMeta?.description ?? "The selected cycle"} will run on the device. Check that bottles are loaded and the lid is closed.`,
      confirmLabel: "Start Wash",
    },
    dispense: {
      icon: Thermometer,
      tone: "primary" as const,
      title: `Dispense ${dispense.volume_ml || "—"} ml?`,
      message: `Milk will be dispensed at ${dispense.temperature_c || "—"}°C. Make sure a bottle is in position.`,
      confirmLabel: "Dispense",
    },
    uv: {
      icon: Sparkles,
      tone: "warning" as const,
      title: "Start UV sterilization?",
      message: "The UV lamp will switch on. Keep the lid closed and hands clear while the cycle runs.",
      confirmLabel: "Start UV",
    },
    // Stop copy leads with the irreversibility, because that's the part that
    // isn't obvious: `handleStop` hits the cancel endpoint, which resets the
    // row — the cycle ends rather than pausing, and there is no resume.
    stop_wash: {
      icon: Square,
      tone: "danger" as const,
      title: "Stop the wash cycle?",
      message: `The cycle ends now${
        washProg ? ` at ${washProg.progress}%` : ""
      } and cannot be resumed — starting again runs it from the beginning. Bottles may still be soapy or wet.`,
      confirmLabel: "Stop Wash",
    },
    stop_dispense: {
      icon: Square,
      tone: "danger" as const,
      title: "Stop dispensing?",
      message: `Dispensing stops immediately${
        dispenseProg ? ` at ${dispenseProg.progress}%` : ""
      } and cannot be resumed. The bottle may be left part-filled.`,
      confirmLabel: "Stop Dispense",
    },
    stop_uv: {
      icon: Square,
      tone: "danger" as const,
      title: "Stop UV sterilization?",
      message:
        "The UV lamp switches off and the cycle ends. Contents will not be fully sterilized and the cycle must be restarted from scratch.",
      confirmLabel: "Stop UV",
    },
  };
  const activeConfirm = confirming ? CONFIRMATIONS[confirming] : null;

  return (
    <div className="p-4 sm:p-6 max-w-4xl mx-auto">
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
          No device paired yet.{" "}
          <Link to="/devices" className="font-medium underline hover:text-yellow-900">
            Pair a device
          </Link>{" "}
          to get started.
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
                  onClick={() => setConfirming("stop_wash")}
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
                  onClick={() => setConfirming("stop_dispense")}
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

      {/* Live status — UV (discrete states, no progress bar) */}
      {uvProg && (
        <div className={`rounded-xl p-4 mb-4 border flex items-center justify-between ${
          uvProg.status === "failed" ? "bg-red-50 border-red-200"
          : uvProg.status === "completed" ? "bg-green-50 border-green-200"
          : "bg-purple-50 border-purple-200"
        }`}>
          <p className={`text-sm font-medium ${
            uvProg.status === "failed" ? "text-red-800"
            : uvProg.status === "completed" ? "text-green-800"
            : "text-purple-800"
          }`}>
            {uvProg.status === "completed" ? "UV sterilization complete"
              : uvProg.status === "failed" ? "UV sterilization failed"
              : "UV sterilizing…"}
          </p>
          {uvProg.status === "started" && (
            <button
              onClick={() => setConfirming("stop_uv")}
              disabled={uvStopLoading}
              title="Stop UV sterilization"
              className="flex items-center gap-1 text-xs text-red-600 hover:text-red-800 border border-red-200 hover:border-red-400 rounded-lg px-2 py-1 disabled:opacity-50 transition-colors"
            >
              <Square className="w-3 h-3 fill-current" />
              {uvStopLoading ? "Stopping…" : "Stop"}
            </button>
          )}
        </div>
      )}

      {/* The tour covers wash, UV and dispensing in one step, so it spotlights
          the whole grid — highlighting a single card while the copy described
          all three read as pointing at the wrong thing. */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" data-tour="controls-actions">
        {/* Washing */}
        <div className="bg-white rounded-xl border border-gray-200 p-5" data-tour="controls-wash">
          <div className="flex items-center gap-2 mb-4">
            <Settings2 className="w-5 h-5 text-primary-600" />
            <h2 className="font-semibold text-gray-900">Washing Cycle</h2>
          </div>
          <p className="text-sm text-gray-500 mb-4">Select a mode to start.</p>
          <div className="grid grid-cols-2 gap-3 mb-4">
            {WASH_MODES.map((mode) => {
              const active = selectedMode === mode.id;
              return (
                <button
                  key={mode.id}
                  onClick={() => setSelectedMode(mode.id)}
                  disabled={washIsActive}
                  aria-pressed={active}
                  className={clsx(
                    "relative border-2 rounded-xl p-3 text-left transition-all disabled:opacity-40",
                    active ? mode.active : mode.idle,
                  )}
                >
                  {/* Non-colour cue as well as the fill — colour alone can't carry state (WCAG 1.4.1). */}
                  {active && <Check className="w-4 h-4 text-white absolute top-2 right-2" />}
                  <mode.icon className={clsx("w-5 h-5 mb-1", active ? "text-white" : "text-gray-600")} />
                  <p className={clsx("text-sm font-semibold", active ? "text-white" : "text-gray-800")}>
                    {mode.label}
                  </p>
                  <p className={clsx("text-xs", active ? "text-white/90" : "text-gray-500")}>
                    {mode.description}
                  </p>
                </button>
              );
            })}
          </div>
          <button
            onClick={() => setConfirming("wash")}
            disabled={!selectedMode || !selectedDevice || washLoading || washIsActive}
            className="w-full bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white py-2.5 rounded-lg text-sm font-medium transition-colors"
          >
            {washLoading ? "Starting…" : washIsActive ? "Cycle running…" : "Start Wash Cycle"}
          </button>
          <button
            onClick={() => setConfirming("uv")}
            disabled={!selectedDevice || uvLoading || uvProg?.status === "started"}
            title="Send a UV sterilization start command to the device"
            data-tour="controls-uv"
            // Same theme palette as every other action button. Outlined rather
            // than filled so "Start Wash Cycle" above stays the card's primary
            // action — the difference now reads as hierarchy, not as an
            // unexplained second brand colour. Dark variants because
            // primary-700 on the dark surface falls under 4.5:1.
            className="w-full mt-2 flex items-center justify-center gap-2 border border-primary-300 dark:border-primary-500/50 text-primary-700 dark:text-primary-300 hover:bg-primary-50 dark:hover:bg-primary-500/10 disabled:opacity-50 py-2.5 rounded-lg text-sm font-medium transition-colors"
          >
            {/* The one remaining UV cue: purple stays on the icon only, so UV
                is still identifiable without owning the whole button. */}
            <Sparkles className="w-4 h-4 text-purple-600 dark:text-purple-400" />
            {uvLoading ? "Starting UV…" : uvProg?.status === "started" ? "UV running…" : "Start UV Sterilization"}
          </button>
        </div>

        {/* Milk Dispense */}
        <div className="bg-white rounded-xl border border-gray-200 p-5" data-tour="controls-dispense">
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
            onClick={requestDispense}
            disabled={!selectedDevice || dispenseLoading || dispenseIsActive}
            className="w-full bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white py-2.5 rounded-lg text-sm font-medium transition-colors"
          >
            {dispenseLoading ? "Sending…" : dispenseIsActive ? "Dispensing…" : "Dispense Milk"}
          </button>
        </div>
      </div>

      {activeConfirm && (
        <ConfirmDialog
          open
          {...activeConfirm}
          onConfirm={runConfirmed}
          onCancel={() => setConfirming(null)}
        />
      )}

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

      {/* UV History */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">Recent UV Cycles</h2>
        </div>
        {uvHistory.length === 0 ? (
          <p className="text-center text-sm text-gray-400 py-8">No UV cycles yet</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-500 uppercase border-b border-gray-100">
                  <th className="px-5 py-3 text-left">Started by</th>
                  <th className="px-5 py-3 text-left">Status</th>
                  <th className="px-5 py-3 text-left">Time</th>
                </tr>
              </thead>
              <tbody>
                {uvHistory.slice(0, 10).map((c) => (
                  <tr key={c.id} className="border-b border-gray-50">
                    <td className="px-5 py-3 text-gray-600 capitalize">{c.initiated_by}</td>
                    <td className="px-5 py-3"><StatusBadge status={c.ended_reason ?? c.status} /></td>
                    <td className="px-5 py-3 text-gray-500">{format(new Date(c.started_at), "dd MMM, HH:mm")}</td>
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

/**
 * Presentation for every `status` / `ended_reason` value the wash, dispense and
 * UV models can emit. Labels are written out rather than derived, because the
 * raw enums (`timed_out`, `superseded`) mean nothing to a parent reading a log.
 */
const STATUS_STYLES: Record<string, { label: string; className: string }> = {
  pending:    { label: "Pending",     className: "bg-yellow-100 text-yellow-700" },
  running:    { label: "Running",     className: "bg-blue-100 text-blue-700"     },
  dispensing: { label: "Dispensing",  className: "bg-blue-100 text-blue-700"     },
  started:    { label: "In Progress", className: "bg-blue-100 text-blue-700"     },
  completed:  { label: "Completed",   className: "bg-green-100 text-green-700"   },
  failed:     { label: "Failed",      className: "bg-red-100 text-red-700"       },
  cancelled:  { label: "Cancelled",   className: "bg-gray-200 text-gray-700"     },
  timed_out:  { label: "Incomplete",  className: "bg-orange-100 text-orange-700" },
  superseded: { label: "Replaced",    className: "bg-gray-200 text-gray-700"     },
};

/** Last-resort formatting so a new backend enum can't leak as `snake_case`. */
function prettifyStatus(status: string) {
  return status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status];
  return (
    <span
      title={status}
      className={`text-xs px-2 py-0.5 rounded-full font-medium ${style?.className ?? "bg-gray-100 text-gray-600"}`}
    >
      {style?.label ?? prettifyStatus(status)}
    </span>
  );
}
