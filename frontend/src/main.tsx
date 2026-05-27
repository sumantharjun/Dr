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

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
