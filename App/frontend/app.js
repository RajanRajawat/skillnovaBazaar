import { api, setAuthTokenProvider, setUnauthorizedHandler } from "./api.js";
import { MarketChart } from "./charts.js";

const STORAGE_KEY = "skillnova-bazaar-chart-state";
const AUTH_STORAGE_KEY = "skillnova-bazaar-auth";
const APP_ROUTE = "app";
const LOGIN_ROUTE = "login";
const FORGOT_PASSWORD_ROUTE = "forgot-password";
const REGISTER_ROUTE = "register";
const AUTH_ROUTES = new Set([APP_ROUTE, LOGIN_ROUTE, FORGOT_PASSWORD_ROUTE, REGISTER_ROUTE]);
const ALLOWED_CHART_TYPES = new Set(["candlestick", "bar", "line", "area", "heikin-ashi"]);
const ALLOWED_INTERVALS = new Set(["1d", "60m", "30m", "15m", "5m"]);
const ALLOWED_RANGES = new Set(["1mo", "3mo", "6mo", "1y", "2y"]);
const TRENDLINE_OPTIONS = [
  { id: "upper-bottoms", label: "Upper Bottoms" },
  { id: "lower-bottoms", label: "Lower Bottoms" },
  { id: "corresponding-bottoms", label: "Corresponding Bottoms" },
  { id: "higher-highs", label: "Higher Highs" },
  { id: "lower-highs", label: "Lower Highs" },
  { id: "swing-high", label: "Swing High" },
];
const DEFAULT_TRENDLINE_IDS = TRENDLINE_OPTIONS.map((item) => item.id);
const initialChartState = getInitialChartState();

const state = {
  symbol: "NIFTY50",
  chartType: "candlestick",
  interval: "1d",
  range: "6mo",
  masterPatterns: [],
  activePatterns: [],
  candles: [],
  trendlines: [],
  viewedPatternId: null,
  visibleTrendlineIds: DEFAULT_TRENDLINE_IDS,
  prediction: null,
  searchLabel: "",
  timer: null,
  newsTimer: null,
  clockTimer: null,
  loading: false,
  newsLoading: false,
  appBooted: false,
  marketEventsBound: false,
  authBusy: false,
  sessionValidated: false,
  auth: readStoredAuthState(),
  ...initialChartState,
};

const els = {
  authView: document.querySelector("#authView"),
  appView: document.querySelector("#appView"),
  authEyebrow: document.querySelector("#authEyebrow"),
  authTitle: document.querySelector("#authTitle"),
  authSubtitle: document.querySelector("#authSubtitle"),
  authMessage: document.querySelector("#authMessage"),
  loginEmail: document.querySelector("#loginEmail"),
  loginRouteLink: document.querySelector("#loginRouteLink"),
  registerRouteLink: document.querySelector("#registerRouteLink"),
  forgotPasswordLink: document.querySelector("#forgotPasswordLink"),
  loginForm: document.querySelector("#loginForm"),
  forgotPasswordForm: document.querySelector("#forgotPasswordForm"),
  registerForm: document.querySelector("#registerForm"),
  backToLoginLink: document.querySelector("#backToLoginLink"),
  loginSubmitButton: document.querySelector("#loginSubmitButton"),
  forgotPasswordSubmitButton: document.querySelector("#forgotPasswordSubmitButton"),
  registerSubmitButton: document.querySelector("#registerSubmitButton"),
  logoutButton: document.querySelector("#logoutButton"),
  sessionUserName: document.querySelector("#sessionUserName"),
  sessionUserEmail: document.querySelector("#sessionUserEmail"),
  search: document.querySelector("#instrumentSearch"),
  results: document.querySelector("#searchResults"),
  instrumentName: document.querySelector("#instrumentName"),
  lastPrice: document.querySelector("#lastPrice"),
  priceChange: document.querySelector("#priceChange"),
  predictionText: document.querySelector("#predictionText"),
  predictionBlock: document.querySelector("#predictionBlock"),
  patternRail: document.querySelector("#patternRail"),
  activePatterns: document.querySelector("#activePatterns"),
  drivers: document.querySelector("#predictionDrivers"),
  newsList: document.querySelector("#newsList"),
  providerBadge: document.querySelector("#providerBadge"),
  updatedAt: document.querySelector("#updatedAt"),
  interval: document.querySelector("#intervalSelect"),
  range: document.querySelector("#rangeSelect"),
  chartControls: document.querySelector("#chartTypeControls"),
  trendlineFilter: document.querySelector("#trendlineFilter"),
  trendlineMenuButton: document.querySelector("#trendlineMenuButton"),
  trendlineMenu: document.querySelector("#trendlineMenu"),
};

