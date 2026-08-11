import { useState, useEffect, FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Palette, Baby as BabyIcon, Cpu, ChevronRight, Check, Plus } from "lucide-react";
import { clsx } from "clsx";
import api from "../services/api";
import BabyProfileFields, { BabyForm, formFor, isDirty } from "../components/BabyProfileFields";
import { MAX_BABIES, useBabyStore } from "../store/babyStore";
import { useAuthStore } from "../store/authStore";
import { useToastStore } from "../store/toastStore";
import { earliestDobISO, todayISO } from "../services/age";
import { applyTheme as applyAppTheme, DEFAULT_THEME } from "../services/theme";
import { THEME_COLORS, type Device, type ThemeColor } from "../types";

export default function SettingsPage() {
  const babies = useBabyStore((s) => s.babies);
  const upsertBaby = useBabyStore((s) => s.upsertBaby);
  const removeBaby = useBabyStore((s) => s.removeBaby);
  const { user, setUser } = useAuthStore();
  const { addToast } = useToastStore();
  const navigate = useNavigate();

  const [theme, setThemeLocal] = useState<ThemeColor>(user?.theme_color ?? DEFAULT_THEME);
  const [device, setDevice] = useState<Device | null>(null);
  const [saving, setSaving] = useState(false);
  const [removingId, setRemovingId] = useState<number | null>(null);
  const [forms, setForms] = useState<Record<number, BabyForm>>(() =>
    Object.fromEntries(babies.map((b) => [b.id, formFor(b)])),
  );

  useEffect(() => {
    api
      .get("/devices/")
      .then((r) => setDevice(r.data[0] ?? null))
      .catch(() => setDevice(null));
  }, []);

  // Seed a form for any baby that appears (added elsewhere, or loaded after
  // mount) and drop forms for ones that vanish. Keyed on the ID LIST, not on
  // `babies` itself — the store hands back a new array after every save, and
  // depending on that would wipe whatever the user was mid-way through typing
  // in the other baby's fields.
  const babyIds = babies.map((b) => b.id).join(",");
  useEffect(() => {
    setForms((prev) => {
      const next: Record<number, BabyForm> = {};
      for (const b of babies) next[b.id] = prev[b.id] ?? formFor(b);
      return next;
    });
  }, [babyIds]); // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * The palette saves on click rather than waiting for Save — it's a
   * direct-manipulation control and the preview applies instantly, so deferring
   * it would leave the app showing a colour that isn't stored. Rolled back on
   * failure.
   */
  async function pickTheme(color: ThemeColor) {
    const previous = theme;
    setThemeLocal(color);
    applyAppTheme(color);
    try {
      const { data } = await api.patch("/auth/me/preferences", { theme_color: color });
      setUser(data);
    } catch (err: any) {
      setThemeLocal(previous);
      applyAppTheme(previous);
      addToast(err.response?.data?.detail || "Couldn't change the theme", "error");
    }
  }

  /**
   * One Save for every baby on the page.
   *
   * Validates all of them first and refuses the whole submit if any is bad —
   * saving one twin and rejecting the other would leave the page in a state
   * where it isn't obvious what was written. Only changed babies are sent.
   */
  async function handleSave(e: FormEvent) {
    e.preventDefault();

    for (const b of babies) {
      const f = forms[b.id];
      if (!f) continue;
      // Name the baby in each message: with two sets of fields on screen,
      // "Weight must be between…" alone doesn't say which one to fix.
      if (!f.name.trim()) {
        addToast(`${b.name}: name is required`, "error");
        return;
      }
      const w = Number(f.weight);
      if (!w || w < 0.5 || w > 30) {
        addToast(`${b.name}: weight must be between 0.5 and 30 kg`, "error");
        return;
      }
      if (f.dob && (f.dob > todayISO() || f.dob < earliestDobISO())) {
        addToast(`${b.name}: please check the date of birth`, "error");
        return;
      }
    }

    const changed = babies.filter((b) => forms[b.id] && isDirty(b, forms[b.id]));
    if (changed.length === 0) {
      addToast("No changes to save", "info");
      return;
    }

    setSaving(true);
    try {
      for (const b of changed) {
        const f = forms[b.id];
        const { data } = await api.patch(`/baby/${b.id}`, {
          name: f.name.trim(),
          gender: f.gender,
          // Omitted when blank: PATCH treats null as "leave unchanged", and
          // there is no way to clear a DOB back to unknown once set.
          ...(f.dob ? { date_of_birth: f.dob } : {}),
          weight_kg: Number(f.weight),
        });
        upsertBaby(data);
      }
      addToast(changed.length > 1 ? "Profiles saved" : `${changed[0].name}'s profile saved`, "success");
    } catch (err: any) {
      addToast(err.response?.data?.detail || "Failed to save", "error");
    } finally {
      setSaving(false);
    }
  }

  async function handleRemove(id: number, name: string) {
    if (babies.length <= 1) return;
    if (!confirm(
      `Remove ${name}'s profile? Their feeding history is kept but will no ` +
      `longer be linked to a baby. This cannot be undone.`
    )) return;
    setRemovingId(id);
    try {
      await api.delete(`/baby/${id}`);
      removeBaby(id);
      addToast(`${name}'s profile removed`, "success");
    } catch (err: any) {
      addToast(err.response?.data?.detail || "Couldn't remove the profile", "error");
    } finally {
      setRemovingId(null);
    }
  }

  const multiple = babies.length > 1;

  return (
    <div className="p-4 sm:p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-500 text-sm mt-1">
          {/* Not "{babies}'s" — that pluralises into "babies's". */}
          {multiple
            ? "Manage your babies' profiles and app theme."
            : "Manage your baby's profile and app theme."}
        </p>
      </div>

      {/* Theme — an account-level preference, so it sits above the babies. */}
      <section className="bg-white rounded-2xl border border-gray-200 p-5 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Palette className="w-5 h-5 text-primary-600" />
          <h2 className="font-semibold text-gray-900">App theme</h2>
        </div>
        <p className="text-sm text-gray-500 mb-4">
          Pick the colour you'd like across the app.
        </p>
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
          {THEME_COLORS.map((t) => {
            const active = theme === t.value;
            return (
              <button
                key={t.value}
                type="button"
                onClick={() => pickTheme(t.value)}
                aria-pressed={active}
                title={t.label}
                className={clsx(
                  "border-2 rounded-2xl p-3 flex flex-col items-center gap-2 transition-all",
                  active
                    ? "border-primary-500 bg-primary-50 dark:bg-primary-500/15 ring-2 ring-primary-300"
                    : "border-gray-200 hover:border-gray-300 bg-white",
                )}
              >
                {/* Literal hex, not a `primary` class: all six swatches are on
                    screen at once, and the CSS variables only ever hold the
                    currently-active palette. */}
                <span
                  className="w-8 h-8 rounded-full flex items-center justify-center"
                  style={{ backgroundColor: t.swatch }}
                >
                  {/* Non-colour cue as well as the ring — colour alone can't
                      carry state, least of all in a colour picker (WCAG 1.4.1). */}
                  {active && <Check className="w-4 h-4 text-white" />}
                </span>
                <span className="text-xs font-medium text-gray-700">{t.label}</span>
              </button>
            );
          })}
        </div>
      </section>

      {/* Every baby in ONE section with ONE Save — two Save buttons on a single
          page left it ambiguous which one applied to what. */}
      <form onSubmit={handleSave}>
        <section className="bg-white rounded-2xl border border-gray-200 p-5">
          <div className="flex items-center gap-2 mb-5 flex-wrap">
            <BabyIcon className="w-5 h-5 text-primary-600" />
            <h2 className="font-semibold text-gray-900">
              {multiple ? `Babies (${babies.length})` : "Baby profile"}
            </h2>
            {/* Hidden at the limit rather than disabled: a permanently greyed
                button invites clicking to find out why. */}
            {babies.length < MAX_BABIES && (
              <button
                type="button"
                onClick={() => navigate("/baby-setup")}
                className="ml-auto flex items-center gap-1.5 text-xs font-medium text-primary-700 border border-primary-300 hover:bg-primary-50 rounded-lg px-2.5 py-1.5 transition-colors"
              >
                <Plus className="w-3.5 h-3.5" /> Add baby
              </button>
            )}
          </div>

          {babies.length === 0 ? (
            <p className="text-gray-500 text-sm">Baby profile not loaded.</p>
          ) : (
            <div
              className={clsx(
                "grid gap-4",
                // Second column ONLY with more than one baby: a lg:grid-cols-2
                // grid holding a single set of fields would leave it half-width
                // beside dead space.
                multiple && "lg:grid-cols-2",
              )}
            >
              {babies.map((b) => (
                <div
                  key={b.id}
                  className={clsx(
                    // Each baby gets its own sub-panel rather than being split
                    // by a rule — a bare divider read as one form cut in half.
                    // `surface-nested` (index.css) rather than bg-gray-*: the
                    // neutral tokens land ~1.03:1 from the card in dark mode,
                    // which is invisible. Only applied with more than one baby;
                    // a lone panel inside the card would be a box in a box.
                    multiple && "surface-nested border rounded-xl p-4",
                  )}
                >
                  <BabyProfileFields
                    baby={b}
                    value={forms[b.id] ?? formFor(b)}
                    onChange={(next) => setForms((p) => ({ ...p, [b.id]: next }))}
                    onRemove={() => handleRemove(b.id, b.name)}
                    canRemove={multiple}
                    removing={removingId === b.id}
                    compact={multiple}
                  />
                </div>
              ))}
            </div>
          )}

          {babies.length > 0 && (
            <div className="flex justify-end mt-6 pt-4 border-t border-gray-100">
              <button
                type="submit"
                disabled={saving}
                className="bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white font-semibold px-6 py-2.5 rounded-lg transition-colors"
              >
                {saving ? "Saving…" : "Save changes"}
              </button>
            </div>
          )}
        </section>
      </form>

      {/* Device card */}
      <section className="bg-white rounded-2xl border border-gray-200 p-5 mt-6">
        <div className="flex items-center gap-2 mb-4">
          <Cpu className="w-5 h-5 text-primary-600" />
          <h2 className="font-semibold text-gray-900">Device</h2>
        </div>

        {device ? (
          <Link
            to="/devices"
            className="flex items-center gap-3 border border-gray-200 rounded-xl p-4 hover:border-primary-300 hover:bg-primary-50/40 transition-colors"
          >
            <span
              className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                device.status === "online" ? "bg-green-500" : "bg-gray-300"
              }`}
            />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-gray-800 truncate">{device.device_name}</p>
              <p className="text-xs font-mono text-gray-400 truncate">{device.mac_address}</p>
            </div>
            <span className="text-xs text-gray-500 capitalize">{device.status}</span>
            <ChevronRight className="w-4 h-4 text-gray-400 flex-shrink-0" />
          </Link>
        ) : (
          <div className="flex items-center justify-between border border-dashed border-gray-300 rounded-xl p-4">
            <p className="text-sm text-gray-500">No device paired yet.</p>
            <Link
              to="/devices"
              className="bg-primary-600 hover:bg-primary-700 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-colors"
            >
              Pair device
            </Link>
          </div>
        )}
        <p className="text-xs text-gray-400 mt-3">
          Pair a new device, scan its QR code, rotate its API key, or remove it.
        </p>
      </section>
    </div>
  );
}
