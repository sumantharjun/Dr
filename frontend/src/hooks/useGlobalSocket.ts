import { useEffect, useRef } from "react";
import api from "../services/api";
import { useAlertStore } from "../store/alertStore";
import { useToastStore } from "../store/toastStore";
import { useWsEventStore } from "../store/wsEventStore";

const WS_BASE = import.meta.env.VITE_WS_URL || "ws://localhost:8000";
const MAX_RETRIES = 15;
const BASE_DELAY_MS = 1000;

function routeEvent(deviceId: number, event: Record<string, unknown>) {
  const ws = useWsEventStore.getState();
  const alertStore = useAlertStore.getState();
  const toastStore = useToastStore.getState();

  switch (event.type as string) {
    case "ping":
      return;

    case "wash_progress":
      ws.setWashProgress(deviceId, {
        cycle_id: event.cycle_id as number,
        progress: event.progress_pct as number,
        status: event.status as string,
      });
      if (event.status === "completed") {
        toastStore.addToast("Wash cycle completed!", "success");
      } else if (event.status === "failed") {
        toastStore.addToast("Wash cycle failed. Check device.", "error");
      }
      break;

    case "dispense_progress":
      ws.setDispenseProgress(deviceId, {
        log_id: event.log_id as number,
        progress: event.progress_pct as number,
        status: event.status as string,
      });
      if (event.status === "completed") {
        toastStore.addToast("Milk dispensed successfully!", "success");
      } else if (event.status === "failed") {
        toastStore.addToast("Dispense failed. Check device.", "error");
      }
      break;

    case "weight_report":
      ws.setWeightReading(deviceId, (event.payload as Record<string, number> | undefined)?.weight_g ?? null);
      break;

    case "feeding_logged":
      ws.setLastFeedingEvent(deviceId, Date.now());
      break;

    case "alert": {
      const severity = event.severity as string;
      const message = event.message as string;
      const toastType = severity === "critical" || severity === "error" ? "error" : "warning";
      toastStore.addToast(message, toastType);
      if (Notification.permission === "granted") {
        new Notification("BabyFeeder Alert", { body: message, icon: "/baby-bottle.svg" });
      }
      // Refresh alerts from server so we get real IDs
      api.get("/alerts/").then((r) => alertStore.setAlerts(r.data)).catch(() => {});
      break;
    }

    default:
      break;
  }
}

/**
 * Manages one WebSocket connection per device for the entire app lifetime.
 * Call this once in AppLayout; individual pages read state from wsEventStore.
 */
export function useGlobalSocket(deviceIds: number[]) {
  const wsMap = useRef<Map<number, WebSocket>>(new Map());
  const retryMap = useRef<Map<number, number>>(new Map());
  const timeoutMap = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());
  const isMountedRef = useRef(true);

  // Always-current connect function via ref so onclose callbacks never go stale
  const connectRef = useRef((_deviceId: number) => {});
  connectRef.current = (deviceId: number) => {
    const token = localStorage.getItem("access_token");
    if (!token || !isMountedRef.current) return;

    const url = `${WS_BASE}/devices/ws/${deviceId}?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    wsMap.current.set(deviceId, ws);

    ws.onopen = () => {
      retryMap.current.set(deviceId, 0);
    };

    ws.onmessage = (e) => {
      if (!isMountedRef.current) return;
      try {
        const data = JSON.parse(e.data as string);
        routeEvent(deviceId, data);
      } catch {
        // Ignore malformed frames
      }
    };

    ws.onclose = () => {
      wsMap.current.delete(deviceId);
      if (!isMountedRef.current) return;
      const retries = retryMap.current.get(deviceId) ?? 0;
      if (retries >= MAX_RETRIES) return;
      const delay = Math.min(BASE_DELAY_MS * 2 ** retries, 60_000);
      retryMap.current.set(deviceId, retries + 1);
      const t = setTimeout(() => connectRef.current(deviceId), delay);
      timeoutMap.current.set(deviceId, t);
    };

    ws.onerror = () => ws.close();
  };

  function disconnectDevice(deviceId: number) {
    const t = timeoutMap.current.get(deviceId);
    if (t) clearTimeout(t);
    timeoutMap.current.delete(deviceId);
    retryMap.current.delete(deviceId);
    const ws = wsMap.current.get(deviceId);
    if (ws) {
      ws.onclose = null;
      ws.onerror = null;
      ws.close();
      wsMap.current.delete(deviceId);
    }
  }

  // Mount/unmount lifecycle
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      timeoutMap.current.forEach((t) => clearTimeout(t));
      wsMap.current.forEach((ws) => {
        ws.onclose = null;
        ws.onerror = null;
        ws.close();
      });
      wsMap.current.clear();
      retryMap.current.clear();
      timeoutMap.current.clear();
    };
  }, []);

  // React to changes in device list
  const deviceIdsKey = deviceIds.join(",");
  useEffect(() => {
    if (!isMountedRef.current) return;
    const currentSet = new Set(deviceIds);

    // Connect new devices
    deviceIds.forEach((id) => {
      if (!wsMap.current.has(id)) connectRef.current(id);
    });

    // Disconnect devices that were removed
    wsMap.current.forEach((_, id) => {
      if (!currentSet.has(id)) disconnectDevice(id);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deviceIdsKey]);
}
