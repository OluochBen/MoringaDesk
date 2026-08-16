import axios from "axios";

// ✅ Use local API by default, fallback to deployed if provided
const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:5000";

export const API_BASE_URL = API_BASE;

export function buildSocialAuthUrl(provider, options = {}) {
  if (!provider) {
    throw new Error("Provider is required to build a social auth URL");
  }

  const { redirectUrl, intent = "login", state } = options;
  const fallbackCallback =
    typeof window !== "undefined"
      ? `${window.location.origin}/auth/callback`
      : "/auth/callback";
  const callbackUrl = redirectUrl || fallbackCallback;

  const params = new URLSearchParams({
    redirect_url: callbackUrl,
    intent,
  });

  if (state) {
    params.set("state", state);
  }

  const encodedProvider = encodeURIComponent(provider);
  return `${API_BASE}/auth/oauth/${encodedProvider}?${params.toString()}`;
}

const api = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  withCredentials: true,
});

// ✅ Attach token automatically if it exists
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token && token !== "undefined" && token !== "null") {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ✅ Handle expired/invalid tokens
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if ([401, 422].includes(error?.response?.status)) {
      localStorage.removeItem("access_token");
      window.location.href = "/auth";
    }
    return Promise.reject(error);
  }
);

// ✅ Helper to store token cleanly
function storeToken(token) {
  if (token) {
    localStorage.setItem("access_token", token);
  }
}

// ---------------------- API ENDPOINTS ----------------------

// ✅ Health check
export const healthApi = {
  ping: () => api.get("/ping").then((r) => r.data),
};

export const faqApi = {
  list: ({ page = 1, per_page = 10, search, category } = {}) =>
    api
      .get("/faqs", {
        params: {
          page,
          per_page,
          search: search || undefined,
          category: category || undefined,
        },
      })
      .then((r) => r.data),

  stats: () => api.get("/faqs/stats").then((r) => r.data),

  recordView: (id) => api.post(`/faqs/${id}/view`).then((r) => r.data),

  markHelpful: (id) => api.post(`/faqs/${id}/helpful`).then((r) => r.data),
};

export const authApi = {
  register: (name, email, password, role = "student") =>
    api.post("/auth/register", { name, email, password, role }).then((r) => {
      if (r.data.access_token) storeToken(r.data.access_token);
      return r.data;
    }),

  login: (email, password) =>
    api.post("/auth/login", { email, password }).then((r) => {
      if (r.data.access_token) storeToken(r.data.access_token);
      return r.data;
    }),

  exchangeOAuthCode: (code) =>
    api.post("/auth/oauth/exchange", { code }).then((r) => {
      if (r.data.access_token) storeToken(r.data.access_token);
      return r.data;
    }),

  me: () =>
    api.get("/auth/me").then((r) => {
      return r.data.user ?? r.data;
    }),

  requestPasswordReset: (email) =>
    api.post("/auth/request-reset", { email }).then((r) => r.data),

  resetPassword: (token, password) =>
    api.post("/auth/reset-password", { token, password }).then((r) => r.data),
};

export const problemsApi = {
  list: ({ page = 1, per_page = 10, problem_type, search, sort } = {}) =>
    api
      .get("/problems", { params: { page, per_page, problem_type, search, sort } })
      .then((r) => r.data),

  get: (id) =>
    api.get(`/problems/${id}`).then((r) => r.data?.item ?? r.data),

  create: ({ title, description, problem_type, tag_ids = [] }) =>
    api
      .post("/problems", { title, description, problem_type, tag_ids })
      .then((r) => r.data?.item ?? r.data),

  update: (id, { title, description, problem_type, tag_ids = [] }) =>
    api
      .put(`/problems/${id}`, { title, description, problem_type, tag_ids })
      .then((r) => r.data?.item ?? r.data),

  delete: (id) => api.delete(`/problems/${id}`).then((r) => r.data),
};

