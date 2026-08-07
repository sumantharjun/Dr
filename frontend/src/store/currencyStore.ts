import { create } from "zustand";
import api from "../services/api";

export type Currency = "INR" | "USD" | "EUR" | "GBP";

export const CURRENCIES: { code: Currency; symbol: string; label: string }[] = [
  { code: "INR", symbol: "₹", label: "Indian Rupee"    },
  { code: "USD", symbol: "$", label: "US Dollar"       },
  { code: "EUR", symbol: "€", label: "Euro"            },
  { code: "GBP", symbol: "£", label: "British Pound"   },
];

// Locale is pinned per currency rather than left to the browser, so the same
// price renders identically for every visitor (a de-DE browser would otherwise
// format USD as "4,58 $").
const LOCALES: Record<Currency, string> = {
  INR: "en-IN",
  USD: "en-US",
  EUR: "en-IE",
  GBP: "en-GB",
};

const STORAGE_KEY = "shop_currency";

function readStored(): Currency {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v && CURRENCIES.some((c) => c.code === v)) return v as Currency;
  } catch {
    /* ignore — private mode / storage disabled */
  }
  return "INR"; // INR stays the default for everyone
}

/**
 * Format an INR amount in the target currency.
 *
 * Every price in the database is INR (see backend/app/routers/orders.py), so
 * this converts on the way out. Non-INR results are prefixed with "≈" because
 * they're a live-rate approximation of a price that is still charged in rupees.
 * Falls back to INR whenever rates haven't loaded or the code is missing, so a
 * failed rate fetch can never render a wrong number — only an unconverted one.
 */
export function formatMoney(
  amountInr: number,
  currency: Currency,
  rates: Record<string, number> | null,
): string {
  const rate = currency === "INR" ? 1 : rates?.[currency];
  const usable = typeof rate === "number" && rate > 0;
  const code: Currency = usable ? currency : "INR";
  const value = usable ? amountInr * (rate as number) : amountInr;

  const formatted = new Intl.NumberFormat(LOCALES[code], {
    style: "currency",
    currency: code,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);

  return code === "INR" ? formatted : `≈ ${formatted}`;
}

interface CurrencyState {
  currency: Currency;
  rates: Record<string, number> | null;
  /** True when the backend served cached/fallback rates because a refresh failed. */
  stale: boolean;
  /** Epoch seconds of the last successful upstream fetch, if known. */
  fetchedAt: number | null;
  setCurrency: (c: Currency) => void;
  loadRates: () => Promise<void>;
}

export const useCurrencyStore = create<CurrencyState>((set, get) => ({
  currency: readStored(),
  rates: null,
  stale: false,
  fetchedAt: null,

  setCurrency: (c) => {
    try {
      localStorage.setItem(STORAGE_KEY, c);
    } catch {
      /* ignore */
    }
    set({ currency: c });
  },

  loadRates: async () => {
    if (get().rates) return; // already loaded this session
    try {
      const { data } = await api.get("/orders/rates");
      set({ rates: data.rates, stale: data.stale, fetchedAt: data.fetched_at });
    } catch {
      // Leave rates null — formatMoney then renders INR unconverted rather
      // than showing a made-up figure.
      set({ stale: true });
    }
  },
}));
