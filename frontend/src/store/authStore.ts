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
    set({ user, token });
  },

  setUser: (user) => {
    setStoredUser(user);
    set({ user });
  },

  logout: () => {
    clearSession();
    set({ user: null, token: null });
  },
}));
