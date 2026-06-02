import { create } from "zustand";

export type Theme = "light" | "dark";

const OVERRIDE_KEY = "theme_override";

// ── Time-based schedule (IST) ───────────────────────────────────────────────
// Dark from 19:00 (7 PM) to 07:00 (7 AM) IST; light otherwise. IST = UTC+5:30,
// computed from the epoch so it's correct regardless of the device timezone.
function istHour(): number {
  const now = new Date();
  const utcMs = now.getTime() + now.getTimezoneOffset() * 60000;
  return new Date(utcMs + 5.5 * 3600000).getHours();
}

function scheduledTheme(): Theme {
  const h = istHour();
  return h >= 19 || h < 7 ? "dark" : "light";
}

// A manual override stores BOTH the chosen theme and the scheduled theme at the
// time it was set. The override stays active only while the schedule hasn't
// flipped since — so at the next 7 AM/7 PM boundary the app auto-switches again.
function readOverride(): { theme: Theme; base: Theme } | null {
  try {
    const o = JSON.parse(localStorage.getItem(OVERRIDE_KEY) || "null");
    if (o && (o.theme === "light" || o.theme === "dark") && (o.base === "light" || o.base === "dark")) {
      return o;
    }
  } catch {
    /* ignore */
  }
  return null;
}

export function effectiveTheme(): Theme {
  const sched = scheduledTheme();
  const ov = readOverride();
  return ov && ov.base === sched ? ov.theme : sched;
}

function applyTheme(theme: Theme) {
  if (typeof document !== "undefined") {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }
}

interface ThemeState {
  theme: Theme;
  /** Manual flip of the switch (sets/clears an override vs. the schedule). */
  toggle: () => void;
  /** Re-evaluate against the schedule — called on a timer to auto-switch. */
  refresh: () => void;
}

export const useThemeStore = create<ThemeState>((set, get) => {
  // Auto-switch at the 7 AM / 7 PM boundaries (and expire stale overrides).
  if (typeof window !== "undefined") {
    setInterval(() => get().refresh(), 60_000);
  }

  applyTheme(effectiveTheme());

  return {
    theme: effectiveTheme(),
    toggle: () => {
      const sched = scheduledTheme();
      const next: Theme = get().theme === "dark" ? "light" : "dark";
      if (next === sched) {
        // Back in line with the schedule → drop the override (resume auto).
        localStorage.removeItem(OVERRIDE_KEY);
      } else {
        localStorage.setItem(OVERRIDE_KEY, JSON.stringify({ theme: next, base: sched }));
      }
      applyTheme(next);
      set({ theme: next });
    },
    refresh: () => {
      const ov = readOverride();
      if (ov && ov.base !== scheduledTheme()) localStorage.removeItem(OVERRIDE_KEY);
      const eff = effectiveTheme();
      if (eff !== get().theme) {
        applyTheme(eff);
        set({ theme: eff });
      }
    },
  };
});