const chart = new MarketChart(document.querySelector("#chart"));

setAuthTokenProvider(() => state.auth.token);
setUnauthorizedHandler(() => {
  if (!state.auth.token) return;
  clearAuthSession();
  stopBackgroundTimers();
  state.appBooted = false;
  state.sessionValidated = false;
  showAuthMessage("Your session expired. Please log in again.", "error");
  navigateTo(LOGIN_ROUTE, { replace: true });
});

bindGlobalEvents();
void syncRoute();
window.addEventListener("hashchange", () => {
  void syncRoute();
});

function getInitialChartState() {
  const saved = readStoredChartState();
  const params = new URLSearchParams(window.location.search);
  const restored = { ...saved };
  if (params.has("symbol")) restored.symbol = params.get("symbol");
  if (params.has("chartType")) restored.chartType = params.get("chartType");
  if (params.has("interval")) restored.interval = params.get("interval");
  if (params.has("range")) restored.range = params.get("range");
  if (params.has("pattern")) restored.viewedPatternId = params.get("pattern");
  if (params.has("levels")) restored.visibleTrendlineIds = params.get("levels").split(",");

  return {
    symbol: cleanSymbol(restored.symbol) || "NIFTY50",
    chartType: ALLOWED_CHART_TYPES.has(restored.chartType) ? restored.chartType : "candlestick",
    interval: ALLOWED_INTERVALS.has(restored.interval) ? restored.interval : "1d",
    range: ALLOWED_RANGES.has(restored.range) ? restored.range : "6mo",
    viewedPatternId: restored.viewedPatternId || null,
    visibleTrendlineIds: normalizeTrendlineIds(restored.visibleTrendlineIds),
    searchLabel: restored.searchLabel || "",
  };
}

function readStoredChartState() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch (_error) {
    return {};
  }
}

function persistChartState(instrument = null) {
  const payload = {
    symbol: state.symbol,
    chartType: state.chartType,
    interval: state.interval,
    range: state.range,
    viewedPatternId: state.viewedPatternId,
    visibleTrendlineIds: state.visibleTrendlineIds,
    searchLabel: state.searchLabel || instrument?.displaySymbol || instrument?.symbol || state.symbol,
  };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch (_error) {
    // Storage can be unavailable in hardened browser modes; URL state still preserves refreshes.
  }

  const params = new URLSearchParams({
    symbol: payload.symbol,
    chartType: payload.chartType,
    interval: payload.interval,
    range: payload.range,
  });
  if (payload.viewedPatternId) params.set("pattern", payload.viewedPatternId);
  params.set("levels", payload.visibleTrendlineIds.join(","));
  const hash = window.location.hash || "#/app";
  window.history.replaceState(null, "", `${window.location.pathname}?${params}${hash}`);
}

function readStoredAuthState() {
  try {
    const payload = JSON.parse(localStorage.getItem(AUTH_STORAGE_KEY) || "{}");
    return {
      token: typeof payload.token === "string" ? payload.token : "",
      user: payload.user && typeof payload.user === "object" ? payload.user : null,
    };
  } catch (_error) {
    return { token: "", user: null };
  }
}

function persistAuthState() {
  try {
    if (!state.auth.token) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      return;
    }
    localStorage.setItem(
      AUTH_STORAGE_KEY,
      JSON.stringify({
        token: state.auth.token,
        user: state.auth.user,
      })
    );
  } catch (_error) {
    // Ignore unavailable storage and continue with the in-memory session.
  }
}

