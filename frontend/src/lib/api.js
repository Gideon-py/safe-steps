import axios from "axios";

const BACKEND = process.env.REACT_APP_BACKEND_URL;
const BASE = `${BACKEND}/api`;

function authHeader(token) {
  return { Authorization: `Bearer ${token}` };
}

const api = {
  // Auth
  register: async (name, email, password) => {
    const { data } = await axios.post(`${BASE}/auth/register`, { name, email, password });
    return data;
  },
  login: async (email, password) => {
    const { data } = await axios.post(`${BASE}/auth/login`, { email, password });
    return data;
  },
  getMe: async (token) => {
    const { data } = await axios.get(`${BASE}/auth/me`, { headers: authHeader(token) });
    return data;
  },

  // Schools
  getSchools: async () => {
    const { data } = await axios.get(`${BASE}/schools`);
    return data;
  },

  // Environment
  getEnvironment: async () => {
    const { data } = await axios.get(`${BASE}/environment/status`);
    return data;
  },

  // Routes – NEW ORS-based endpoints
  getAlternatives: async (startLat, startLng, destLat, destLng) => {
    const { data } = await axios.post(`${BASE}/route/alternatives`, {
      start: { lat: startLat, lng: startLng },
      dest: { lat: destLat, lng: destLng },
    });
    return data;
  },

  getSafestRoute: async (startLat, startLng, destLat, destLng) => {
    const { data } = await axios.post(`${BASE}/route/safest`, {
      start: { lat: startLat, lng: startLng },
      dest: { lat: destLat, lng: destLng },
    });
    return data;
  },

  // Legacy endpoint (school_id based)
  calculateRoutes: async (startLat, startLng, schoolId, departureTime) => {
    const { data } = await axios.post(`${BASE}/routes/calculate`, {
      start_lat: startLat,
      start_lng: startLng,
      school_id: schoolId,
      departure_time: departureTime,
    });
    return data;
  },

  // Saved routes
  saveRoute: async (token, routeName, routeData) => {
    const { data } = await axios.post(
      `${BASE}/routes/save`,
      { route_name: routeName, route_data: routeData },
      { headers: authHeader(token) }
    );
    return data;
  },
  getSavedRoutes: async (token) => {
    const { data } = await axios.get(`${BASE}/routes/saved`, { headers: authHeader(token) });
    return data;
  },
  deleteSavedRoute: async (token, routeId) => {
    const { data } = await axios.delete(`${BASE}/routes/saved/${routeId}`, { headers: authHeader(token) });
    return data;
  },
};

export default api;
