// Mirror of backend/app/services/alerts_catalog.py — keep them in sync.

export type Severity = "info" | "warning" | "error" | "critical";

interface AlertTypeMeta {
  label: string;
  description: string;
  defaultSeverity: Severity;
  source: "device" | "server";
}

export const ALERT_TYPES: Record<string, AlertTypeMeta> = {
  // ─── Device-emitted (MOU Annexure A1 safety alerts) ─────────────────────
  overheating: {
    label: "Overheating",
    description: "Device or milk temperature exceeded safe limit.",
    defaultSeverity: "critical",
    source: "device",
  },
  malfunction: {
    label: "Device Malfunction",
    description: "Hardware or sensor failure detected.",
    defaultSeverity: "error",
    source: "device",
  },
  washing_error: {
    label: "Washing Error",
    description: "Wash cycle could not complete or detected an anomaly.",
    defaultSeverity: "error",
    source: "device",
  },
  low_detergent: {
    label: "Low Detergent",
    description: "Detergent reservoir is running low.",
    defaultSeverity: "warning",
    source: "device",
  },

  // ─── Server-generated ───────────────────────────────────────────────────
  feeding_reminder: {
    label: "Feeding Reminder",
    description: "Baby is due for a feed.",
    defaultSeverity: "warning",
    source: "server",
  },
  overdue_feed: {
    label: "Overdue Feed",
    description: "No feed recorded for an extended period.",
    defaultSeverity: "warning",
    source: "server",
  },
  low_intake: {
    label: "Low Intake",
    description: "Most recent feed was below the expected minimum.",
    defaultSeverity: "warning",
    source: "server",
  },
  frequent_feeding: {
    label: "Frequent Feeding",
    description: "Unusually high feeding frequency detected.",
    defaultSeverity: "error",
    source: "server",
  },
};

export function alertMeta(type: string): AlertTypeMeta {
  return (
    ALERT_TYPES[type] ?? {
      label: type.replace(/_/g, " "),
      description: "",
      defaultSeverity: "warning",
      source: "device",
    }
  );
}
