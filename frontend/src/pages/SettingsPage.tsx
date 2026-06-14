import { useState, useEffect, FormEvent } from "react";
import { Link } from "react-router-dom";
import { Palette, Baby as BabyIcon, Cpu, ChevronRight } from "lucide-react";
import api from "../services/api";
import Mascot from "../components/Mascot";
import { useBabyStore } from "../store/babyStore";
import { useToastStore } from "../store/toastStore";
import type { Device } from "../types";

export default function SettingsPage() {
  const { baby, setBaby, applyTheme } = useBabyStore();
  const { addToast } = useToastStore();

  const [name, setName] = useState(baby?.name ?? "");
  const [gender, setGender] = useState<"male" | "female">(baby?.gender ?? "male");
  const [weight, setWeight] = useState(baby ? String(baby.weight_kg) : "");
  const [theme, setThemeLocal] = useState<"blue" | "pink">(baby?.theme_color ?? "blue");
  const [saving, setSaving] = useState(false);
  const [device, setDevice] = useState<Device | null>(null);

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

  function pickTheme(color: "blue" | "pink") {
    setThemeLocal(color);
    applyTheme(color); // instant preview
  }

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    const w = Number(weight);
    if (!w || w < 0.5 || w > 30) {
      addToast("Weight must be between 0.5 and 30 kg", "error");
      return;
    }
    setSaving(true);
    try {
      const { data } = await api.patch("/baby/", {
        name: name.trim() || null,
        gender,
        weight_kg: w,
        theme_color: theme,
      });
      setBaby(data);
      addToast("Settings saved", "success");
    } catch (err: any) {
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
            Choose the theme colour.
          </p>
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => pickTheme("blue")}
              className={`border-2 rounded-2xl p-4 flex items-center gap-3 transition-all ${
                theme === "blue"
                  ? "border-sky-brand bg-sky-brand/20 dark:bg-sky-brand/10 ring-2 ring-sky-brand/40"
                  : "border-gray-200 hover:border-gray-300 bg-white"
              }`}
            >
              <span className="w-8 h-8 rounded-full bg-sky-brand" />
              <div className="text-left">
                <p className="text-sm font-semibold text-gray-800">Blue</p>
                {/* <p className="text-xs text-gray-500">Boy default</p> */}
              </div>
            </button>
            <button
              type="button"
              onClick={() => pickTheme("pink")}
              className={`border-2 rounded-2xl p-4 flex items-center gap-3 transition-all ${
                theme === "pink"
                  ? "border-pink-300 dark:border-pink-500/50 bg-pink-50 dark:bg-pink-500/15 ring-2 ring-pink-200"
                  : "border-gray-200 hover:border-gray-300 bg-white"
              }`}
            >
              <span className="w-8 h-8 rounded-full bg-pink-300" />
              <div className="text-left">
                <p className="text-sm font-semibold text-gray-800">Pink</p>
                {/* <p className="text-xs text-gray-500">Girl default</p> */}
              </div>
            </button>
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
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Name <span className="text-gray-400 text-xs">(optional)</span>
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400"
                  maxLength={255}
                />
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
        </section>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={saving}
            className="bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white font-semibold px-6 py-2.5 rounded-lg transition-colors"
          >
            {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
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
