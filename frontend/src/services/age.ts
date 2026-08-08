/**
 * Human-readable baby ages.
 *
 * Parents don't think in days past the first fortnight — a 100-day-old is
 * "3 months", not "100 days". The unit shifts with age so the number stays
 * meaningful at every stage, which is how paediatric guidance is written too.
 */

/** The longest span still worth reporting in days rather than weeks. */
const DAYS_CUTOFF = 14;
/** Beyond this, weeks stop being useful and months read better. */
const WEEKS_CUTOFF = 98; // 14 weeks

function plural(n: number, unit: string): string {
  return `${n} ${unit}${n === 1 ? "" : "s"}`;
}

/**
 * Format an age in days. Returns null when the age is unknown, so callers can
 * decide what to render rather than being handed a misleading "0 days".
 */
export function formatAge(ageDays: number | null | undefined): string | null {
  if (ageDays == null || ageDays < 0) return null;

  if (ageDays === 0) return "Born today";
  if (ageDays <= DAYS_CUTOFF) return plural(ageDays, "day");
  if (ageDays < WEEKS_CUTOFF) return plural(Math.floor(ageDays / 7), "week");

  // Average month length: keeps "6 months" landing on the day a parent expects
  // rather than drifting by a few days across the year.
  const months = Math.floor(ageDays / 30.44);
  if (months < 24) return plural(months, "month");

  const years = Math.floor(months / 12);
  const rem = months % 12;
  return rem === 0 ? plural(years, "year") : `${plural(years, "year")} ${plural(rem, "month")}`;
}

/**
 * A complete, displayable sentence fragment for an age.
 *
 * Callers must not append "old" to formatAge() themselves — "Born today" is
 * already a full phrase and "Born today old." is what you get otherwise.
 * Keeping the grammar here means every screen words it the same way.
 */
export function describeAge(ageDays: number | null | undefined): string | null {
  const age = formatAge(ageDays);
  if (age === null) return null;
  return age === "Born today" ? age : `${age} old`;
}

/**
 * Days between an ISO date (YYYY-MM-DD) and today, for previewing an age the
 * user is still typing — before the server has computed `age_days`.
 *
 * Built from local date parts rather than `new Date(iso)`, which parses a bare
 * date as UTC midnight and lands a day out for anyone west of Greenwich.
 */
export function ageDaysFromISO(iso: string): number | null {
  const [y, m, d] = (iso || "").split("-").map(Number);
  if (!y || !m || !d) return null;
  const born = new Date(y, m - 1, d);
  const now = new Date();
  const midnightToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((midnightToday.getTime() - born.getTime()) / 86_400_000);
}

/** Today as YYYY-MM-DD, for the `max` attribute on a date input. */
export function todayISO(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Ten years ago as YYYY-MM-DD — mirrors MAX_AGE_YEARS in schemas/baby.py. */
export function earliestDobISO(): string {
  const d = new Date();
  d.setFullYear(d.getFullYear() - 10);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
