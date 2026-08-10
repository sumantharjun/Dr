import { useEffect, useRef, useState } from "react";
import api from "../services/api";
import { useAuthStore } from "../store/authStore";
import { User } from "../types";

const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;
const GSI_SRC = "https://accounts.google.com/gsi/client";

/** Minimal shape of the bits of Google Identity Services we use. */
declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (o: Record<string, unknown>) => void;
          renderButton: (el: HTMLElement, o: Record<string, unknown>) => void;
        };
      };
    };
  }
}

/**
 * Load the Google Identity Services script once per page, shared by every
 * caller. Injected on demand rather than sitting in index.html so a build with
 * no client ID makes no third-party request at all.
 */
let gsiPromise: Promise<void> | null = null;
function loadGsi(): Promise<void> {
  if (gsiPromise) return gsiPromise;
  gsiPromise = new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) return resolve();
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GSI_SRC}"]`);
    if (existing) {
      existing.addEventListener("load", () => resolve());
      existing.addEventListener("error", () => reject(new Error("GSI failed to load")));
      return;
    }
    const s = document.createElement("script");
    s.src = GSI_SRC;
    s.async = true;
    s.defer = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("GSI failed to load"));
    document.head.appendChild(s);
  });
  return gsiPromise;
}

/**
 * "Continue with Google".
 *
 * Google hands the browser a signed ID token; we forward it once to
 * /auth/google, which verifies it and returns one of our own session tokens.
 * From then on this is an ordinary session — the same store, the same sliding
 * renewal, the same Remember Me choice.
 *
 * Renders nothing when VITE_GOOGLE_CLIENT_ID is unset, so environments without
 * Google configured simply don't show the option.
 */
export default function GoogleSignInButton({
  remember,
  onError,
  onSuccess,
}: {
  /** Mirrors the "Keep me signed in" checkbox so OAuth honours the same choice. */
  remember: boolean;
  onError: (message: string) => void;
  onSuccess: () => void;
}) {
  const holder = useRef<HTMLDivElement>(null);
  const { setAuth } = useAuthStore();
  const [unavailable, setUnavailable] = useState(false);

  // `remember` is read inside Google's callback, which is registered once. A
  // ref keeps that callback reading the current value instead of the value
  // captured when the button was first rendered.
  const rememberRef = useRef(remember);
  rememberRef.current = remember;

  useEffect(() => {
    if (!CLIENT_ID) return;
    let cancelled = false;

    loadGsi()
      .then(() => {
        if (cancelled || !holder.current || !window.google) return;
        window.google.accounts.id.initialize({
          client_id: CLIENT_ID,
          callback: async (resp: { credential?: string }) => {
            if (!resp.credential) return onError("Google sign-in was cancelled.");
            try {
              const { data } = await api.post("/auth/google", {
                credential: resp.credential,
                remember_me: rememberRef.current,
              });
              setAuth(data.user as User, data.access_token, rememberRef.current);
              onSuccess();
            } catch (err: unknown) {
              const status = (err as { response?: { status?: number } })?.response?.status;
              const detail = (err as { response?: { data?: { detail?: string } } })
                ?.response?.data?.detail;
              if (status === 401) {
                onError(detail || "Google couldn't verify that account.");
              } else if (status === 503) {
                onError("Google sign-in isn't available right now.");
              } else {
                onError(detail || "Couldn't sign in with Google. Please try again.");
              }
            }
          },
        });
        window.google.accounts.id.renderButton(holder.current, {
          theme: "outline",
          size: "large",
          width: 320,
          text: "continue_with",
          shape: "rectangular",
        });
      })
      .catch(() => {
        // Blocked by an extension, offline, or a locked-down network. Say so
        // rather than leaving an empty gap where a button should be.
        if (!cancelled) setUnavailable(true);
      });

    return () => {
      cancelled = true;
    };
  }, [setAuth, onError, onSuccess]);

  if (!CLIENT_ID) return null;

  // Divider first, then the button: this block sits *below* the email form, so
  // the divider has to separate it from the form above rather than trail it.
  return (
    <div className="mt-6">
      <div className="flex items-center gap-3 mb-5">
        <span className="h-px flex-1 bg-gray-200" />
        <span className="text-xs text-gray-400">or</span>
        <span className="h-px flex-1 bg-gray-200" />
      </div>
      {unavailable ? (
        <p className="text-xs text-gray-400 text-center">
          Google sign-in couldn't load. Use your email and password above.
        </p>
      ) : (
        <div ref={holder} className="flex justify-center" />
      )}
    </div>
  );
}
