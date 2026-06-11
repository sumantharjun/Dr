import { create } from "zustand";

export interface WashProgressData {
  cycle_id: number;
  progress: number;
  status: string;
}

export interface DispenseProgressData {
  log_id: number;
  progress: number;
  status: string;
}

export interface UvProgressData {
  uv_cycle_id: number;
  status: string;
}

interface WsEventState {
  washProgress: Record<number, WashProgressData | null>;
  dispenseProgress: Record<number, DispenseProgressData | null>;
  uvProgress: Record<number, UvProgressData | null>;
  weightReadings: Record<number, number | null>;
  lastFeedingEvent: Record<number, number | null>;

  setWashProgress: (deviceId: number, data: WashProgressData | null) => void;
  setDispenseProgress: (deviceId: number, data: DispenseProgressData | null) => void;
  setUvProgress: (deviceId: number, data: UvProgressData | null) => void;
  setWeightReading: (deviceId: number, weight: number | null) => void;
  setLastFeedingEvent: (deviceId: number, ts: number) => void;
}

export const useWsEventStore = create<WsEventState>((set) => ({
  washProgress: {},
  dispenseProgress: {},
  uvProgress: {},
  weightReadings: {},
  lastFeedingEvent: {},

  setWashProgress: (deviceId, data) =>
    set((s) => ({ washProgress: { ...s.washProgress, [deviceId]: data } })),

  setDispenseProgress: (deviceId, data) =>
    set((s) => ({ dispenseProgress: { ...s.dispenseProgress, [deviceId]: data } })),

  setUvProgress: (deviceId, data) =>
    set((s) => ({ uvProgress: { ...s.uvProgress, [deviceId]: data } })),

  setWeightReading: (deviceId, weight) =>
    set((s) => ({ weightReadings: { ...s.weightReadings, [deviceId]: weight } })),

  setLastFeedingEvent: (deviceId, ts) =>
    set((s) => ({ lastFeedingEvent: { ...s.lastFeedingEvent, [deviceId]: ts } })),
}));
