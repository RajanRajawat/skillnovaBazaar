const LOCAL_API_BASE = "http://127.0.0.1:8000/api";
const DEPLOYED_API_BASE = "/api";
const LOCAL_HOSTS = new Set(["127.0.0.1", "localhost"]);

window.SKILLNOVA_CONFIG = {
  apiBaseUrl: LOCAL_HOSTS.has(window.location.hostname) ? LOCAL_API_BASE : DEPLOYED_API_BASE,
};
