"""
Single source of truth for alert_type values used across the system.

There are two categories:
  - Device-emitted alerts (Annexure A safety alerts in the MOU): firmware POSTs
    these via POST /alerts/. The set is closed — POST validates against it.
  - Server-generated alerts: created by background jobs / analyzers in code.
    These are NOT valid as inputs to POST /alerts/.

Keep the TS mirror in `frontend/src/types/alerts.ts` in sync if you edit this.
"""

from typing import Literal


# ─── Device-emitted safety alerts (MOU Annexure A1) ──────────────────────────
DEVICE_ALERT_TYPES = {
    "overheating": {
        "label": "Overheating",
        "description": "Device or milk temperature exceeded safe limit.",
        "default_severity": "critical",
    },
    "malfunction": {
        "label": "Device Malfunction",
        "description": "Hardware or sensor failure detected.",
        "default_severity": "error",
    },
    "washing_error": {
        "label": "Washing Error",
        "description": "Wash cycle could not complete or detected an anomaly.",
        "default_severity": "error",
    },
    "low_detergent": {
        "label": "Low Detergent",
        "description": "Detergent reservoir is running low.",
        "default_severity": "warning",
    },
}

# ─── Server-generated alerts (created by feeding_analyzer, scheduler, etc.) ──
SERVER_ALERT_TYPES = {
    "feeding_reminder": {
        "label": "Feeding Reminder",
        "description": "Baby is due for a feed.",
        "default_severity": "warning",
    },
    "overdue_feed": {
        "label": "Overdue Feed",
        "description": "No feed recorded for an extended period.",
        "default_severity": "warning",
    },
    "low_intake": {
        "label": "Low Intake",
        "description": "Most recent feed was below the expected minimum.",
        "default_severity": "warning",
    },
    "frequent_feeding": {
        "label": "Frequent Feeding",
        "description": "Unusually high feeding frequency detected.",
        "default_severity": "error",
    },
}

ALERT_TYPES = {**DEVICE_ALERT_TYPES, **SERVER_ALERT_TYPES}

VALID_DEVICE_ALERT_TYPES = frozenset(DEVICE_ALERT_TYPES.keys())
VALID_ALERT_TYPES = frozenset(ALERT_TYPES.keys())

DeviceAlertTypeLiteral = Literal[
    "overheating",
    "malfunction",
    "washing_error",
    "low_detergent",
]


def default_severity_for(alert_type: str) -> str:
    entry = ALERT_TYPES.get(alert_type)
    return entry["default_severity"] if entry else "warning"