export const solutionsApi = {
  list: (problemId, { page = 1, per_page = 10 } = {}) =>
    api
      .get(`/problems/${problemId}/solutions`, { params: { page, per_page } })
      .then((r) => r.data),

  get: (problemId, solutionId) =>
    api
      .get(`/problems/${problemId}/solutions/${solutionId}`)
      .then((r) => r.data?.item ?? r.data),

  create: (problemId, { content }) =>
    api
      .post(`/problems/${problemId}/solutions`, { content })
      .then((r) => r.data?.item ?? r.data),

  update: (problemId, solutionId, { content }) =>
    api
      .put(`/problems/${problemId}/solutions/${solutionId}`, { content })
      .then((r) => r.data?.item ?? r.data),

  delete: (problemId, solutionId) =>
    api.delete(`/problems/${problemId}/solutions/${solutionId}`).then((r) => r.data),
};

export const votesApi = {
  voteSolution: (solutionId, vote_type, problemId) => {
    const url = problemId
      ? `/problems/${problemId}/solutions/${solutionId}/vote`
      : `/solutions/${solutionId}/vote`;
    return api.post(url, { vote_type }).then((r) => r.data?.item ?? r.data);
  },

  removeVote: (solutionId, problemId) => {
    const url = problemId
      ? `/problems/${problemId}/solutions/${solutionId}/vote`
      : `/solutions/${solutionId}/vote`;
    return api.delete(url).then((r) => r.data?.item ?? r.data);
  },

  getVotes: (solutionId) =>
    api.get(`/solutions/${solutionId}/votes`).then((r) => r.data),
};

export const notificationsApi = {
  list: ({ page = 1, per_page = 10, unread_only = false } = {}) =>
    api
      .get("/notifications", { params: { page, per_page, unread_only } })
      .then((r) => r.data),

  unreadCount: () => api.get("/notifications/unread-count").then((r) => r.data),

  markRead: (id) => api.put(`/notifications/${id}/read`).then((r) => r.data),

  markAllRead: () => api.put(`/notifications/read-all`).then((r) => r.data),
};

export const tagsApi = {
  list: ({ q = "", page = 1, per_page = 20 } = {}) =>
    api.get("/tags", { params: { q, page, per_page } }).then((r) => r.data),

  create: (name) => api.post("/tags", { name }).then((r) => r.data),
};

export const profileApi = {
  get: (userId) => api.get(`/profile/${userId}`).then((r) => r.data),
};

export const adminApi = {
  dashboard: () => api.get("/admin/dashboard").then((r) => r.data),
};

export const publicApi = {
  stats: () => api.get("/stats").then((r) => r.data),
  subscribe: (email, source = "footer") =>
    api.post("/subscribe", { email, source }).then((r) => r.data),
  status: () => api.get("/status").then((r) => r.data),
};

export const blogApi = {
  list: ({ page = 1, per_page = 6, search, status } = {}) =>
    api
      .get("/blog/posts", {
        params: {
          page,
          per_page,
          search: search || undefined,
          status: status || undefined,
        },
      })
      .then((r) => r.data),

  get: (identifier, { include = "full" } = {}) =>
    api.get(`/blog/posts/${identifier}`, { params: { include } }).then((r) => r.data?.item ?? r.data),

  create: (payload) => api.post("/blog/posts", payload).then((r) => r.data),

  update: (postId, payload) => api.put(`/blog/posts/${postId}`, payload).then((r) => r.data),

  remove: (postId) => api.delete(`/blog/posts/${postId}`).then((r) => r.data),
};

export const feedbackApi = {
  submit: ({ feedback_type, title, description, priority, contact_name, contact_email }) =>
    api
      .post("/feedback", {
        feedback_type,
        title,
        description,
        priority,
        contact_name,
        contact_email,
      })
      .then((r) => r.data),

  list: ({ page = 1, per_page = 25, type, status, priority } = {}) =>
    api
      .get("/admin/feedback", {
        params: {
          page,
          per_page,
          type: type || undefined,
          status: status || undefined,
          priority: priority || undefined,
        },
      })
      .then((r) => r.data),

  update: (id, payload) => api.put(`/admin/feedback/${id}`, payload).then((r) => r.data),

  stats: () => api.get("/admin/feedback/stats").then((r) => r.data),
};

// ✅ default axios instance
export default api;
