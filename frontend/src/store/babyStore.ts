import { create } from "zustand";

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
  theme_color: "blue" | "pink";
  created_at: string;
  updated_at: string;
}

interface BabyState {
  baby: Baby | null;
  setBaby: (baby: Baby | null) => void;
  applyTheme: (color: "blue" | "pink") => void;
}

function applyHtmlTheme(color: "blue" | "pink") {
  if (typeof document !== "undefined") {
    document.documentElement.setAttribute("data-theme", color);
  }
}

function loadBaby(): Baby | null {
  try {
    const raw = localStorage.getItem("baby");
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Baby;
    applyHtmlTheme(parsed.theme_color);
    return parsed;
  } catch {
    return null;
  }
}

export const useBabyStore = create<BabyState>((set) => ({
  baby: loadBaby(),
  setBaby: (baby) => {
    if (baby) {
      localStorage.setItem("baby", JSON.stringify(baby));
      applyHtmlTheme(baby.theme_color);
    } else {
      localStorage.removeItem("baby");
      applyHtmlTheme("blue"); // Sleeping_Bear_Mascot / pre-login default
    }
    set({ baby });
  },
  applyTheme: (color) => {
    applyHtmlTheme(color);
    set((s) =>
      s.baby ? { baby: { ...s.baby, theme_color: color } } : s
    );
  },
}));
