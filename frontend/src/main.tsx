import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

// Apply the account's palette before first paint, or the app renders a frame in
// the default colour and visibly flips. Read straight from localStorage rather
// than through the store, which hasn't initialised this early.
try {
  const stored = localStorage.getItem("app_theme_color");
  const valid = ["green", "blue", "pink", "lilac", "peach", "slate"];
  document.documentElement.setAttribute(
    "data-theme",
    stored && valid.includes(stored) ? stored : "green",
  );
} catch {
  document.documentElement.setAttribute("data-theme", "green");
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
