/** App palettes, defined as [data-theme="…"] blocks in index.css. */
export type ThemeColor = "green" | "blue" | "pink" | "lilac" | "peach" | "slate";

export const THEME_COLORS: { value: ThemeColor; label: string; swatch: string }[] = [
  // `swatch` is a literal hex of each palette's 500 shade — the picker has to
  // render all six at once, so it can't use the `primary` CSS variables (those
  // only ever hold the *active* theme).
  { value: "green", label: "Green", swatch: "#2EA069" },
  { value: "blue",  label: "Blue",  swatch: "#2FA8CB" },
  { value: "pink",  label: "Pink",  swatch: "#DE4E8C" },
  { value: "lilac", label: "Lilac", swatch: "#8363C4" },
  { value: "peach", label: "Peach", swatch: "#D6692D" },
  { value: "slate", label: "Slate", swatch: "#64748B" },
];

export interface User {
  id: number;
  email: string;
  full_name: string;
  /** The parent's chosen app colour — an account preference, not per baby. */
  theme_color: ThemeColor;
  /** Null until the guided tour is finished or skipped; drives first-run onboarding. */
  tour_completed_at: string | null;
  created_at: string;
}

export interface Device {
  id: number;
  device_name: string;
  mac_address: string;
  wifi_ssid: string | null;
  status: "online" | "offline" | "pairing" | "error";
  /** Which baby this device's scale reports are attributed to ("Feeding now"). */
  active_baby_id: number | null;
  last_seen: string | null;
  created_at: string;
}

export interface FeedingLog {
  id: number;
  device_id: number | null;
  feed_time: string;
  weight_before_g: number | null;
  weight_after_g: number | null;
  milk_consumed_ml: number | null;
  method: "device" | "manual" | "breast" | "other";
  // Null for logs predating the field and for device-reported feeds, where the
  // scale can't know what the bottle held.
  milk_type: MilkType | null;
  notes: string | null;
  created_at: string;
}

export type MilkType = "breast_milk" | "formula" | "cow_milk" | "mixed" | "other";

export interface FeedingAnalytics {
  date: string;
  total_ml: number;
  feed_count: number;
}

export interface FeedingSchedule {
  last_feed_time: string | null;
  minutes_since_last_feed: number | null;
  next_feed_due: string | null;
}

export interface WashingCycle {
  id: number;
  device_id: number;
  mode: "full_cycle" | "steam_dry" | "dry";
  status: "pending" | "running" | "completed" | "failed";
  progress_pct: number;
  started_at: string;
  completed_at: string | null;
}

export interface UvCycle {
  id: number;
  device_id: number;
  status: "started" | "completed" | "failed";
  initiated_by: "app" | "device";
  ended_reason: string | null;
  started_at: string;
  completed_at: string | null;
}

export interface DispenseLog {
  id: number;
  device_id: number;
  temperature_c: number;
  volume_ml: number;
  scoop_number: number | null;
  status: "pending" | "dispensing" | "completed" | "failed";
  progress_pct: number;
  created_at: string;
  completed_at: string | null;
}

export interface DeviceAlert {
  id: number;
  device_id: number;
  alert_type: string;
  message: string;
  severity: "info" | "warning" | "error" | "critical";
  is_read: boolean;
  created_at: string;
}

export interface Product {
  id: number;
  name: string;
  description: string | null;
  price: number;
  category: string;
  stock: number;
  image_url: string | null;
}

export interface OrderItem {
  id: number;
  product_id: number;
  quantity: number;
  unit_price: number;
  product: Product;
}

export interface Order {
  id: number;
  status: "pending" | "confirmed" | "shipped" | "delivered" | "cancelled";
  total_price: number;
  created_at: string;
  items: OrderItem[];
}

export interface ActivityLog {
  id: number;
  device_id: number;
  event_type: string;
  description: string | null;
  recorded_at: string;
}

export interface Baby {
  id: number;
  /** Always present — required on create, and legacy blanks were backfilled to "Baby". */
  name: string;
  gender: "male" | "female";
  /** ISO date (YYYY-MM-DD). Null for profiles created before this field existed. */
  date_of_birth: string | null;
  /** Age in whole days, derived server-side from date_of_birth. */
  age_days: number | null;
  weight_kg: number;
  created_at: string;
  updated_at: string;
}