function applyAuthPayload(payload) {
  state.auth = {
    token: String(payload?.token || ""),
    user: payload?.user || null,
  };
  state.sessionValidated = Boolean(state.auth.token);
  persistAuthState();
  renderSessionUser();
}

function clearAuthSession() {
  state.auth = { token: "", user: null };
  persistAuthState();
  renderSessionUser();
}

function normalizeRoute(value) {
  const clean = String(value || "")
    .replace(/^#\/?/, "")
    .trim()
    .toLowerCase();
  return AUTH_ROUTES.has(clean) ? clean : APP_ROUTE;
}

function currentRoute() {
  return normalizeRoute(window.location.hash);
}

function routeUrl(route) {
  return `${window.location.pathname}${window.location.search}#/${route}`;
}

function navigateTo(route, options = {}) {
  const targetRoute = normalizeRoute(route);
  const nextUrl = routeUrl(targetRoute);
  const method = options.replace ? "replaceState" : "pushState";
  if (window.location.href.endsWith(nextUrl)) {
    void syncRoute();
    return;
  }
  window.history[method](null, "", nextUrl);
  void syncRoute();
}

async function syncRoute() {
  const route = currentRoute();
  if (!state.auth.token) {
    stopBackgroundTimers();
    state.appBooted = false;
    if (route === APP_ROUTE) {
      showAuthView(LOGIN_ROUTE);
      window.history.replaceState(null, "", routeUrl(LOGIN_ROUTE));
      return;
    }
    showAuthView(route);
    return;
  }

  if (route !== APP_ROUTE) {
    window.history.replaceState(null, "", routeUrl(APP_ROUTE));
  }

  const sessionReady = await ensureSession();
  if (!sessionReady) {
    return;
  }

  showAppView();
  await bootDashboard();
}

async function ensureSession() {
  if (!state.auth.token) {
    return false;
  }
  if (state.sessionValidated && state.auth.user) {
    return true;
  }
  try {
    const payload = await api.me();
    state.auth.user = payload.user || null;
    state.sessionValidated = true;
    persistAuthState();
    renderSessionUser();
    return true;
  } catch (error) {
    if (error.status !== 401) {
      clearAuthSession();
      showAuthMessage(error.message, "error");
      navigateTo(LOGIN_ROUTE, { replace: true });
    }
    return false;
  }
}

function showAuthView(route) {
  const isRegister = route === REGISTER_ROUTE;
  const isForgotPassword = route === FORGOT_PASSWORD_ROUTE;
  els.authView.hidden = false;
  els.appView.hidden = true;
  els.loginForm.hidden = isRegister || isForgotPassword;
  els.forgotPasswordForm.hidden = !isForgotPassword;
  els.registerForm.hidden = !isRegister;
  els.loginRouteLink.classList.toggle("active", !isRegister);
  els.registerRouteLink.classList.toggle("active", isRegister);
  if (isRegister) {
    els.authEyebrow.textContent = "Create your account";
    els.authTitle.textContent = "Register for protected access";
    els.authSubtitle.textContent = "Create an account to unlock the analysis terminal and secured API routes.";
    return;
  }
  if (isForgotPassword) {
    els.authEyebrow.textContent = "Recover your access";
    els.authTitle.textContent = "Reset your password";
    els.authSubtitle.textContent = "Enter your account email and choose a new password to regain access.";
    return;
  }
  els.authEyebrow.textContent = "Welcome back";
  els.authTitle.textContent = "Login to continue";
  els.authSubtitle.textContent = "Use your account to access the protected market dashboard.";
}

function showAppView() {
  els.authView.hidden = true;
  els.appView.hidden = false;
  renderSessionUser();
}

function renderSessionUser() {
  const user = state.auth.user || {};
  els.sessionUserName.textContent = user.name || "Guest";
  els.sessionUserEmail.textContent = user.email || "No active session";
}

function showAuthMessage(message, type = "error") {
  if (!message) {
    els.authMessage.hidden = true;
    els.authMessage.textContent = "";
    els.authMessage.className = "auth-message";
    return;
  }
  els.authMessage.hidden = false;
  els.authMessage.textContent = message;
  els.authMessage.className = `auth-message ${type}`;
}

function setAuthBusy(nextBusy) {
  state.authBusy = nextBusy;
  els.loginSubmitButton.disabled = nextBusy;
  els.forgotPasswordSubmitButton.disabled = nextBusy;
  els.registerSubmitButton.disabled = nextBusy;
}

function bindGlobalEvents() {
  els.loginRouteLink.addEventListener("click", () => showAuthMessage(""));
  els.registerRouteLink.addEventListener("click", () => showAuthMessage(""));
  els.forgotPasswordLink.addEventListener("click", () => showAuthMessage(""));
  els.backToLoginLink.addEventListener("click", () => showAuthMessage(""));

  els.loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.authBusy) return;
    showAuthMessage("");
    setAuthBusy(true);
    const form = new FormData(els.loginForm);
    try {
      const payload = await api.login({
        email: String(form.get("email") || ""),
        password: String(form.get("password") || ""),
      });
      applyAuthPayload(payload);
      els.loginForm.reset();
      navigateTo(APP_ROUTE, { replace: true });
    } catch (error) {
      showAuthMessage(error.message, "error");
    } finally {
      setAuthBusy(false);
    }
  });

  els.forgotPasswordForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.authBusy) return;
    showAuthMessage("");
    const form = new FormData(els.forgotPasswordForm);
    const email = String(form.get("email") || "");
    const password = String(form.get("password") || "");
    const confirmPassword = String(form.get("confirmPassword") || "");
    if (password !== confirmPassword) {
      showAuthMessage("Passwords do not match", "error");
      return;
    }
    setAuthBusy(true);
    try {
      await api.resetPassword({ email, password, confirmPassword });
      els.forgotPasswordForm.reset();
      els.loginEmail.value = email;
      navigateTo(LOGIN_ROUTE, { replace: true });
      showAuthMessage("Password reset successful. Please log in with your new password.", "success");
    } catch (error) {
      showAuthMessage(error.message, "error");
    } finally {
      setAuthBusy(false);
    }
  });

  els.registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.authBusy) return;
    showAuthMessage("");
    setAuthBusy(true);
    const form = new FormData(els.registerForm);
    try {
      const payload = await api.register({
        name: String(form.get("name") || ""),
        email: String(form.get("email") || ""),
        password: String(form.get("password") || ""),
      });
      applyAuthPayload(payload);
      els.registerForm.reset();
      navigateTo(APP_ROUTE, { replace: true });
    } catch (error) {
      showAuthMessage(error.message, "error");
    } finally {
      setAuthBusy(false);
    }
  });

  els.logoutButton.addEventListener("click", () => {
    clearAuthSession();
    stopBackgroundTimers();
    state.appBooted = false;
    state.sessionValidated = false;
    showAuthMessage("You have been logged out.", "success");
    navigateTo(LOGIN_ROUTE, { replace: true });
  });
}

