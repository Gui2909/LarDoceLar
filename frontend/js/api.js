const API_BASE = "";

export function getToken() {
  return localStorage.getItem("ldl_token");
}

export function setSession(token, user) {
  localStorage.setItem("ldl_token", token);
  localStorage.setItem("ldl_user", JSON.stringify(user));
}

export function getUser() {
  const raw = localStorage.getItem("ldl_user");
  return raw ? JSON.parse(raw) : null;
}

export function clearSession() {
  localStorage.removeItem("ldl_token");
  localStorage.removeItem("ldl_user");
}


export async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const token = getToken();
  if (token) headers["X-Token"] = token;

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  let data = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!response.ok) {
    const detail = data?.detail;
    const message = typeof detail === "string" ? detail : `Erro ${response.status}`;
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return data;
}

export const endpoints = {
  setup: () => api("/auth/setup"),
  login: (body) => api("/auth/login", { method: "POST", body: JSON.stringify(body) }),
  me: () => api("/auth/me"),
  createUser: (body) => api("/users", { method: "POST", body: JSON.stringify(body) }),
  listUsers: () => api("/users"),
  listProducts: (onlyActive = true) => api(`/products?only_active=${onlyActive}`),
  createProduct: (body) => api("/products", { method: "POST", body: JSON.stringify(body) }),
  updateProduct: (id, body) => api(`/products/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deactivateProduct: (id) => api(`/products/${id}/deactivate`, { method: "POST" }),
  createOrder: (body) => api("/orders", { method: "POST", body: JSON.stringify(body) }),
  listOrders: (status) => api(status ? `/orders?status=${status}` : "/orders"),
  getOrder: (id) => api(`/orders/${id}`),
  addItem: (orderId, body) =>
    api(`/orders/${orderId}/items`, { method: "POST", body: JSON.stringify(body) }),
  updateItem: (orderId, itemId, body) =>
    api(`/orders/${orderId}/items/${itemId}`, { method: "PUT", body: JSON.stringify(body) }),
  removeItem: (orderId, itemId, password) =>
    api(`/orders/${orderId}/items/${itemId}`, { method: "DELETE", body: JSON.stringify({ password }) }),
  checkout: (orderId, body) =>
    api(`/orders/${orderId}/checkout`, { method: "POST", body: JSON.stringify(body) }),
  listInvoices: () => api("/invoices"),
  payInvoice: (customerName, body) => api(`/invoices/${encodeURIComponent(customerName)}/pay`, { method: "POST", body: JSON.stringify(body) }),
  cancelOrder: (orderId, body) =>
    api(`/orders/${orderId}/cancel`, { method: "POST", body: JSON.stringify(body) }),
  deleteOrder: (orderId, password) => api(`/orders/${orderId}`, { method: "DELETE", body: JSON.stringify({ password }) }),
  deleteProduct: (productId, password) => api(`/products/${productId}`, { method: "DELETE", body: JSON.stringify({ password }) }),
  deleteUser: (userId, password) => api(`/users/${userId}`, { method: "DELETE", body: JSON.stringify({ password }) }),
  cashStatus: () => api("/cash/status"),
  openCash: (body) => api("/cash/open", { method: "POST", body: JSON.stringify(body) }),
  closeCash: (body) => api("/cash/close", { method: "POST", body: JSON.stringify(body) }),
  supplyCash: (body) => api("/cash/supply", { method: "POST", body: JSON.stringify(body) }),
  withdrawCash: (body) => api("/cash/withdrawal", { method: "POST", body: JSON.stringify(body) }),
  listCashflow: () => api("/cashflow"),
  getCashReport: () => api("/cash/report"),
  periodReport: (startDate, endDate) => api(`/reports/period?start_date=${startDate}&end_date=${endDate}`),
};

export function formatMoney(value) {
  return Number(value || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export function formatDateTime(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString("pt-BR");
}
