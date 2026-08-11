import { ThemeColor } from "../types";

/**
 * Applying the account's chosen palette.
 *
 * The colour lives on the user (users.theme_color) and is mirrored into
 * localStorage so `main.tsx` can set it before first paint — without that, the
 * app renders one frame in the default palette and visibly flips.
 */
const KEY = "app_theme_color";
export const DEFAULT_THEME: ThemeColor = "green";

const VALID: ThemeColor[] = ["green", "blue", "pink", "lilac", "peach", "slate"];

export function isThemeColor(v: unknown): v is ThemeColor {
  return typeof v === "string" && (VALID as string[]).includes(v);
}

export function readStoredTheme(): ThemeColor {
  try {
    const v = localStorage.getItem(KEY);
    return isThemeColor(v) ? v : DEFAULT_THEME;
  } catch {
    return DEFAULT_THEME;
  }
}

/** Set the palette on <html> and remember it for the next cold start. */
export function applyTheme(color: ThemeColor): void {
  if (typeof document !== "undefined") {
    document.documentElement.setAttribute("data-theme", color);
  }
  try {
    localStorage.setItem(KEY, color);
  } catch {
    /* storage disabled — the theme still applies for this session */
  }
}

export function clearStoredTheme(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
