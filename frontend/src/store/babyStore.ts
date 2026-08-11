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
  created_at: string;
  updated_at: string;
}

interface BabyState {
  baby: Baby | null;
  setBaby: (baby: Baby | null) => void;
}

function loadBaby(): Baby | null {
  try {
    const raw = localStorage.getItem("baby");
    return raw ? (JSON.parse(raw) as Baby) : null;
  } catch {
    return null;
  }
}

/**
 * The baby profile. Note it no longer carries the app colour — that moved to
 * the user (see services/theme.ts and store/authStore.ts), because the palette
 * is a free choice for the account rather than something derived from a baby.
 */
export const useBabyStore = create<BabyState>((set) => ({
  baby: loadBaby(),
  setBaby: (baby) => {
    if (baby) localStorage.setItem("baby", JSON.stringify(baby));
    else localStorage.removeItem("baby");
    set({ baby });
  },
}));
