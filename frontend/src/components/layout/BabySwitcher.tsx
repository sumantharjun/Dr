import { useEffect, useRef, useState } from "react";
import { ChevronDown, Check } from "lucide-react";
import { clsx } from "clsx";
import { useBabyStore } from "../../store/babyStore";
import { formatAge } from "../../services/age";

/**
 * Header control for choosing which baby the app is showing.
 *
 * Renders nothing when there's only one baby — the overwhelming majority of
 * accounts — so single-baby parents see no change at all from multi-baby
 * support.
 */
export default function BabySwitcher() {
  const babies = useBabyStore((s) => s.babies);
  const selectedId = useBabyStore((s) => s.selectedId);
  const selectBaby = useBabyStore((s) => s.selectBaby);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click or Escape, matching ProfileMenu.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (babies.length < 2) return null;

  const selected = babies.find((b) => b.id === selectedId);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`Showing ${selected?.name ?? "baby"} — change baby`}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-100 border border-gray-300 transition-colors"
      >
        <span className="truncate max-w-[9rem]">{selected?.name ?? "Select baby"}</span>
        <ChevronDown className={clsx("w-4 h-4 transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div
          role="listbox"
          className="absolute left-0 mt-1 w-56 bg-white border border-gray-200 rounded-xl shadow-lg py-1 z-50"
        >
          {babies.map((b) => {
            const active = b.id === selectedId;
            const age = formatAge(b.age_days);
            return (
              <button
                key={b.id}
                role="option"
                aria-selected={active}
                onClick={() => {
                  selectBaby(b.id);
                  setOpen(false);
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm hover:bg-gray-50 transition-colors"
              >
                {/* Reserve the tick's width on every row so names stay aligned. */}
                <span className="w-4 flex-shrink-0">
                  {active && <Check className="w-4 h-4 text-primary-600" />}
                </span>
                <span className="flex-1 min-w-0">
                  <span className="block truncate text-gray-900">{b.name}</span>
                  {age && <span className="block text-xs text-gray-400">{age}</span>}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
