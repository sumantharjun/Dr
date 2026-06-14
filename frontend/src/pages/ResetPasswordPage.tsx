import { useState, FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import api from "../services/api";
import Mascot from "../components/Mascot";

export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const navigate = useNavigate();

  const [pw, setPw] = useState({ new_password: "", confirm: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [showNew, setShowNew] = useState(false);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    const errs: Record<string, string> = {};
    if (!pw.new_password) errs.new_password = "Enter a new password";
    else if (pw.new_password.length < 8) errs.new_password = "Must be at least 8 characters";
    if (pw.confirm !== pw.new_password) errs.confirm = "Passwords do not match";
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setLoading(true);
    try {
      await api.post("/auth/reset-password", { token, new_password: pw.new_password });
      setDone(true);
      setTimeout(() => navigate("/login", { replace: true }), 1800);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Couldn't reset your password. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-cream-50 via-cream-100 to-sky-brand/30 p-4">
      <div className="bg-white rounded-3xl shadow-lg p-8 w-full max-w-md">
        <div className="flex flex-col items-center mb-6">
          <img src="/mascots/UNOVA_Logo.png" alt="UNOVA" className="w-48 sm:w-64 max-w-full h-auto mb-4" />
          <Mascot variant="sleeping" size={150} />
          <h2 className="text-xl font-bold text-gray-900 mt-2">Set a new password</h2>
        </div>

        {!token ? (
          <div className="text-center space-y-4">
            <div className="bg-red-50 text-red-700 text-sm px-4 py-3 rounded-lg">
              This reset link is missing its token. Please request a new link.
            </div>
            <Link to="/forgot-password" className="inline-block text-primary-600 font-medium hover:underline text-sm">
              Request a new link
            </Link>
          </div>
        ) : done ? (
          <div className="text-center space-y-4">
            <div className="bg-green-50 text-green-700 text-sm px-4 py-3 rounded-lg">
              Your password has been reset. Redirecting you to sign in…
            </div>
            <Link to="/login" className="inline-block text-primary-600 font-medium hover:underline text-sm">
              Go to sign in
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            {error && <div className="bg-red-50 text-red-700 text-sm px-4 py-3 rounded-lg">{error}</div>}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">New password</label>
              <div className="relative">
                <input
                  type={showNew ? "text" : "password"}
                  value={pw.new_password}
                  onChange={(e) => { setPw((p) => ({ ...p, new_password: e.target.value })); if (errors.new_password) setErrors((p) => ({ ...p, new_password: "" })); }}
                  aria-invalid={!!errors.new_password}
                  className={`w-full border rounded-lg px-3 py-2.5 pr-10 text-sm focus:outline-none focus:ring-2 ${
                    errors.new_password ? "border-red-400 focus:ring-red-400" : "border-gray-300 focus:ring-primary-500"
                  }`}
                  placeholder="Min. 8 characters"
                />
                <button
                  type="button"
                  onClick={() => setShowNew((v) => !v)}
                  tabIndex={-1}
                  aria-label={showNew ? "Hide password" : "Show password"}
                  className="absolute inset-y-0 right-0 flex items-center px-3 text-gray-400 hover:text-gray-600"
                >
                  {showNew ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {errors.new_password && <p className="text-xs text-red-600 mt-1">{errors.new_password}</p>}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Confirm new password</label>
              <input
                type="password"
                value={pw.confirm}
                onChange={(e) => { setPw((p) => ({ ...p, confirm: e.target.value })); if (errors.confirm) setErrors((p) => ({ ...p, confirm: "" })); }}
                aria-invalid={!!errors.confirm}
                className={`w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 ${
                  errors.confirm ? "border-red-400 focus:ring-red-400" : "border-gray-300 focus:ring-primary-500"
                }`}
                placeholder="Re-enter your new password"
              />
              {errors.confirm && <p className="text-xs text-red-600 mt-1">{errors.confirm}</p>}
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white font-semibold py-2.5 rounded-lg transition-colors"
            >
              {loading ? "Resetting…" : "Reset password"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
