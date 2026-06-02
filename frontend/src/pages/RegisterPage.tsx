import { useState, FormEvent } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import api from "../services/api";
import { useAuthStore } from "../store/authStore";
import Mascot from "../components/Mascot";

export default function RegisterPage() {
  const [form, setForm] = useState({ email: "", full_name: "", password: "" });
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const { setAuth } = useAuthStore();
  const navigate = useNavigate();

  function clearFieldError(key: string) {
    setFieldErrors((p) => (p[key] ? { ...p, [key]: "" } : p));
  }

  function validate() {
    const errs: Record<string, string> = {};
    if (!form.full_name.trim()) errs.full_name = "Full name is required";
    if (!form.email.trim()) errs.email = "Email is required";
    else if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email)) errs.email = "Enter a valid email address";
    if (!form.password) errs.password = "Password is required";
    else if (form.password.length < 8) errs.password = "Password must be at least 8 characters";
    if (!confirmPassword) errs.confirmPassword = "Please confirm your password";
    else if (form.password !== confirmPassword) errs.confirmPassword = "Passwords do not match";
    return errs;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    const errs = validate();
    setFieldErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setLoading(true);
    try {
      const { data } = await api.post("/auth/register", form);
      setAuth(data.user, data.access_token);
      navigate("/dashboard");
    } catch (err: any) {
      const status = err.response?.status;
      if (status === 400) setError("That email is already registered.");
      else if (status === 429) setError("Too many attempts. Please wait a bit and try again.");
      else setError(err.response?.data?.detail || "Registration failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-cream-50 via-cream-100 to-sky-brand/30 p-4">
      <div className="bg-white rounded-3xl shadow-lg p-8 w-full max-w-md">
        <div className="flex flex-col items-center mb-6">
          <img
            src="/mascots/UNOVA_Logo.png"
            alt="UNOVA"
            className="w-64 h-auto mb-4"
          />
          <Mascot variant="sleeping" size={170} />
          <h2 className="text-xl font-bold text-gray-900 mt-2">Create Account</h2>
          <p className="text-xs tracking-widest text-primary-600 font-medium mt-1">
            SAFE · TRUST · PRECISE
          </p>
          <p className="text-gray-500 text-sm mt-3">
            Start monitoring your baby's feeding
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          {error && (
            <div className="bg-red-50 text-red-700 text-sm px-4 py-3 rounded-lg">{error}</div>
          )}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
            <input
              type="text"
              value={form.full_name}
              onChange={(e) => { setForm({ ...form, full_name: e.target.value }); clearFieldError("full_name"); }}
              aria-invalid={!!fieldErrors.full_name}
              className={`w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 ${
                fieldErrors.full_name ? "border-red-400 focus:ring-red-400" : "border-gray-300 focus:ring-primary-500"
              }`}
              placeholder="Jane Smith"
            />
            {fieldErrors.full_name && <p className="text-xs text-red-600 mt-1">{fieldErrors.full_name}</p>}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              value={form.email}
              onChange={(e) => { setForm({ ...form, email: e.target.value }); clearFieldError("email"); }}
              aria-invalid={!!fieldErrors.email}
              className={`w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 ${
                fieldErrors.email ? "border-red-400 focus:ring-red-400" : "border-gray-300 focus:ring-primary-500"
              }`}
              placeholder="you@example.com"
            />
            {fieldErrors.email && <p className="text-xs text-red-600 mt-1">{fieldErrors.email}</p>}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={form.password}
                onChange={(e) => { setForm({ ...form, password: e.target.value }); clearFieldError("password"); }}
                aria-invalid={!!fieldErrors.password}
                className={`w-full border rounded-lg px-3 py-2.5 pr-10 text-sm focus:outline-none focus:ring-2 ${
                  fieldErrors.password ? "border-red-400 focus:ring-red-400" : "border-gray-300 focus:ring-primary-500"
                }`}
                placeholder="Min. 8 characters"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                tabIndex={-1}
                aria-label={showPassword ? "Hide password" : "Show password"}
                className="absolute inset-y-0 right-0 flex items-center px-3 text-gray-400 hover:text-gray-600"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            {fieldErrors.password && <p className="text-xs text-red-600 mt-1">{fieldErrors.password}</p>}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Confirm Password</label>
            <div className="relative">
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => { setConfirmPassword(e.target.value); clearFieldError("confirmPassword"); }}
                aria-invalid={!!fieldErrors.confirmPassword}
                className={`w-full border rounded-lg px-3 py-2.5 pr-10 text-sm focus:outline-none focus:ring-2 ${
                  fieldErrors.confirmPassword ? "border-red-400 focus:ring-red-400" : "border-gray-300 focus:ring-primary-500"
                }`}
                placeholder="Re-enter your password"
              />
            </div>
            {(fieldErrors.confirmPassword || (confirmPassword && form.password !== confirmPassword)) && (
              <p className="text-xs text-red-600 mt-1">
                {fieldErrors.confirmPassword || "Passwords do not match"}
              </p>
            )}
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white font-semibold py-2.5 rounded-lg transition-colors"
          >
            {loading ? "Creating account..." : "Create Account"}
          </button>
        </form>

        <p className="text-center text-sm text-gray-500 mt-6">
          Already have an account?{" "}
          <Link to="/login" className="text-primary-600 font-medium hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