function bindMarketEvents() {
  if (state.marketEventsBound) {
    return;
  }
  state.marketEventsBound = true;

  els.search.addEventListener("input", debounce(handleSearch));
  els.search.addEventListener("focus", () => {
    if (els.search.value.trim()) handleSearch();
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".search-wrap")) {
      els.results.hidden = true;
    }
    if (!event.target.closest(".trendline-filter")) {
      els.trendlineMenu.hidden = true;
      els.trendlineMenuButton.setAttribute("aria-expanded", "false");
    }
  });

  els.trendlineMenuButton.addEventListener("click", () => {
    const nextHidden = !els.trendlineMenu.hidden;
    els.trendlineMenu.hidden = nextHidden;
    els.trendlineMenuButton.setAttribute("aria-expanded", String(!nextHidden));
  });

  els.trendlineMenu.addEventListener("change", (event) => {
    const input = event.target.closest("input[type='checkbox'][data-trendline-id]");
    if (!input) return;
    state.visibleTrendlineIds = [...els.trendlineMenu.querySelectorAll("input[data-trendline-id]:checked")].map(
      (item) => item.dataset.trendlineId
    );
    persistChartState();
    renderTrendlineFilterButton();
    renderCurrentChart();
  });

  els.chartControls.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-chart-type]");
    if (!button) return;
    state.chartType = button.dataset.chartType;
    resetRemovedPatterns();
    els.chartControls.querySelectorAll("button").forEach((item) => item.classList.toggle("active", item === button));
    persistChartState();
    void loadAnalysis();
  });

  els.interval.addEventListener("change", () => {
    state.interval = els.interval.value;
    resetRemovedPatterns();
    persistChartState();
    void loadAnalysis();
  });

  els.range.addEventListener("change", () => {
    state.range = els.range.value;
    resetRemovedPatterns();
    persistChartState();
    void loadAnalysis();
  });
}

