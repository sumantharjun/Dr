/**
 * Single place that decides *where* the session token lives.
 *
 * "Remember me" → localStorage: survives closing the browser.
 * Otherwise     → sessionStorage: cleared when the tab/browser closes, which
 *                 is what the unticked box is supposed to promise on a shared
 *                 or family device.
 *
 * Everything that needs the token (axios, both WebSocket hooks, the auth store)
 * goes through here — reading localStorage directly would miss non-remembered
 * sessions entirely and silently break them.
 */
const TOKEN_KEY = "access_token";
const USER_KEY = "user";

/** Read from either store. localStorage wins if somehow both are populated. */
export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null; // storage disabled (private mode, hardened settings)
  }
}

export function getStoredUser(): string | null {
  try {
    return localStorage.getItem(USER_KEY) ?? sessionStorage.getItem(USER_KEY);
  } catch {
    return null;
  }
}

/** Persist a brand-new session, choosing the store from the Remember-me choice. */
export function setSession(token: string, user: unknown, remember: boolean): void {
  try {
    clearSession(); // never leave a copy behind in the other store
    const store = remember ? localStorage : sessionStorage;
    store.setItem(TOKEN_KEY, token);
    store.setItem(USER_KEY, JSON.stringify(user));
  } catch {
    /* ignore */
  }
}

/**
 * Replace the token in whichever store already holds it, leaving the
 * remembered/not-remembered choice untouched. Used for sliding renewals and
 * for the re-issued token after a password change — neither of which should
 * move a session between stores.
 */
export function updateToken(token: string): void {
  try {
    if (localStorage.getItem(TOKEN_KEY) !== null) localStorage.setItem(TOKEN_KEY, token);
    else if (sessionStorage.getItem(TOKEN_KEY) !== null) sessionStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* ignore */
  }
}

export function setStoredUser(user: unknown): void {
  try {
    const store = localStorage.getItem(TOKEN_KEY) !== null ? localStorage : sessionStorage;
    store.setItem(USER_KEY, JSON.stringify(user));
  } catch {
    /* ignore */
  }
}

export function clearSession(): void {
  try {
    for (const store of [localStorage, sessionStorage]) {
      store.removeItem(TOKEN_KEY);
      store.removeItem(USER_KEY);
    }
  } catch {
    /* ignore */
  }
}
