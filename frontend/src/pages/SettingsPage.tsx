import { useState, useEffect, FormEvent } from "react";
import { Link } from "react-router-dom";
import { Palette, Baby as BabyIcon, Cpu, ChevronRight, Check } from "lucide-react";
import { clsx } from "clsx";
import api from "../services/api";
import Mascot from "../components/Mascot";
import { useBabyStore } from "../store/babyStore";
import { useAuthStore } from "../store/authStore";
import { useToastStore } from "../store/toastStore";
import { ageDaysFromISO, describeAge, earliestDobISO, todayISO } from "../services/age";
import { applyTheme as applyAppTheme, DEFAULT_THEME } from "../services/theme";
import { THEME_COLORS, type Device, type ThemeColor } from "../types";

export default function SettingsPage() {
  const { baby, setBaby } = useBabyStore();
  const { user, setUser } = useAuthStore();
  const { addToast } = useToastStore();

  const [name, setName] = useState(baby?.name ?? "");
  const [gender, setGender] = useState<"male" | "female">(baby?.gender ?? "male");
  const [dob, setDob] = useState(baby?.date_of_birth ?? "");
  const [weight, setWeight] = useState(baby ? String(baby.weight_kg) : "");
  const [theme, setThemeLocal] = useState<ThemeColor>(user?.theme_color ?? DEFAULT_THEME);
  const [saving, setSaving] = useState(false);
  const [device, setDevice] = useState<Device | null>(null);

  const age = describeAge(ageDaysFromISO(dob));

  useEffect(() => {
    api
      .get("/devices/")
      .then((r) => setDevice(r.data[0] ?? null))
      .catch(() => setDevice(null));
  }, []);

  if (!baby) {
    return (
      <div className="p-4 sm:p-6 max-w-2xl mx-auto">
        <p className="text-gray-500">Baby profile not loaded.</p>
      </div>
    );
  }

  function pickTheme(color: ThemeColor) {
    setThemeLocal(color);
    applyAppTheme(color); // instant preview; persisted on save below
  }

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      addToast("Baby's name is required", "error");
      return;
    }
    const w = Number(weight);
    if (!w || w < 0.5 || w > 30) {
      addToast("Weight must be between 0.5 and 30 kg", "error");
      return;
    }
    if (dob && (dob > todayISO() || dob < earliestDobISO())) {
      addToast("Please check the date of birth", "error");
      return;
    }
    setSaving(true);
    try {
      const { data } = await api.patch("/baby/", {
        name: trimmedName,
        gender,
        // Omitted when blank: PATCH treats null as "leave unchanged", and there
        // is no way to clear a DOB back to unknown once set.
        ...(dob ? { date_of_birth: dob } : {}),
        weight_kg: w,
      });
      setBaby(data);

      // The colour belongs to the account, so it saves separately from the baby.
      if (theme !== user?.theme_color) {
        const { data: updatedUser } = await api.patch("/auth/me/preferences", {
          theme_color: theme,
        });
        setUser(updatedUser);
      }
      addToast("Settings saved", "success");
    } catch (err: any) {
      // Undo the instant preview — otherwise the app keeps a colour that was
      // never persisted and reverts confusingly on the next reload.
      const saved = user?.theme_color ?? DEFAULT_THEME;
      setThemeLocal(saved);
      applyAppTheme(saved);
      addToast(err.response?.data?.detail || "Failed to save", "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="p-4 sm:p-6 max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-500 text-sm mt-1">
          Manage your baby's profile and app theme.
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Theme card */}
        <section className="bg-white rounded-2xl border border-gray-200 p-5">
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

        {/* Baby info card */}
        <section className="bg-white rounded-2xl border border-gray-200 p-5">
          <div className="flex items-center gap-2 mb-4">
            <BabyIcon className="w-5 h-5 text-primary-600" />
            <h2 className="font-semibold text-gray-900">Baby profile</h2>
          </div>

          <div className="flex items-start gap-5">
            <Mascot variant="auto" size={120} className="flex-shrink-0" />
            <div className="flex-1 space-y-4">
              <div>
                <label htmlFor="settings-name" className="block text-sm font-medium text-gray-700 mb-1">
                  Name <span className="text-red-500">*</span>
                </label>
                <input
                  id="settings-name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400"
                  maxLength={255}
                />
              </div>

              <div>
                <label htmlFor="settings-dob" className="block text-sm font-medium text-gray-700 mb-1">
                  Date of birth
                </label>
                <input
                  id="settings-dob"
                  type="date"
                  value={dob}
                  onChange={(e) => setDob(e.target.value)}
                  max={todayISO()}
                  min={earliestDobISO()}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400"
                />
                {age ? (
                  <p className="text-xs text-gray-400 mt-1">{age}.</p>
                ) : (
                  // Profiles created before this field existed land here. Say
                  // what it unlocks rather than just flagging it as empty.
                  <p className="text-xs text-amber-600 mt-1">
                    Add a date of birth to enable age-based feeding volume and interval guidance.
                  </p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Gender
                  </label>
                  <select
                    value={gender}
                    onChange={(e) => setGender(e.target.value as "male" | "female")}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400"
                  >
                    <option value="male">Boy</option>
                    <option value="female">Girl</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Weight (kg)
                  </label>
                  <input
                    type="number"
                    min="0.5"
                    max="30"
                    step="0.1"
                    value={weight}
                    onChange={(e) => setWeight(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400"
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="flex justify-end mt-5 pt-4 border-t border-gray-100">
            <button
              type="submit"
              disabled={saving}
              className="bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white font-semibold px-6 py-2.5 rounded-lg transition-colors"
            >
              {saving ? "Saving…" : "Save changes"}
            </button>
          </div>
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
