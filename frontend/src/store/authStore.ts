import { create } from "zustand";
import { User } from "../types";
import {
  clearSession,
  getStoredUser,
  getToken,
  setSession,
  setStoredUser,
  updateToken,
} from "../services/tokenStorage";
import { applyTheme, clearStoredTheme, DEFAULT_THEME } from "../services/theme";

interface AuthState {
  user: User | null;
  token: string | null;
  /**
   * Start a session. `remember` picks persistent vs. session-only storage;
   * omit it when re-issuing a token for an already-open session (e.g. after a
   * password change) to leave the user's original choice alone.
   */
  setAuth: (user: User, token: string, remember?: boolean) => void;
  setUser: (user: User) => void;
  logout: () => void;
}

function loadUser(): User | null {
  try {
    const raw = getStoredUser();
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  user: loadUser(),
  token: getToken(),

  setAuth: (user, token, remember) => {
    if (remember === undefined) {
      updateToken(token);
      setStoredUser(user);
    } else {
      setSession(token, user, remember);
    }
    // Every auth response carries the account's colour, so signing in on a new
    // device picks up the right palette immediately.
    if (user.theme_color) applyTheme(user.theme_color);
    set({ user, token });
  },

  setUser: (user) => {
    setStoredUser(user);
    if (user.theme_color) applyTheme(user.theme_color);
    set({ user });
  },

  logout: () => {
    clearSession();
    // Back to the default palette — the next person to sign in on this device
    // shouldn't inherit the previous account's colour.
    clearStoredTheme();
    applyTheme(DEFAULT_THEME);
    set({ user: null, token: null });
  },
}));