async function bootDashboard() {
  bindMarketEvents();
  applyStateToControls();
  renderClock();
  renderSessionUser();

  if (state.appBooted) {
    startBackgroundTimers();
    return;
  }

  state.appBooted = true;
  try {
    const patterns = await api.patterns();
    state.masterPatterns = patterns.patterns || [];
    renderPatternRail();
    await loadAnalysis();
    persistChartState();
    startBackgroundTimers();
  } catch (error) {
    state.appBooted = false;
    if (error.status === 401) return;
    els.activePatterns.innerHTML = `<div class="pattern-card"><strong>Startup failed</strong><p>${escapeHtml(error.message)}</p></div>`;
  }
}

function startBackgroundTimers() {
  if (!state.timer) {
    state.timer = setInterval(() => {
      void loadAnalysis({ quiet: true });
    }, 15000);
  }
  if (!state.newsTimer) {
    state.newsTimer = setInterval(() => {
      void refreshNews({ quiet: true });
    }, 15000);
  }
  if (!state.clockTimer) {
    state.clockTimer = setInterval(renderClock, 1000);
  }
}

function stopBackgroundTimers() {
  clearInterval(state.timer);
  clearInterval(state.newsTimer);
  clearInterval(state.clockTimer);
  state.timer = null;
  state.newsTimer = null;
  state.clockTimer = null;
  document.body.classList.remove("loading");
}

function cleanSymbol(value) {
  return String(value || "").trim().slice(0, 80);
}

function normalizeTrendlineIds(value) {
  const allowed = new Set(DEFAULT_TRENDLINE_IDS);
  if (!Array.isArray(value)) return [...DEFAULT_TRENDLINE_IDS];
  return value.filter((item) => allowed.has(item));
}

function applyStateToControls() {
  els.interval.value = state.interval;
  els.range.value = state.range;
  if (state.searchLabel) els.search.value = state.searchLabel;
  els.chartControls.querySelectorAll("button").forEach((button) => {
    button.classList.toggle("active", button.dataset.chartType === state.chartType);
  });
  renderTrendlineFilter();
}

function resetRemovedPatterns() {
  state.viewedPatternId = null;
}

function debounce(fn, wait = 220) {
  let timeout = null;
  return (...args) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => fn(...args), wait);
  };
}

async function handleSearch() {
  const query = els.search.value.trim();
  if (!query) {
    els.results.hidden = true;
    return;
  }
  try {
    const payload = await api.instruments(query, 35);
    renderSearchResults(payload.results);
  } catch (error) {
    if (error.status === 401) return;
    els.results.innerHTML = `<div class="search-item">Search unavailable<small>${escapeHtml(error.message)}</small></div>`;
    els.results.hidden = false;
  }
}

function renderSearchResults(results) {
  els.results.innerHTML = results
    .map(
      (item) => `
        <button class="search-item" data-symbol="${escapeHtml(item.symbol)}">
          <span>
            <strong>${escapeHtml(item.displaySymbol || item.symbol)}</strong>
            <small>${escapeHtml(item.name)} | ${escapeHtml(item.exchange)} | ${escapeHtml(item.segment)}</small>
          </span>
          <span class="tag">${escapeHtml(item.type)}</span>
        </button>
      `
    )
    .join("");
  els.results.querySelectorAll(".search-item").forEach((button) => {
    button.addEventListener("click", () => {
      state.symbol = button.dataset.symbol;
      resetRemovedPatterns();
      state.searchLabel = button.querySelector("strong").textContent;
      els.search.value = state.searchLabel;
      els.results.hidden = true;
      persistChartState();
      void loadAnalysis();
    });
  });
  els.results.hidden = results.length === 0;
}

