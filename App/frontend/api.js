const DEFAULT_API_BASE = ["127.0.0.1", "localhost"].includes(window.location.hostname)
  ? "http://127.0.0.1:8000/api"
  : "/api";

let authTokenProvider = () => "";
let unauthorizedHandler = null;

function configuredApiBase() {
  const configBase = window.SKILLNOVA_CONFIG?.apiBaseUrl;
  const runtimeBase = typeof localStorage !== "undefined" ? localStorage.getItem("skillnova-api-base-url") : "";
  const selected = runtimeBase || configBase || DEFAULT_API_BASE;
  return String(selected).replace(/\/+$/, "");
}

export function setAuthTokenProvider(provider) {
  authTokenProvider = typeof provider === "function" ? provider : () => "";
}

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = typeof handler === "function" ? handler : null;
}

async function request(path, options = {}) {
  const { skipAuth = false, headers: optionHeaders = {}, ...fetchOptions } = options;
  const token = skipAuth ? "" : String(authTokenProvider?.() || "").trim();
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...optionHeaders,
  };
  const response = await fetch(`${configuredApiBase()}${path}`, {
    headers,
    ...fetchOptions,
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : { error: await response.text() };
  if (response.status === 401 && token && unauthorizedHandler) {
    unauthorizedHandler(payload);
  }
  if (!response.ok) {
    const error = new Error(payload.error || payload.detail || `Request failed with ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return payload;
}

export const api = {
  register({ name, email, password }) {
    return request("/auth/register", {
      skipAuth: true,
      method: "POST",
      body: JSON.stringify({ name, email, password }),
    });
  },
  login({ email, password }) {
    return request("/auth/login", {
      skipAuth: true,
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },
  resetPassword({ email, password, confirmPassword }) {
    return request("/auth/reset-password", {
      skipAuth: true,
      method: "POST",
      body: JSON.stringify({ email, password, confirmPassword }),
    });
  },
  me() {
    return request("/auth/me");
  },
  instruments(query, limit = 25) {
    const params = new URLSearchParams({ q: query, limit: String(limit) });
    return request(`/instruments?${params}`);
  },
  patterns() {
    return request("/patterns");
  },
  news(symbol, limit = 8) {
    const params = new URLSearchParams({ symbol, limit: String(limit) });
    return request(`/news?${params}`);
  },
  analyze({ symbol, range, interval, chartType }) {
    return request("/analyze", {
      method: "POST",
      body: JSON.stringify({ symbol, range, interval, chartType }),
    });
  },
  renameUnknown(id, name) {
    return request(`/patterns/unknown/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify({ name }),
    });
  },
};
