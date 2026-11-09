
import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 180000,
});

// --------------------------------------------------
// REQUEST INTERCEPTOR - ATTACH JWT
// --------------------------------------------------

api.interceptors.request.use(
  (config) => {
    const token = sessionStorage.getItem('resolveai_token');

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// --------------------------------------------------
// RESPONSE INTERCEPTOR - HANDLE EXPIRED SESSION
// --------------------------------------------------

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const requestUrl = error.config?.url || '';

    if (
      status === 401 &&
      !requestUrl.includes('/api/auth/login') &&
      sessionStorage.getItem('resolveai_token')
    ) {
      sessionStorage.removeItem('resolveai_token');
      sessionStorage.removeItem('resolveai_user');

      window.dispatchEvent(
        new Event('resolveai:unauthorized')
      );
    }

    return Promise.reject(error);
  }
);

// --------------------------------------------------
// TICKET API FUNCTIONS
// --------------------------------------------------

export const getTicket = (id) =>
  api.get(`/api/tickets/${id}`);

export const getTicketHistory = (id) =>
  api.get(`/api/tickets/${id}/history`);

export const getActionHistory = (id) =>
  api.get(`/api/tickets/${id}/action-history`);

export const approveResponse = (id) =>
  api.post(`/api/agents/${id}/approve`);

export const rejectResponse = (id, reason) =>
  api.post(`/api/agents/${id}/reject`, { reason });

export const editResponse = (id, customer_response) =>
  api.post(`/api/agents/${id}/edit-response`, {
    customer_response,
  });

export default api;
