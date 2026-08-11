import { ReactNode, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import api from "../services/api";
import { useAuthStore } from "../store/authStore";
import { useBabyStore } from "../store/babyStore";

/**
 * Gate that sits between authentication and the main app shell:
 *   - No token             -> /login
 *   - Token but no babies  -> /baby-setup
 *   - Token AND >=1 baby   -> render the children (AppLayout)
 *
 * The list is always refetched, even when a cached copy exists. It's one small
 * request, and the cache can be stale in ways that matter now that there can be
 * several babies — one added on another device wouldn't otherwise appear.
 */
export default function BabyGate({ children }: { children: ReactNode }) {
  const { token } = useAuthStore();
  const { babies, setBabies } = useBabyStore();
  // Only block on the very first load; a refresh with babies already cached
  // renders immediately and updates underneath.
  const [checking, setChecking] = useState(babies.length === 0);
  const [needsSetup, setNeedsSetup] = useState(false);

  useEffect(() => {
    if (!token) return;
    api
      .get("/baby/")
      .then((r) => {
        const list = r.data ?? [];
        setBabies(list);
        setNeedsSetup(list.length === 0);
        setChecking(false);
      })
      .catch((err) => {
        // 404 is no longer expected — the endpoint returns [] — but tolerate it
        // in case an older backend is still deployed.
        if (err?.response?.status === 404) setNeedsSetup(true);
        setChecking(false);
      });
  }, [token, setBabies]);

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