async function loadAnalysis(options = {}) {
  if (state.loading) return;
  state.loading = true;
  if (!options.quiet) document.body.classList.add("loading");
  try {
    const payload = await api.analyze({
      symbol: state.symbol,
      range: state.range,
      interval: state.interval,
      chartType: state.chartType,
    });
    const visiblePatterns = filterRemovedPatterns(payload.patterns);
    state.masterPatterns = payload.masterPatterns;
    state.activePatterns = visiblePatterns;
    state.candles = payload.candles;
    state.trendlines = payload.trendlines || [];
    state.prediction = payload.prediction;
    chart.render(payload.candles, state.chartType, visibleTrendlines());
    syncViewedPatternOverlay();
    renderHeader(payload);
    renderPatternRail();
    renderActivePatterns(visiblePatterns);
    renderPrediction(payload.prediction);
    renderNews(payload.news);
    persistChartState(payload.instrument);
    els.providerBadge.textContent = payload.newsProvider || "News";
  } catch (error) {
    if (error.status === 401) return;
    els.activePatterns.innerHTML = `<div class="pattern-card"><strong>Analysis unavailable</strong><p>${escapeHtml(error.message)}</p></div>`;
  } finally {
    state.loading = false;
    document.body.classList.remove("loading");
  }
}

function renderHeader(payload) {
  const instrument = payload.instrument;
  els.instrumentName.textContent = `${instrument.displaySymbol || instrument.symbol} - ${instrument.exchange}`;
  els.lastPrice.textContent = formatNumber(payload.quote.price);
  els.priceChange.textContent = `${formatNumber(payload.quote.change)} (${formatNumber(payload.quote.changePercent)}%)`;
  state.searchLabel = instrument.displaySymbol || instrument.symbol;
  if (document.activeElement !== els.search && els.results.hidden) {
    els.search.value = state.searchLabel;
  }
}

function renderClock() {
  els.updatedAt.textContent = new Date().toLocaleTimeString();
}

function renderPrediction(prediction) {
  if (!prediction) return;
  const shortTerm = prediction.shortTerm || prediction;
  const longTerm = prediction.longTerm || null;
  els.predictionText.textContent = longTerm
    ? `Short ${shortTerm.direction} ${shortTerm.confidence}% | Long ${longTerm.direction} ${longTerm.confidence}%`
    : `${shortTerm.direction} ${shortTerm.confidence}%`;
  els.predictionBlock.style.borderColor = "var(--blue)";

  const horizons = [shortTerm, longTerm].filter(Boolean);
  const horizonCards = horizons
    .map(
      (item) => `
        <div class="driver-item prediction-horizon">
          <strong>${escapeHtml(item.label || "Prediction")}</strong>
          <span>${escapeHtml(item.direction)} ${escapeHtml(item.confidence)}% | ${formatRange(item.range)}</span>
        </div>
      `
    )
    .join("");
  const drivers = (prediction.drivers || [])
    .map((driver) => `<div class="driver-item">${escapeHtml(driver)}</div>`)
    .join("");
  els.drivers.innerHTML = horizonCards + drivers;
}

function renderTrendlineFilter() {
  const selected = new Set(state.visibleTrendlineIds);
  els.trendlineMenu.innerHTML = TRENDLINE_OPTIONS.map(
    (item) => `
      <label class="trendline-option">
        <input type="checkbox" data-trendline-id="${escapeHtml(item.id)}" ${selected.has(item.id) ? "checked" : ""} />
        <span class="trendline-check" aria-hidden="true"></span>
        <span class="trendline-label">${escapeHtml(item.label)}</span>
      </label>
    `
  ).join("");
  renderTrendlineFilterButton();
}

function renderTrendlineFilterButton() {
  const count = state.visibleTrendlineIds.length;
  const value = count === TRENDLINE_OPTIONS.length ? "All" : String(count);
  els.trendlineMenuButton.querySelector(".level-trigger-count").textContent = value;
}

