import { useState, FormEvent } from "react";
import { Link } from "react-router-dom";
import api from "../services/api";
import Mascot from "../components/Mascot";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!email.trim() || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
      setFieldError("Enter a valid email address");
      return;
    }
    setLoading(true);
    try {
      await api.post("/auth/forgot-password", { email });
      setSent(true);
    } catch (err: any) {
      if (err.response?.status === 429) setError("Too many requests. Please wait a few minutes and try again.");
      else setError(err.response?.data?.detail || "Something went wrong. Please try again.");
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
          <h2 className="text-xl font-bold text-gray-900 mt-2">Forgot password</h2>
          <p className="text-gray-500 text-sm mt-2 text-center">
            Enter your email and we'll send you a link to reset your password.
          </p>
        </div>

        {sent ? (
          <div className="text-center space-y-4">
            <div className="bg-green-50 text-green-700 text-sm px-4 py-3 rounded-lg">
              If an account exists for <span className="font-medium">{email}</span>, a reset link is
              on its way. The link expires in 1 hour.
            </div>
            <Link to="/login" className="inline-block text-primary-600 font-medium hover:underline text-sm">
              Back to sign in
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            {error && <div className="bg-red-50 text-red-700 text-sm px-4 py-3 rounded-lg">{error}</div>}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => { setEmail(e.target.value); if (fieldError) setFieldError(""); }}
                aria-invalid={!!fieldError}
                className={`w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 ${
                  fieldError ? "border-red-400 focus:ring-red-400" : "border-gray-300 focus:ring-primary-500"
                }`}
                placeholder="you@example.com"
              />
              {fieldError && <p className="text-xs text-red-600 mt-1">{fieldError}</p>}
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white font-semibold py-2.5 rounded-lg transition-colors"
            >
              {loading ? "Sending…" : "Send reset link"}
            </button>
            <p className="text-center text-sm text-gray-500">
              Remembered it?{" "}
              <Link to="/login" className="text-primary-600 font-medium hover:underline">Sign in</Link>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
