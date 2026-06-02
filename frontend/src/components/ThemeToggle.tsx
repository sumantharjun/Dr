import { Sun, Moon } from "lucide-react";
import { clsx } from "clsx";
import { useThemeStore } from "../store/themeStore";

export default function ThemeToggle() {
  const { theme, toggle } = useThemeStore();
  const isDark = theme === "dark";

  return (
    <button
      type="button"
      role="switch"
      aria-checked={isDark}
      onClick={toggle}
      title={`${isDark ? "Dark" : "Light"} mode — auto-switches at 7 AM / 7 PM IST. Click to toggle.`}
      aria-label="Toggle dark mode"
      className={clsx(
        "relative inline-flex h-7 w-14 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary-400",
        isDark ? "bg-primary-600" : "bg-gray-300"
      )}
    >
      <span
        className={clsx(
          "inline-flex h-6 w-6 items-center justify-center rounded-full bg-white text-gray-700 shadow transform transition-transform",
          isDark ? "translate-x-7" : "translate-x-1"
        )}
      >
        {isDark ? <Moon className="w-3.5 h-3.5" /> : <Sun className="w-3.5 h-3.5" />}
      </span>
    </button>
  );
}
