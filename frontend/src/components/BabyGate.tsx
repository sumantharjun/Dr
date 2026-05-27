import { ReactNode, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import api from "../services/api";
import { useAuthStore } from "../store/authStore";
import { useBabyStore } from "../store/babyStore";

/**
 * Gate that sits between authentication and the main app shell:
 *   - No token            -> /login
 *   - Token but no baby   -> /baby-setup
 *   - Token AND baby      -> render the children (AppLayout)
 *
 * The baby is fetched once per session and cached in babyStore (which also
 * applies the user's theme to <html data-theme=...>).
 */
export default function BabyGate({ children }: { children: ReactNode }) {
  const { token } = useAuthStore();
  const { baby, setBaby } = useBabyStore();
  const [checking, setChecking] = useState(!baby);
  const [needsSetup, setNeedsSetup] = useState(false);

  useEffect(() => {
    if (!token) return;
    if (baby) {
      setChecking(false);
      return;
    }
    api
      .get("/baby/")
      .then((r) => {
        setBaby(r.data);
        setChecking(false);
      })
      .catch((err) => {
        if (err?.response?.status === 404) {
          setNeedsSetup(true);
        }
        setChecking(false);
      });
  }, [token, baby, setBaby]);

  if (!token) return <Navigate to="/login" replace />;
  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-400 text-sm">
        Loading…
      </div>
    );
  }
  if (needsSetup) return <Navigate to="/baby-setup" replace />;
  return <>{children}</>;
}
