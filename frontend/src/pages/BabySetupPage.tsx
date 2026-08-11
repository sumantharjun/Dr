import { useState, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";
import Mascot from "../components/Mascot";
import { MAX_BABIES, useBabyStore } from "../store/babyStore";
import { ageDaysFromISO, describeAge, earliestDobISO, todayISO } from "../services/age";

export default function BabySetupPage() {
  const [gender, setGender] = useState<"male" | "female" | "">("");
  const [name, setName] = useState("");
  const [dob, setDob] = useState("");
  const [weight, setWeight] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const upsertBaby = useBabyStore((s) => s.upsertBaby);
  const selectBaby = useBabyStore((s) => s.selectBaby);
  const babies = useBabyStore((s) => s.babies);
  const navigate = useNavigate();
  // Reachable directly (browser back, a bookmark) even with the "Add baby"
  // control hidden, so say so up front rather than letting someone fill in the
  // whole form and be rejected by the API.
  const atLimit = babies.length >= MAX_BABIES;

  // Live echo of the age as the parent picks a date — confirms they entered
  // what they meant before they commit to it.
  const age = describeAge(ageDaysFromISO(dob));

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    // Trimmed, so a name of only spaces is rejected the same way the API does.
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError("Please enter your baby's name.");
      return;
    }
    if (!gender) {
      setError("Please select a gender.");
      return;
    }
    if (!dob) {
      setError("Please enter your baby's date of birth.");
      return;
    }
    // Mirror the server's bounds so a bad date is caught before the round trip.
    if (dob > todayISO()) {
      setError("Date of birth can't be in the future.");
      return;
    }
    if (dob < earliestDobISO()) {
      setError("Please check the date of birth — that's more than 10 years ago.");
      return;
    }
    const w = Number(weight);
    if (!w || w < 0.5 || w > 30) {
      setError("Enter a weight between 0.5 and 30 kg.");
      return;
    }
    setSaving(true);
    try {
      const { data } = await api.post("/baby/", {
        name: trimmedName,
        gender,
        date_of_birth: dob,
        weight_kg: w,
      });
      // Add and select it, so the app lands showing the baby just created —
      // relevant when this is a second baby added from Settings.
      upsertBaby(data);
      selectBaby(data.id);
      navigate("/dashboard");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Could not save baby profile");
    } finally {
      setSaving(false);
    }
  }

  if (atLimit) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-cream-50 via-cream-100 to-sky-brand/30 p-4">
        <div className="bg-white rounded-3xl shadow-lg p-8 w-full max-w-md text-center">
          <Mascot variant="sleeping" size={140} className="mx-auto" />
          <h1 className="text-xl font-bold text-gray-900 mt-4">
            You've added the maximum of {MAX_BABIES} babies
          </h1>
          <p className="text-gray-500 text-sm mt-2">
            Remove one from Settings first if you need to add another.
          </p>
          <button
            type="button"
            onClick={() => navigate("/settings")}
            className="mt-6 w-full bg-primary-600 hover:bg-primary-700 text-white font-semibold py-2.5 rounded-lg transition-colors"
          >
            Back to Settings
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-cream-50 via-cream-100 to-sky-brand/30 p-4">
      <div className="bg-white rounded-3xl shadow-lg p-8 w-full max-w-lg">
        <div className="flex flex-col items-center mb-6">
          <img
            src="/mascots/UNOBOT_Logo.png"
            alt="UNOBOT"
            className="w-56 sm:w-72 max-w-full h-auto mb-4"
          />
          <Mascot variant="sleeping" size={180} />
          <h1 className="text-xl font-bold text-gray-900 mt-2">
            Tell us about your baby
          </h1>
          <p className="text-gray-500 text-sm mt-1 text-center">
            We'll personalise the app for your little one. You can edit these
            details any time from Settings.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {error && (
            <div className="bg-red-50 text-red-700 text-sm px-4 py-3 rounded-lg">
              {error}
            </div>
          )}

          {/* Gender (required) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Gender <span className="text-red-500">*</span>
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setGender("male")}
                className={`border-2 rounded-2xl px-4 py-4 transition-all flex flex-col items-center gap-1 ${
                  gender === "male"
                    ? "border-sky-brand bg-sky-brand/20 ring-2 ring-sky-brand/40"
                    : "border-gray-200 hover:border-gray-300 bg-white"
                }`}
              >
                <span className="text-2xl">👦</span>
                <span className="text-sm font-semibold text-gray-800">Boy</span>
              </button>
              <button
                type="button"
                onClick={() => setGender("female")}
                className={`border-2 rounded-2xl px-4 py-4 transition-all flex flex-col items-center gap-1 ${
                  gender === "female"
                    ? "border-pink-300 bg-pink-50 ring-2 ring-pink-200"
                    : "border-gray-200 hover:border-gray-300 bg-white"
                }`}
              >
                <span className="text-2xl">👧</span>
                <span className="text-sm font-semibold text-gray-800">Girl</span>
              </button>
            </div>
          </div>

          {/* Date of birth (required) */}
          <div>
            <label htmlFor="dob" className="block text-sm font-medium text-gray-700 mb-1">
              Date of birth <span className="text-red-500">*</span>
            </label>
            <input
              id="dob"
              type="date"
              value={dob}
              onChange={(e) => setDob(e.target.value)}
              required
              max={todayISO()}
              min={earliestDobISO()}
              className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400"
            />
            <p className="text-xs text-gray-400 mt-1">
              {age ? `${age}.` : "Used for age-appropriate feeding volume and interval guidance."}
            </p>
          </div>

          {/* Weight (required) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Weight (kg) <span className="text-red-500">*</span>
            </label>
            <input
              type="number"
              min="0.5"
              max="30"
              step="0.1"
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
              required
              className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400"
              placeholder="e.g. 3.5"
            />
            <p className="text-xs text-gray-400 mt-1">
              Used for feeding analysis and growth tracking.
            </p>
          </div>

          {/* Name (required) */}
          <div>
            <label htmlFor="baby-name" className="block text-sm font-medium text-gray-700 mb-1">
              Baby's name <span className="text-red-500">*</span>
            </label>
            <input
              id="baby-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400"
              placeholder="e.g. Aarav"
              maxLength={255}
            />
            <p className="text-xs text-gray-400 mt-1">
              Used to personalise greetings and reminders across the app.
            </p>
          </div>

          <button
            type="submit"
            disabled={saving}
            className="w-full bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white font-semibold py-2.5 rounded-lg transition-colors"
          >
            {saving ? "Saving…" : "Continue"}
          </button>
        </form>
      </div>
    </div>
  );
}
