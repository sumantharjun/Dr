import { useState, useRef, useEffect, FormEvent } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { ChevronUp, KeyRound, LogOut, Eye, EyeOff } from "lucide-react";
import { clsx } from "clsx";
import api from "../../services/api";
import { useAuthStore } from "../../store/authStore";
import { useBabyStore } from "../../store/babyStore";
import { useToastStore } from "../../store/toastStore";

const PW_FIELDS = [
  ["current_password", "Current password"],
  ["new_password", "New password"],
  ["confirm", "Confirm new password"],
] as const;

export default function ProfileMenu() {
  const { user, logout, setAuth } = useAuthStore();
  const { setBaby } = useBabyStore();
  const { addToast } = useToastStore();
  const navigate = useNavigate();

  const [menuOpen, setMenuOpen] = useState(false);
  const [showChangePw, setShowChangePw] = useState(false);
  const [showLogout, setShowLogout] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  const [pw, setPw] = useState({ current_password: "", new_password: "", confirm: "" });
  const [pwErrors, setPwErrors] = useState<Record<string, string>>({});
  const [changingPw, setChangingPw] = useState(false);
  const [showNew, setShowNew] = useState(false);

  const initials = (user?.full_name || user?.email || "?")
    .split(" ")
    .map((s) => s[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  // Close the popover on outside click.
  useEffect(() => {
    if (!menuOpen) return;
    function onDown(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setMenuOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [menuOpen]);

  function doLogout() {
    logout();
    setBaby(null);
    navigate("/login", { replace: true });
  }

  function openChangePw() {
    setPw({ current_password: "", new_password: "", confirm: "" });
    setPwErrors({});
    setShowNew(false);
    setShowChangePw(true);
    setMenuOpen(false);
  }

  async function handleChangePassword(e: FormEvent) {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!pw.current_password) errs.current_password = "Enter your current password";
    if (!pw.new_password) errs.new_password = "Enter a new password";
    else if (pw.new_password.length < 8) errs.new_password = "Must be at least 8 characters";
    else if (pw.new_password === pw.current_password)
      errs.new_password = "New password must be different from the current one";
    if (pw.confirm !== pw.new_password) errs.confirm = "Passwords do not match";
    setPwErrors(errs);
    if (Object.keys(errs).length > 0) return;

    setChangingPw(true);
    try {
      const { data } = await api.post("/auth/change-password", {
        current_password: pw.current_password,
        new_password: pw.new_password,
      });
      // The change invalidates all prior tokens; adopt the fresh one the server
      // returns so THIS session keeps working (other sessions are logged out).
      if (data?.access_token && user) setAuth(user, data.access_token);
      addToast("Password changed", "success");
      setShowChangePw(false);
    } catch (err: any) {
      const detail = err.response?.data?.detail as string | undefined;
      if (err.response?.status === 400 && /current password/i.test(detail || "")) {
        setPwErrors({ current_password: "Current password is incorrect" });
      } else if (err.response?.status === 400 && /different/i.test(detail || "")) {
        setPwErrors({ new_password: "New password must be different from the current one" });
      } else {
        addToast(detail || "Failed to change password", "error");
      }
    } finally {
      setChangingPw(false);
    }
  }

  return (
    <div className="relative" ref={wrapRef}>
      {/* Popover */}
      {menuOpen && (
        <div className="absolute bottom-full mb-2 left-0 right-0 bg-white border border-gray-200 rounded-xl shadow-lg overflow-hidden z-20">
          <div className="px-4 py-3 border-b border-gray-100">
            <p className="text-sm font-semibold text-gray-800 truncate">{user?.full_name || "—"}</p>
            <p className="text-xs text-gray-400 truncate">{user?.email}</p>
          </div>
          <button
            onClick={openChangePw}
            className="flex items-center gap-3 w-full px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50"
          >
            <KeyRound className="w-4 h-4" />
            Change password
          </button>
          <button
            onClick={() => { setShowLogout(true); setMenuOpen(false); }}
            className="flex items-center gap-3 w-full px-4 py-2.5 text-sm text-red-600 hover:bg-red-50"
          >
            <LogOut className="w-4 h-4" />
            Log out
          </button>
        </div>
      )}

      {/* Trigger */}
      <button
        onClick={() => setMenuOpen((o) => !o)}
        className="flex items-center gap-3 w-full px-2 py-2 rounded-lg hover:bg-gray-100 transition-colors"
      >
        <div className="w-9 h-9 rounded-full bg-primary-100 text-primary-700 flex items-center justify-center text-sm font-bold flex-shrink-0">
          {initials}
        </div>
        <div className="flex-1 min-w-0 text-left">
          <p className="text-sm font-medium text-gray-800 truncate">{user?.full_name || "Profile"}</p>
          <p className="text-xs text-gray-400 truncate">{user?.email}</p>
        </div>
        <ChevronUp className={clsx("w-4 h-4 text-gray-400 transition-transform", !menuOpen && "rotate-180")} />
      </button>

      {/* Change-password modal — portaled to <body> so it can't be trapped by
          the sidebar's stacking context (otherwise page content can overlap it). */}
      {showChangePw && createPortal(
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 p-4" onMouseDown={() => setShowChangePw(false)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-5" onMouseDown={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-2 mb-4">
              <KeyRound className="w-5 h-5 text-primary-600" />
              <h2 className="font-semibold text-gray-900">Change password</h2>
            </div>
            <form onSubmit={handleChangePassword} className="space-y-4" noValidate>
              {PW_FIELDS.map(([key, label]) => {
                const isNew = key === "new_password";
                return (
                  <div key={key}>
                    <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
                    <div className="relative">
                      <input
                        type={isNew && showNew ? "text" : "password"}
                        value={pw[key]}
                        onChange={(e) => {
                          setPw((p) => ({ ...p, [key]: e.target.value }));
                          setPwErrors((p) => (p[key] ? { ...p, [key]: "" } : p));
                        }}
                        aria-invalid={!!pwErrors[key]}
                        className={clsx(
                          "w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2",
                          isNew && "pr-10",
                          pwErrors[key] ? "border-red-400 focus:ring-red-400" : "border-gray-300 focus:ring-primary-400"
                        )}
                        placeholder={isNew ? "Min. 8 characters" : ""}
                      />
                      {isNew && (
                        <button
                          type="button"
                          onClick={() => setShowNew((v) => !v)}
                          tabIndex={-1}
                          aria-label={showNew ? "Hide password" : "Show password"}
                          className="absolute inset-y-0 right-0 flex items-center px-3 text-gray-400 hover:text-gray-600"
                        >
                          {showNew ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      )}
                    </div>
                    {pwErrors[key] && <p className="text-xs text-red-600 mt-1">{pwErrors[key]}</p>}
                  </div>
                );
              })}
              <div className="flex justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setShowChangePw(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={changingPw}
                  className="bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white font-semibold px-5 py-2 rounded-lg transition-colors"
                >
                  {changingPw ? "Updating…" : "Update"}
                </button>
              </div>
            </form>
          </div>
        </div>,
        document.body
      )}

      {/* Logout confirmation popup — portaled to <body> for the same reason. */}
      {showLogout && createPortal(
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 p-4" onMouseDown={() => setShowLogout(false)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6 text-center" onMouseDown={(e) => e.stopPropagation()}>
            <div className="w-12 h-12 rounded-full bg-red-50 flex items-center justify-center mx-auto mb-3">
              <LogOut className="w-6 h-6 text-red-600" />
            </div>
            <h2 className="font-semibold text-gray-900 text-lg">Log out?</h2>
            <p className="text-sm text-gray-500 mt-1 mb-5">You'll need to sign in again to access the dashboard.</p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowLogout(false)}
                className="flex-1 px-4 py-2.5 text-sm font-medium text-gray-700 border border-gray-300 hover:bg-gray-50 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={doLogout}
                className="flex-1 px-4 py-2.5 text-sm font-semibold text-white bg-red-600 hover:bg-red-700 rounded-lg"
              >
                Log out
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