function visibleTrendlines() {
  const visibleIds = new Set(state.visibleTrendlineIds);
  return state.trendlines.filter((line) => visibleIds.has(line.id));
}

function renderCurrentChart() {
  if (!state.candles.length) return;
  chart.render(state.candles, state.chartType, visibleTrendlines());
  syncViewedPatternOverlay();
}

function filterRemovedPatterns(patterns) {
  return Array.isArray(patterns) ? patterns : [];
}

function renderPatternRail() {
  if (!els.patternRail) {
    return;
  }
  const activeIds = new Set(state.activePatterns.map((pattern) => pattern.id));
  const visiblePatterns = prioritizedPatterns();
  els.patternRail.innerHTML = visiblePatterns
    .map((pattern) => {
      const classes = ["pattern-pill"];
      if (activeIds.has(pattern.id)) classes.push("active");
      if (state.viewedPatternId === pattern.id) classes.push("viewing");
      if (pattern.isUnknown || pattern.category === "Unknown") classes.push("unknown");
      return `<button class="${classes.join(" ")}" data-pattern-id="${escapeHtml(pattern.id)}">${escapeHtml(pattern.name)}</button>`;
    })
    .join("");
  els.patternRail.querySelectorAll(".pattern-pill").forEach((button) => {
    const pattern = visiblePatterns.find((item) => item.id === button.dataset.patternId);
    if (pattern && (pattern.isUnknown || pattern.category === "Unknown")) {
      button.addEventListener("click", () => beginRename(button, pattern));
    }
  });
}

function renderActivePatterns(patterns) {
  if (!patterns.length) {
    state.viewedPatternId = null;
    chart.clearPattern();
    els.activePatterns.innerHTML = `<div class="pattern-card"><strong>No active formation</strong><p>Signals are mixed across the current range.</p></div>`;
    return;
  }
  const sortedPatterns = [...patterns].sort((a, b) => patternValidPercent(b) - patternValidPercent(a));
  els.activePatterns.innerHTML = sortedPatterns
    .map(
      (pattern) => `
        <article class="pattern-card ${state.viewedPatternId === pattern.id ? "viewing" : ""}">
          <div class="pattern-title-row">
            <button class="pattern-title ${pattern.isUnknown ? "unknown-title" : ""}" data-pattern-id="${escapeHtml(pattern.id)}">
              ${escapeHtml(pattern.name)}
            </button>
            <div class="pattern-actions">
              <span class="confidence">${patternValidPercent(pattern)}%</span>
              <button class="pattern-view-button" data-view-pattern-id="${escapeHtml(pattern.id)}">View</button>
              <button class="pattern-remove-button" data-remove-pattern-id="${escapeHtml(pattern.id)}" aria-label="Remove ${escapeHtml(pattern.name)}">Remove</button>
            </div>
          </div>
          <p>${escapeHtml(pattern.reason)}</p>
          <div class="pattern-meta">
            <span>${escapeHtml(pattern.bias)}</span>
            <span>${escapeHtml(pattern.status)}</span>
            <span>${escapeHtml(pattern.category)}</span>
          </div>
        </article>
      `
    )
    .join("");

  els.activePatterns.querySelectorAll(".pattern-title").forEach((button) => {
    const pattern = sortedPatterns.find((item) => item.id === button.dataset.patternId);
    if (pattern?.isUnknown) {
      button.addEventListener("click", () => beginRename(button, pattern));
    }
  });
  els.activePatterns.querySelectorAll(".pattern-view-button").forEach((button) => {
    const pattern = sortedPatterns.find((item) => item.id === button.dataset.viewPatternId);
    if (pattern) {
      button.addEventListener("click", () => viewPattern(pattern));
    }
  });
  els.activePatterns.querySelectorAll(".pattern-remove-button").forEach((button) => {
    const pattern = sortedPatterns.find((item) => item.id === button.dataset.removePatternId);
    if (pattern) {
      button.addEventListener("click", () => removePattern(pattern));
    }
  });
}

