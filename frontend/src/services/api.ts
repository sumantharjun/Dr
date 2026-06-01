import axios, { AxiosError, AxiosRequestConfig } from "axios";

const MAX_RETRIES = 3;
const RETRY_BASE_DELAY_MS = 300;

declare module "axios" {
  interface AxiosRequestConfig {
    _retryCount?: number;
  }
}

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "https://unova-api.vsngroups.com",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  async (err: AxiosError) => {
    const config = err.config as AxiosRequestConfig & { _retryCount?: number };

    if (err.response?.status === 401) {
      localStorage.removeItem("access_token");
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
