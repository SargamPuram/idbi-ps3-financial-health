import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8001";

const api = axios.create({ baseURL, timeout: 20000 });

export default api;

export const endpoints = {
  portfolio: () => api.get("/portfolio"),
  healthCard: (msmeId) => api.get(`/health-card/${msmeId}`),
  sectorBenchmark: (sector) => api.get(`/sector-benchmark/${sector}`),
  assess: (payload) => api.post("/assess", payload),
  simulate: (payload) => api.post("/simulate", payload),
  compare: (ids) => api.get(`/compare?ids=${ids.join(",")}`),
  analytics: () => api.get("/analytics"),
  exportCard: (msmeId) => api.get(`/export/${msmeId}`),
};
