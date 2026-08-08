import axios, { AxiosError, AxiosRequestConfig } from "axios";
import { clearSession, getToken, updateToken } from "./tokenStorage";

const MAX_RETRIES = 3;
const RETRY_BASE_DELAY_MS = 300;

// Sliding sessions: the API returns a freshly-issued token in this header once
// the current one is past half its life. Swapping it in keeps an active user
// signed in indefinitely. Requires expose_headers on the API's CORS middleware,
// or the browser hides it from JS cross-origin. Axios lowercases header keys.
const RENEWED_TOKEN_HEADER = "x-renewed-token";

declare module "axios" {
  interface AxiosRequestConfig {
    _retryCount?: number;
  }
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "https://unova-api.vsngroups.com",
});

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => {
    const renewed = res.headers?.[RENEWED_TOKEN_HEADER];
    if (typeof renewed === "string" && renewed) {
      updateToken(renewed);
    }
    return res;
  },
  async (err: AxiosError) => {
    const config = err.config as AxiosRequestConfig & { _retryCount?: number };

    if (err.response?.status === 401) {
      // Clear both stores, not just localStorage — otherwise a non-remembered
      // session would leave a dead token in sessionStorage and every later
      // request would keep 401ing.
      clearSession();
      window.location.href = "/login";
      return Promise.reject(err);
    }

    // Do not retry client errors (4xx) — only network errors or 5xx
    const isRetryable =
      !err.response || (err.response.status >= 500 && err.response.status < 600);

    if (isRetryable && config && (config._retryCount ?? 0) < MAX_RETRIES) {
      config._retryCount = (config._retryCount ?? 0) + 1;
      const delay = RETRY_BASE_DELAY_MS * 2 ** (config._retryCount - 1);
      await new Promise((resolve) => setTimeout(resolve, delay));
      return api(config);
    }

    return Promise.reject(err);
  }
);

export default api;
