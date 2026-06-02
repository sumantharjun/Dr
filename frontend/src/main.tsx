import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

// Apply persisted theme as early as possible to avoid a flash of the wrong palette.
try {
  const raw = localStorage.getItem("baby");
  if (raw) {
    const baby = JSON.parse(raw);
    const color = baby?.theme_color === "pink" ? "pink" : "blue";
    document.documentElement.setAttribute("data-theme", color);
  } else {
    document.documentElement.setAttribute("data-theme", "blue");
  }
} catch {
  document.documentElement.setAttribute("data-theme", "blue");
}

// Resolve light/dark before first paint (no flash): time-based schedule
// (dark 7 PM–7 AM IST) unless a manual override is still within the current
// schedule window. Mirrors store/themeStore.ts.
try {
  const utcMs = Date.now() + new Date().getTimezoneOffset() * 60000;
  const istHour = new Date(utcMs + 5.5 * 3600000).getHours();
  const scheduled = istHour >= 19 || istHour < 7 ? "dark" : "light";
  let theme = scheduled;
  const ov = JSON.parse(localStorage.getItem("theme_override") || "null");
  if (ov && ov.base === scheduled && (ov.theme === "light" || ov.theme === "dark")) {
    theme = ov.theme;
  }
  document.documentElement.classList.toggle("dark", theme === "dark");
} catch {
  /* ignore */
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
