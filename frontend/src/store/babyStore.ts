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

/**
 * How many babies an account may have. Must match MAX_BABIES_PER_USER in
 * backend/app/routers/baby.py — the API enforces it, this just stops the UI
 * offering an action that would be rejected.
 */
export const MAX_BABIES = 2;

const BABIES_KEY = "babies";
const SELECTED_KEY = "selected_baby_id";

interface BabyState {
  babies: Baby[];
  /** The baby every scoped screen is currently showing. Null only before load. */
  selectedId: number | null;
  setBabies: (babies: Baby[]) => void;
  selectBaby: (id: number) => void;
  /** Insert or replace one baby, keeping the rest of the list intact. */
  upsertBaby: (baby: Baby) => void;
  removeBaby: (id: number) => void;
  clear: () => void;
}

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function persist(babies: Baby[], selectedId: number | null) {
  try {
    localStorage.setItem(BABIES_KEY, JSON.stringify(babies));
    if (selectedId === null) localStorage.removeItem(SELECTED_KEY);
    else localStorage.setItem(SELECTED_KEY, String(selectedId));
  } catch {
    /* storage disabled — state still works for this session */
  }
}

/**
 * Pick which baby to show. Keeps the current selection when it's still valid,
 * so a background refresh of the list can't silently switch the parent to a
 * different baby mid-task. Falls back to the first (oldest) profile.
 */
function resolveSelection(babies: Baby[], current: number | null): number | null {
  if (current !== null && babies.some((b) => b.id === current)) return current;
  return babies.length ? babies[0].id : null;
}

/**
 * All babies on the account, plus which one the app is currently showing.
 *
 * Multi-baby exists for twins: a single account, two independent feeding
 * schedules. The selection here is what every scoped request keys on.
 */
export const useBabyStore = create<BabyState>((set, get) => {
  const babies = read<Baby[]>(BABIES_KEY, []);
  const storedId = Number(localStorage.getItem(SELECTED_KEY));
  return {
    babies,
    selectedId: resolveSelection(babies, Number.isFinite(storedId) && storedId ? storedId : null),

    setBabies: (next) => {
      const selectedId = resolveSelection(next, get().selectedId);
      persist(next, selectedId);
      set({ babies: next, selectedId });
    },

    selectBaby: (id) => {
      if (!get().babies.some((b) => b.id === id)) return;
      persist(get().babies, id);
      set({ selectedId: id });
    },

    upsertBaby: (baby) => {
      const existing = get().babies;
      const next = existing.some((b) => b.id === baby.id)
        ? existing.map((b) => (b.id === baby.id ? baby : b))
        : [...existing, baby];
      const selectedId = resolveSelection(next, get().selectedId);
      persist(next, selectedId);
      set({ babies: next, selectedId });
    },

    removeBaby: (id) => {
      const next = get().babies.filter((b) => b.id !== id);
      // Deliberately re-resolve: removing the selected baby must land on a
      // valid one rather than leaving a dangling id every request would 404 on.
      const selectedId = resolveSelection(next, get().selectedId === id ? null : get().selectedId);
      persist(next, selectedId);
      set({ babies: next, selectedId });
    },

    clear: () => {
      try {
        localStorage.removeItem(BABIES_KEY);
        localStorage.removeItem(SELECTED_KEY);
      } catch {
        /* ignore */
      }
      set({ babies: [], selectedId: null });
    },
  };
});

/** Convenience: the currently-selected baby, or null. */
export function useSelectedBaby(): Baby | null {
  const babies = useBabyStore((s) => s.babies);
  const selectedId = useBabyStore((s) => s.selectedId);
  return babies.find((b) => b.id === selectedId) ?? null;
}
