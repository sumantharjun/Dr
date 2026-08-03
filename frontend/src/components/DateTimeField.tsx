import { useState } from "react";
import { clsx } from "clsx";
import { ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import {
  format, parse, isValid, isToday, isYesterday, isSameDay, isSameMonth, isAfter,
  startOfMonth, startOfWeek, startOfDay, endOfMonth, endOfWeek, eachDayOfInterval,
  addMonths, subMonths, subMinutes, setHours, setMinutes,
} from "date-fns";

/** Wire format shared with the API. Local wall-clock — never UTC. */
const WIRE = "yyyy-MM-dd'T'HH:mm";

/** Serialise a Date to the wire format the feeding API expects. */
export function toWire(d: Date): string {
  return format(d, WIRE);
}

/** Parse a wire string back to a Date, falling back to now if malformed. */
function fromWire(s: string): Date {
  const d = parse(s, WIRE, new Date());
  return isValid(d) ? d : new Date();
}

const PRESETS: { label: string; minutesAgo: number }[] = [
  { label: "Now", minutesAgo: 0 },
  { label: "15m ago", minutesAgo: 15 },
  { label: "30m ago", minutesAgo: 30 },
  { label: "1h ago", minutesAgo: 60 },
  { label: "2h ago", minutesAgo: 120 },
];

const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
const HOURS = Array.from({ length: 12 }, (_, i) => i + 1);
const MINUTES = Array.from({ length: 12 }, (_, i) => i * 5);

/** "Today at 2:45 PM" / "Yesterday at 11:20 PM" / "28 Jul 2026 at 2:45 PM" */
function summarise(d: Date): string {
  const time = format(d, "h:mm a");
  if (isToday(d)) return `Today at ${time}`;
  if (isYesterday(d)) return `Yesterday at ${time}`;
  return `${format(d, "d MMM yyyy")} at ${time}`;
}

/**
 * Brand-styled replacement for `<input type="datetime-local">`.
 *
 * Presets cover the common case (a feed logged just after it happened) in one
 * tap; the calendar behind the disclosure handles backfilling any date. Expands
 * inline rather than in a popover, so there is no positioning or outside-click
 * handling to get wrong.
 *
 * Styling deliberately uses literal light utilities — `index.css` flips these
 * centrally for dark mode, so `dark:` variants here would be redundant.
 */
export default function DateTimeField({ value, onChange }: {
  value: string;
  onChange: (next: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const selected = fromWire(value);
  const [month, setMonth] = useState(() => startOfMonth(selected));
  const now = new Date();

  const days = eachDayOfInterval({
    start: startOfWeek(startOfMonth(month), { weekStartsOn: 0 }),
    end: endOfWeek(endOfMonth(month), { weekStartsOn: 0 }),
  });

  // 12-hour clock parts, derived from the selected date each render.
  const hour24 = selected.getHours();
  const hour12 = hour24 % 12 === 0 ? 12 : hour24 % 12;
  const meridiem = hour24 < 12 ? "AM" : "PM";
  // Snap DOWN to a 5-minute option so the select always has a value — rounding
  // up could land on an option disabled for being in the future.
  const minute = Math.floor(selected.getMinutes() / 5) * 5;

  function to24(h12: number, mer: string) {
    return mer === "AM" ? (h12 === 12 ? 0 : h12) : h12 === 12 ? 12 : h12 + 12;
  }

  function at(h12: number, mins: number, mer: string) {
    return setMinutes(setHours(selected, to24(h12, mer)), mins);
  }

  /** A feed can't have happened yet, so never emit a future timestamp. */
  function commit(d: Date) {
    onChange(toWire(isAfter(d, now) ? now : d));
  }

  function applyTime(h12: number, mins: number, mer: string) {
    commit(at(h12, mins, mer));
  }

  /**
   * Disable an option only when its *earliest* possible moment is still in the
   * future — so picking "PM" at 11 AM stays blocked, but at 12:30 PM it doesn't
   * get blocked just because the currently-selected hour would overshoot.
   */
  function optionDisabled(h12: number, mins: number, mer: string) {
    return isToday(selected) && isAfter(at(h12, mins, mer), now);
  }

  const selectClass =
    "border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none";

  return (
    <div className="border border-gray-300 rounded-lg p-3 space-y-3">
      {/* Presets — the one-tap path */}
      <div className="flex flex-wrap gap-2">
        {PRESETS.map((p) => {
          const active = Math.abs(selected.getTime() - subMinutes(new Date(), p.minutesAgo).getTime()) < 60_000;
          return (
            <button
              key={p.label}
              type="button"
              aria-pressed={active}
              onClick={() => {
                const next = subMinutes(new Date(), p.minutesAgo);
                onChange(toWire(next));
                // Follow the jump, or the open calendar keeps showing whatever
                // month the user had navigated to with nothing selected in it.
                setMonth(startOfMonth(next));
              }}
              className={clsx(
                "px-3 py-1.5 rounded-full text-xs font-medium transition-colors",
                active
                  ? "bg-primary-600 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200",
              )}
            >
              {p.label}
            </button>
          );
        })}
      </div>

      <p className="text-sm font-medium text-gray-700">{summarise(selected)}</p>

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex items-center gap-1 text-xs font-medium text-primary-600 hover:underline"
      >
        <ChevronDown className={clsx("w-3.5 h-3.5 transition-transform", open && "rotate-180")} />
        Set a different time
      </button>

      {open && (
        <div className="pt-1 space-y-3">
          {/* Month navigation */}
          <div className="flex items-center justify-between">
            <button
              type="button"
              aria-label="Previous month"
              onClick={() => setMonth((m) => subMonths(m, 1))}
              className="p-1 rounded-md text-gray-500 hover:bg-gray-100"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-sm font-semibold text-gray-900">{format(month, "MMMM yyyy")}</span>
            <button
              type="button"
              aria-label="Next month"
              disabled={isSameMonth(month, now)}
              onClick={() => setMonth((m) => addMonths(m, 1))}
              className="p-1 rounded-md text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          {/* Day grid */}
          <div className="grid grid-cols-7 gap-0.5">
            {WEEKDAYS.map((w) => (
              <span key={w} className="text-center text-[10px] font-medium text-gray-400 py-1">
                {w}
              </span>
            ))}
            {days.map((day) => {
              const isSelected = isSameDay(day, selected);
              const outside = !isSameMonth(day, month);
              const future = isAfter(startOfDay(day), startOfDay(now));
              return (
                <button
                  key={day.toISOString()}
                  type="button"
                  disabled={future}
                  aria-current={isSelected ? "date" : undefined}
                  onClick={() => {
                    // Keep the chosen time, change only the calendar date. commit()
                    // clamps if that time hasn't happened yet on the new date.
                    commit(setMinutes(setHours(day, selected.getHours()), selected.getMinutes()));
                  }}
                  className={clsx(
                    "h-8 rounded-md text-xs transition-colors",
                    isSelected && "bg-primary-600 text-white font-semibold",
                    !isSelected && future && "text-gray-300 cursor-not-allowed",
                    !isSelected && !future && isToday(day) && "border border-primary-400 text-gray-700",
                    !isSelected && !future && !isToday(day) && "hover:bg-gray-100",
                    !isSelected && !future && (outside ? "text-gray-300" : "text-gray-700"),
                  )}
                >
                  {format(day, "d")}
                </button>
              );
            })}
          </div>

          {/* Time */}
          <div className="flex items-center gap-2 pt-1">
            <span className="text-xs font-medium text-gray-500">Time</span>
            <select
              aria-label="Hour"
              value={hour12}
              onChange={(e) => applyTime(Number(e.target.value), minute, meridiem)}
              className={selectClass}
            >
              {HOURS.map((h) => (
                <option key={h} value={h} disabled={optionDisabled(h, 0, meridiem)}>{h}</option>
              ))}
            </select>
            <span className="text-gray-400">:</span>
            <select
              aria-label="Minute"
              value={minute}
              onChange={(e) => applyTime(hour12, Number(e.target.value), meridiem)}
              className={selectClass}
            >
              {MINUTES.map((m) => (
                <option key={m} value={m} disabled={optionDisabled(hour12, m, meridiem)}>
                  {String(m).padStart(2, "0")}
                </option>
              ))}
            </select>
            <select
              aria-label="AM or PM"
              value={meridiem}
              onChange={(e) => applyTime(hour12, minute, e.target.value)}
              className={selectClass}
            >
              {/* Earliest AM is 00:00 and earliest PM is 12:00, so only PM can be future. */}
              <option value="AM" disabled={optionDisabled(12, 0, "AM")}>AM</option>
              <option value="PM" disabled={optionDisabled(12, 0, "PM")}>PM</option>
            </select>
          </div>
        </div>
      )}
    </div>
  );
}