function prioritizedPatterns() {
  const masterById = new Map(state.masterPatterns.map((pattern) => [pattern.id, pattern]));
  const seen = new Set();
  const activeFirst = [...state.activePatterns]
    .sort((a, b) => patternValidPercent(b) - patternValidPercent(a))
    .map((pattern) => {
      seen.add(pattern.id);
      return { ...(masterById.get(pattern.id) || {}), ...pattern };
    });
  const inactive = state.masterPatterns.filter((pattern) => !seen.has(pattern.id));
  return [...activeFirst, ...inactive];
}

function viewPattern(pattern) {
  state.viewedPatternId = pattern.id;
  chart.showPattern(pattern, state.prediction);
  renderPrediction(state.prediction);
  persistChartState();
  renderPatternRail();
  renderActivePatterns(state.activePatterns);
}

function removePattern(pattern) {
  void pattern;
  state.viewedPatternId = null;
  chart.clearPattern();
  persistChartState();
  renderPatternRail();
  renderActivePatterns(state.activePatterns);
}

function syncViewedPatternOverlay() {
  const pattern = state.activePatterns.find((item) => item.id === state.viewedPatternId);
  if (pattern) {
    chart.showPattern(pattern, state.prediction);
    return;
  }
  state.viewedPatternId = null;
  chart.clearPattern();
  persistChartState();
}

function patternValidPercent(pattern) {
  return Number.isFinite(Number(pattern.validPercent))
    ? Math.round(Number(pattern.validPercent))
    : Math.round((pattern.confidence || 0) * 100);
}

function renderNews(news) {
  if (!news.length) {
    els.newsList.innerHTML = `<article class="news-item news-empty"><span>No fresh headlines returned for this instrument.</span></article>`;
    return;
  }
  els.newsList.innerHTML = news
    .map(
      (item) => `
        <article class="news-item">
          <div class="news-content">
            <a href="${escapeAttribute(item.url || "#")}" target="_blank" rel="noreferrer">${escapeHtml(item.title)}</a>
            <div class="news-meta">
              <span>${escapeHtml(item.source || "News")}</span>
              <span>${escapeHtml(item.sentiment)}</span>
            </div>
          </div>
          <time class="news-time" datetime="${escapeHtml(item.publishedAt || "")}">${formatNewsTimestamp(item.publishedAt)}</time>
        </article>
      `
    )
    .join("");
}

async function refreshNews() {
  if (state.newsLoading) return;
  state.newsLoading = true;
  try {
    const payload = await api.news(state.symbol, 8);
    renderNews(payload.news || []);
    els.providerBadge.textContent = payload.newsProvider || "News";
  } catch (error) {
    if (error.status !== 401) {
      // The chart analysis loop will surface broader connectivity failures.
    }
  } finally {
    state.newsLoading = false;
  }
}

function beginRename(anchor, pattern) {
  const input = document.createElement("input");
  input.className = "rename-input";
  input.value = pattern.name;
  input.setAttribute("aria-label", `Rename ${pattern.name}`);
  anchor.replaceWith(input);
  input.focus();
  input.select();

  const finish = async (save) => {
    if (!save) {
      await loadAnalysis({ quiet: true });
      return;
    }
    const name = input.value.trim();
    if (!name || name === pattern.name) {
      await loadAnalysis({ quiet: true });
      return;
    }
    try {
      await api.renameUnknown(pattern.id, name);
      await loadAnalysis({ quiet: true });
    } catch (error) {
      if (error.status === 401) return;
      input.value = error.message;
      setTimeout(() => {
        void loadAnalysis({ quiet: true });
      }, 900);
    }
  };

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") void finish(true);
    if (event.key === "Escape") void finish(false);
  });
  input.addEventListener(
    "blur",
    () => {
      void finish(true);
    },
    { once: true }
  );
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatRange(range) {
  if (!range) return "Range unavailable";
  const lower = Number(range.lower);
  const upper = Number(range.upper);
  if (!Number.isFinite(lower) || !Number.isFinite(upper)) return "Range unavailable";
  return `${formatNumber(lower)} to ${formatNumber(upper)}`;
}

function formatNewsTimestamp(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttribute(value) {
  const text = String(value || "#");
  return text.startsWith("http") ? escapeHtml(text) : "#";
}
