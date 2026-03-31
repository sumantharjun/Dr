export interface User {
  id: number;
  email: string;
  full_name: string;
  created_at: string;
}

export interface Device {
  id: number;
  device_name: string;
  mac_address: string;
  wifi_ssid: string | null;
  status: "online" | "offline" | "pairing" | "error";
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
  notes: string | null;
  created_at: string;
}

export interface FeedingAnalytics {
  date: string;
  total_ml: number;
  feed_count: number;
}

export interface FeedingSchedule {
  last_feed_time: string | null;
  minutes_since_last_feed: number | null;
  recommended_interval_hours: number;
  next_feed_due: string | null;
}

export interface WashingCycle {
  id: number;
  device_id: number;
  mode: "full_cycle" | "wash" | "deep_clean" | "dispense";
  status: "pending" | "running" | "completed" | "failed";
  progress_pct: number;
  started_at: string;
  completed_at: string | null;
}

export interface DispenseLog {
  id: number;
  device_id: number;
  temperature_c: number;
  volume_ml: number;
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
