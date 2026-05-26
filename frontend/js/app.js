import {
  endpoints,
  getToken,
  getUser,
  setSession,
  clearSession,
  formatMoney,
  formatDateTime,
} from "./api.js?v=3";

const state = {
  user: null,
  view: "pdv",
  currentOrder: null,
  cashStatus: null,
  pdvFilter: { search: "", category: "Todos" },
};

const els = {
  loginScreen: document.getElementById("login-screen"),
  appShell: document.getElementById("app-shell"),
  loginForm: document.getElementById("login-form"),
  setupForm: document.getElementById("setup-form"),
  mainNav: document.getElementById("main-nav"),
  pageTitle: document.getElementById("page-title"),
  pageContent: document.getElementById("page-content"),
  userInfo: document.getElementById("user-info"),
  cashBadge: document.getElementById("cash-badge"),
  btnLogout: document.getElementById("btn-logout"),
  toastContainer: document.getElementById("toast-container"),
};

const NAV_ITEMS = [
  { id: "dashboard", label: "🏠 Início", roles: ["admin", "cashier"] },
  { id: "pdv", label: "🛒 PDV", roles: ["admin", "cashier"] },
  { id: "orders", label: "📋 Pedidos", roles: ["admin", "cashier"] },
  { id: "products", label: "📦 Produtos", roles: ["admin"] },
  { id: "cash", label: "💰 Caixa", roles: ["admin", "cashier"] },
  { id: "invoices", label: "📄 Fiado", roles: ["admin", "cashier"] },
  { id: "reports", label: "📊 Relatórios", roles: ["admin"] },
  { id: "users", label: "👤 Usuários", roles: ["admin"] },
];

const PAYMENT_METHODS_MAP = {
  "DINHEIRO": "Dinheiro",
  "PIX": "Pix",
  "CARTAO_CREDITO": "Cartão de Crédito",
  "CARTAO_DEBITO": "Cartão de Débito",
  "BOLETO": "Boleto",
  "FIADO": "Fiado",
  "FATURADO": "Fiado",
  "MÚLTIPLO": "Múltiplo"
};
function formatPaymentMethod(method) {
  if (!method || method === "NA") return "—";
  return PAYMENT_METHODS_MAP[method] || method;
}

function toast(message, type = "info") {
  const node = document.createElement("div");
  node.className = `toast ${type === "error" ? "error" : type === "success" ? "success" : ""}`;
  node.textContent = message;
  els.toastContainer.appendChild(node);
  setTimeout(() => node.remove(), 3500);
}

async function withError(action, successMessage) {
  try {
    const result = await action();
    if (successMessage) toast(successMessage, "success");
    return result;
  } catch (error) {
    if (error.status === 401) {
      clearSession();
      showLogin();
      const msg = error.message && error.message !== "Erro 401" ? error.message : "Sessão expirada. Faça login novamente.";
      toast(msg, "error");
      return null;
    }
    toast(error.message || "Erro inesperado", "error");
    return null;
  }
}

function showLogin(needsSetup = false) {
  els.appShell.classList.add("hidden");
  els.loginScreen.classList.remove("hidden");
  els.loginForm.classList.toggle("hidden", needsSetup);
  els.setupForm.classList.toggle("hidden", !needsSetup);
}

async function showApp() {
  els.loginScreen.classList.add("hidden");
  els.appShell.classList.remove("hidden");
  state.user = getUser();
  els.userInfo.textContent = `${state.user.name} (${state.user.role})`;

  await refreshCashBadge();
  if (state.cashStatus && !state.cashStatus.open) {
    state.view = "cash";
    toast("Você precisa abrir o turno antes de usar o sistema.", "warning");
  }

  navigate(state.view || "dashboard");
}

function renderNav() {
  const role = state.user.role.toLowerCase();
  els.mainNav.innerHTML = NAV_ITEMS.filter((item) => item.roles.includes(role))
    .map(
      (item) =>
        `<button type="button" class="nav-btn ${state.view === item.id ? "active" : ""}" data-view="${item.id}">${item.label}</button>`
    )
    .join("");

  els.mainNav.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => navigate(btn.dataset.view));
  });
}

async function refreshCashBadge() {
  const data = await withError(() => endpoints.cashStatus());
  if (!data) return;
  state.cashStatus = data;
  els.cashBadge.classList.remove("hidden", "open", "closed");
  if (data.open) {
    els.cashBadge.classList.add("open");
    els.cashBadge.textContent = `Caixa aberto · ${formatMoney(data.session.expected_amount)}`;
  } else {
    els.cashBadge.classList.add("closed");
    els.cashBadge.textContent = "Caixa fechado";
  }
}

function navigate(view) {
  if (view !== "cash" && view !== "dashboard" && state.cashStatus && !state.cashStatus.open) {
    toast("Abertura de turno obrigatória. Abra o caixa primeiro.", "error");
    view = "cash";
  }
  state.view = view;
  renderNav();
  const titles = {
    dashboard: "Início",
    pdv: "Ponto de Venda",
    orders: "Pedidos",
    products: "Produtos",
    stock: "Estoque",
    cash: "Caixa",
    invoices: "Fiado",
    reports: "Relatórios",
    users: "Usuários",
  };
  els.pageTitle.textContent = titles[view] || "LarDoceLar";
  const renderers = {
    dashboard: renderDashboard,
    pdv: renderPdv,
    orders: renderOrders,
    products: renderProducts,
    cash: renderCash,
    invoices: renderInvoices,
    reports: renderReports,
    users: renderUsers,
  };
  renderers[view]?.();
}

// ─── DASHBOARD ───────────────────────────────────────────────────────────────
async function renderDashboard() {
  els.pageContent.innerHTML = `<div class="empty-state">Carregando...</div>`;
  const data = await withError(() => endpoints.dashboard());
  if (!data) return;

  els.pageContent.innerHTML = `
    <div class="dashboard-grid">
      <div class="dash-card dash-card--primary">
        <div class="dash-card__icon">💰</div>
        <div class="dash-card__label">Vendas Hoje</div>
        <div class="dash-card__value">${formatMoney(data.total_today)}</div>
      </div>
      <div class="dash-card dash-card--success">
        <div class="dash-card__icon">✅</div>
        <div class="dash-card__label">Pedidos Fechados</div>
        <div class="dash-card__value">${data.orders_closed_today}</div>
      </div>
      <div class="dash-card dash-card--warning" id="dash-open-orders" style="cursor: pointer; transition: all 0.2s ease;" onmouseover="this.style.transform='translateY(-3px)'; this.style.boxShadow='0 6px 16px rgba(0,0,0,0.1)';" onmouseout="this.style.transform='none'; this.style.boxShadow='none';">
        <div class="dash-card__icon">🔓</div>
        <div class="dash-card__label">Pedidos Abertos</div>
        <div class="dash-card__value">${data.orders_open_now}</div>
      </div>
      <div class="dash-card dash-card--danger" id="dash-fiado-pendente" style="cursor: pointer; transition: all 0.2s ease;" onmouseover="this.style.transform='translateY(-3px)'; this.style.boxShadow='0 6px 16px rgba(0,0,0,0.1)';" onmouseout="this.style.transform='none'; this.style.boxShadow='none';">
        <div class="dash-card__icon">📄</div>
        <div class="dash-card__label">Fiado Pendente</div>
        <div class="dash-card__value">${formatMoney(data.total_fiado_pendente)}</div>
      </div>
    </div>
    <div class="dash-status card" style="margin-top:20px;">
      <div style="display:flex;align-items:center;gap:12px;">
        <span style="font-size:2rem;">${data.cash_open ? "🟢" : "🔴"}</span>
        <div>
          <strong>Status do Caixa</strong>
          <p style="margin:4px 0 0;color:var(--text-muted);">
            ${data.cash_open
              ? `Caixa aberto · Saldo estimado: <strong>${formatMoney(data.cash_balance)}</strong>`
              : "Caixa fechado. Vá em <strong>Caixa</strong> para abrir o turno."}
          </p>
        </div>
      </div>
    </div>
    <div style="margin-top:20px; text-align:right;">
      <button class="btn btn-secondary btn-sm" id="btn-dash-refresh">🔄 Atualizar</button>
    </div>
  `;
  document.getElementById("btn-dash-refresh")?.addEventListener("click", renderDashboard);
  document.getElementById("dash-open-orders")?.addEventListener("click", () => navigate("orders"));
  document.getElementById("dash-fiado-pendente")?.addEventListener("click", () => navigate("invoices"));
}

// ─── PDV ─────────────────────────────────────────────────────────────────────
async function renderPdv() {
  els.pageContent.innerHTML = `<div class="empty-state">Carregando PDV...</div>`;
  const [products, cash] = await Promise.all([
    withError(() => endpoints.listProducts(true)),
    withError(() => endpoints.cashStatus()),
  ]);
  if (!products) return;

  if (!state.currentOrder) {
    els.pageContent.innerHTML = `
      <div class="empty-state" style="margin-top: 40px;">
        <span style="font-size: 3rem; margin-bottom: 16px; display: block;">🧾</span>
        <h2>Nenhuma comanda aberta</h2>
        <p>Para começar a registrar produtos, abra uma nova comanda identificando o cliente.</p>
        <button type="button" class="btn btn-primary" id="btn-open-comanda" style="margin-top: 16px;">Abrir nova comanda</button>
      </div>
    `;
    document.getElementById("btn-open-comanda").addEventListener("click", async () => {
      const customerName = await promptCustomerName();
      if (!customerName || customerName.length < 2) {
        if (customerName !== null) toast("Nome do cliente inválido ou não informado", "error");
        return;
      }
      state.currentOrder = await withError(() => endpoints.createOrder({ customer_name: customerName }));
      if (state.currentOrder) renderPdv();
    });
    return;
  }

  const order = await withError(() => endpoints.getOrder(state.currentOrder.id));
  if (!order) {
    state.currentOrder = null;
    renderPdv();
    return;
  }

  const cashAlert = !cash?.open
    ? `<div class="alert warning">Caixa fechado. Abra o caixa (menu Caixa) antes de finalizar vendas.</div>`
    : "";

  // Build unique categories list
  const categories = ["Todos", ...new Set(products.map(p => p.category || "Sem categoria").sort())];

  // Filter products
  const search = state.pdvFilter.search.toLowerCase();
  const catFilter = state.pdvFilter.category;
  const filtered = products.filter(p => {
    const matchCat = catFilter === "Todos" || (p.category || "Sem categoria") === catFilter;
    const matchSearch = !search || p.name.toLowerCase().includes(search) || (p.category || "").toLowerCase().includes(search);
    return matchCat && matchSearch;
  });

  const subtotal = order.items.reduce((s, i) => s + i.subtotal, 0);
  const discount = order.discount || 0;
  const finalTotal = Math.max(0, subtotal - discount);

  els.pageContent.innerHTML = `
    ${cashAlert}
    <div class="grid-2">
      <div>
        <div class="card">
          <h3>Produtos</h3>
          <div class="pdv-search-bar">
            <input type="text" id="pdv-search" placeholder="🔍 Buscar produto..." value="${escapeAttr(state.pdvFilter.search)}" autocomplete="off">
          </div>
          <div class="category-chips" id="category-chips">
            ${categories.map(c => `
              <button type="button" class="chip ${c === catFilter ? "chip--active" : ""}" data-cat="${escapeAttr(c)}">${escapeHtml(c)}</button>
            `).join("")}
          </div>
          <div class="grid-3" id="product-grid">
            ${filtered.length ? filtered.map((p) => `
              <div class="product-card" data-product-id="${p.id}" data-product-price="${p.price}" data-product-name="${escapeAttr(p.name)}">
                <div class="name">${escapeHtml(p.name)}</div>
                <div class="meta">${escapeHtml(p.category || "Sem categoria")}</div>
                <div class="price">${formatMoney(p.price)}</div>
              </div>
            `).join("") : `<div class="empty-state" style="grid-column:1/-1">Nenhum produto encontrado.</div>`}
          </div>
        </div>
      </div>
      <div class="cart-panel card">
        <h3>Pedido #${order.id} - ${escapeHtml(order.customer_name || "Cliente")}</h3>
        <div id="cart-items">
          ${order.items.length
            ? order.items.map((item) => cartItemHtml(order.id, item)).join("")
            : `<div class="empty-state">Clique em um produto para adicionar</div>`}
        </div>

        <div class="cart-discount-row">
          <label style="margin:12px 0 4px;font-size:0.85rem;font-weight:600;">Desconto (R$)</label>
          <div style="display:flex;gap:8px;">
            <input type="number" id="discount-input" min="0" step="0.01" value="${discount.toFixed(2)}" style="flex:1;">
            <button type="button" class="btn btn-secondary btn-sm" id="btn-apply-discount">Aplicar</button>
          </div>
        </div>

        <div class="cart-total">
          <div>
            <div>Subtotal</div>
            ${discount > 0 ? `<div style="color:var(--success);font-size:0.85rem;">Desconto: −${formatMoney(discount)}</div>` : ""}
          </div>
          <div style="text-align:right;">
            ${discount > 0 ? `<div style="text-decoration:line-through;color:var(--text-muted);font-size:0.9rem;">${formatMoney(subtotal)}</div>` : ""}
            <div>${formatMoney(finalTotal)}</div>
          </div>
        </div>

        <div class="cart-notes">
          <label style="margin:8px 0 4px;font-size:0.85rem;font-weight:600;">Observação</label>
          <textarea id="notes-input" rows="2" placeholder="Ex: sem cebola, entrega no balcão...">${escapeHtml(order.notes || "")}</textarea>
          <button type="button" class="btn btn-secondary btn-sm" id="btn-save-notes" style="margin-top:6px;">💾 Salvar obs.</button>
        </div>

        <button type="button" class="btn btn-primary btn-block" id="btn-checkout" ${order.items.length ? "" : "disabled"}>Finalizar venda</button>
        <button type="button" class="btn btn-secondary btn-block" id="btn-finish-order">Concluir pedido</button>
        <button type="button" class="btn btn-secondary btn-block" id="btn-new-order">Novo pedido</button>
      </div>
    </div>
  `;

  // Search filter
  document.getElementById("pdv-search").addEventListener("input", (e) => {
    state.pdvFilter.search = e.target.value;
    renderPdv();
  });

  // Category chips
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      state.pdvFilter.category = chip.dataset.cat;
      renderPdv();
    });
  });

  // Add item with quantity modal
  document.querySelectorAll(".product-card").forEach((card) => {
    card.addEventListener("click", async () => {
      const qty = await promptQuantity(card.dataset.productName);
      if (!qty || qty < 1) return;
      await withError(
        () => endpoints.addItem(order.id, { product_id: Number(card.dataset.productId), quantity: qty }),
        "Item adicionado"
      );
      renderPdv();
    });
  });

  // Apply discount
  document.getElementById("btn-apply-discount")?.addEventListener("click", async () => {
    const d = parseFloat(document.getElementById("discount-input").value) || 0;
    await withError(() => endpoints.setDiscount(order.id, d), "Desconto aplicado");
    renderPdv();
  });

  // Save notes
  document.getElementById("btn-save-notes")?.addEventListener("click", async () => {
    const notes = document.getElementById("notes-input").value.trim();
    await withError(() => endpoints.setNotes(order.id, notes), "Observação salva");
  });

  bindCartActions(order.id);

  document.getElementById("btn-checkout")?.addEventListener("click", () => {
    const orderWithTotal = { ...order, total: finalTotal };
    openCheckoutModal(orderWithTotal);
  });

  document.getElementById("btn-finish-order")?.addEventListener("click", () => {
    state.currentOrder = null;
    state.pdvFilter = { search: "", category: "Todos" };
    renderPdv();
  });

  document.getElementById("btn-new-order")?.addEventListener("click", async () => {
    const customerName = await promptCustomerName();
    if (!customerName || customerName.length < 2) {
      if (customerName !== null) toast("Nome inválido", "error");
      return;
    }
    state.currentOrder = await withError(() => endpoints.createOrder({ customer_name: customerName }), "Novo pedido criado");
    state.pdvFilter = { search: "", category: "Todos" };
    renderPdv();
  });
}

// ─── MODALS ──────────────────────────────────────────────────────────────────
function promptCustomerName() {
  return new Promise((resolve) => {
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.innerHTML = `
      <div class="modal">
        <h3>Identificação do Cliente</h3>
        <label>Nome do cliente (obrigatório)</label>
        <input type="text" id="customer-name-input" placeholder="Ex: Maria" autocomplete="off">
        <div class="actions" style="margin-top:18px">
          <button type="button" class="btn btn-primary" id="confirm-customer">Confirmar</button>
          <button type="button" class="btn btn-secondary" id="cancel-customer">Cancelar</button>
        </div>
      </div>
    `;
    document.body.appendChild(backdrop);
    const input = backdrop.querySelector("#customer-name-input");
    input.focus();
    const close = (val) => { backdrop.remove(); resolve(val); };
    backdrop.querySelector("#confirm-customer").addEventListener("click", () => close(input.value.trim()));
    backdrop.querySelector("#cancel-customer").addEventListener("click", () => close(null));
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") close(input.value.trim()); });
  });
}

function promptQuantity(productName) {
  return new Promise((resolve) => {
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.innerHTML = `
      <div class="modal" style="max-width:320px;">
        <h3>Quantidade</h3>
        <p style="color:var(--text-muted);margin:0 0 12px;">${escapeHtml(productName || "Produto")}</p>
        <div class="qty-modal-row">
          <button type="button" class="btn btn-secondary btn-sm" id="qty-dec">−</button>
          <input type="number" id="qty-input" min="1" step="1" value="1" style="width:80px;text-align:center;font-size:1.2rem;">
          <button type="button" class="btn btn-secondary btn-sm" id="qty-inc">+</button>
        </div>
        <div class="actions" style="margin-top:18px">
          <button type="button" class="btn btn-primary" id="confirm-qty">Adicionar</button>
          <button type="button" class="btn btn-secondary" id="cancel-qty">Cancelar</button>
        </div>
      </div>
    `;
    document.body.appendChild(backdrop);
    const input = backdrop.querySelector("#qty-input");
    input.focus();
    input.select();
    const close = (val) => { backdrop.remove(); resolve(val); };
    backdrop.querySelector("#qty-dec").addEventListener("click", () => { input.value = Math.max(1, Number(input.value) - 1); });
    backdrop.querySelector("#qty-inc").addEventListener("click", () => { input.value = Number(input.value) + 1; });
    backdrop.querySelector("#confirm-qty").addEventListener("click", () => close(Number(input.value)));
    backdrop.querySelector("#cancel-qty").addEventListener("click", () => close(null));
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") close(Number(input.value)); });
  });
}

function promptUserPassword() {
  return new Promise((resolve) => {
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.innerHTML = `
      <div class="modal">
        <h3>Confirmação de Exclusão</h3>
        <label>Sua Senha (obrigatória)</label>
        <input type="password" id="user-password-input" placeholder="Sua senha">
        <div class="actions" style="margin-top:18px">
          <button type="button" class="btn btn-danger" id="confirm-user-pwd">Confirmar Exclusão</button>
          <button type="button" class="btn btn-secondary" id="cancel-user-pwd">Cancelar</button>
        </div>
      </div>
    `;
    document.body.appendChild(backdrop);
    const input = backdrop.querySelector("#user-password-input");
    input.focus();
    const close = (val) => { backdrop.remove(); resolve(val); };
    backdrop.querySelector("#confirm-user-pwd").addEventListener("click", () => close(input.value));
    backdrop.querySelector("#cancel-user-pwd").addEventListener("click", () => close(null));
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") close(input.value); });
  });
}

// ─── CART ────────────────────────────────────────────────────────────────────
function cartItemHtml(orderId, item) {
  return `
    <div class="cart-item" data-item-id="${item.id}">
      <div style="flex:1;">
        <strong>${escapeHtml(item.product_name)}</strong>
        <div class="meta">${formatMoney(item.price)} · Subtotal ${formatMoney(item.subtotal)}</div>
        <div class="qty-controls">
          <button type="button" data-action="dec" data-order="${orderId}" data-item="${item.id}">−</button>
          <input type="number" class="qty-inline" data-action="set" data-order="${orderId}" data-item="${item.id}" value="${item.quantity}" min="1" style="width:52px;text-align:center;">
          <button type="button" data-action="inc" data-order="${orderId}" data-item="${item.id}">+</button>
          <button type="button" data-action="remove" data-order="${orderId}" data-item="${item.id}" style="margin-left:4px;color:var(--danger);">🗑️</button>
        </div>
      </div>
    </div>
  `;
}

let _qtyDebounceTimers = {};

function bindCartActions(orderId) {
  document.querySelectorAll("[data-action]").forEach((btn) => {
    if (btn.dataset.action === "set") {
      // inline qty input with debounce
      btn.addEventListener("change", async () => {
        const itemId = Number(btn.dataset.item);
        const qty = Math.max(1, Number(btn.value));
        btn.value = qty;
        clearTimeout(_qtyDebounceTimers[itemId]);
        _qtyDebounceTimers[itemId] = setTimeout(async () => {
          await withError(() => endpoints.updateItem(orderId, itemId, { quantity: qty }));
          renderPdv();
        }, 400);
      });
      return;
    }

    btn.addEventListener("click", async () => {
      const itemId = Number(btn.dataset.item);
      const order = await withError(() => endpoints.getOrder(orderId));
      if (!order) return;
      const item = order.items.find((i) => i.id === itemId);
      if (!item) return;

      if (btn.dataset.action === "remove") {
        const password = await promptUserPassword();
        if (!password) return;
        await withError(() => endpoints.removeItem(orderId, itemId, password), "Item removido");
      } else if (btn.dataset.action === "inc") {
        await withError(() => endpoints.updateItem(orderId, itemId, { quantity: item.quantity + 1 }));
      } else if (btn.dataset.action === "dec") {
        if (item.quantity <= 1) {
          const password = await promptUserPassword();
          if (!password) return;
          await withError(() => endpoints.removeItem(orderId, itemId, password), "Item removido");
        } else {
          await withError(() => endpoints.updateItem(orderId, itemId, { quantity: item.quantity - 1 }));
        }
      }
      renderPdv();
    });
  });
}

// ─── CHECKOUT ────────────────────────────────────────────────────────────────
function openCheckoutModal(order) {
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  document.body.appendChild(backdrop);

  let payments = [];

  const render = () => {
    const totalReceived = payments.reduce((acc, p) => acc + p.amount, 0);
    const remaining = Math.max(0, order.total - totalReceived);

    backdrop.innerHTML = `
      <div class="modal">
        <h3>Finalizar venda</h3>
        <p>Total do Pedido: <strong>${formatMoney(order.total)}</strong></p>
        ${order.notes ? `<p style="color:var(--text-muted);font-size:0.9rem;">📝 ${escapeHtml(order.notes)}</p>` : ""}

        <div style="margin-bottom: 15px;">
          ${payments.map((p, idx) => `
            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
              <span>${formatPaymentMethod(p.method)}</span>
              <span>
                ${formatMoney(p.amount)}
                <button type="button" class="btn btn-sm btn-danger btn-remove-pay" data-idx="${idx}" style="padding:2px 6px; margin-left:5px;">×</button>
              </span>
            </div>
          `).join("")}
          ${payments.length ? `<hr style="margin:10px 0">` : ""}
          <p>Falta Receber: <strong style="color:var(--danger)">${formatMoney(remaining)}</strong></p>
        </div>

        <div style="background:var(--surface-2); padding:10px; border-radius:8px; margin-bottom:15px;">
          <label style="margin-top:0">Adicionar Pagamento</label>
          <div style="display:flex; gap:8px; margin-top:5px;">
            <select id="pay-method" style="flex:1">
              <option value="DINHEIRO">Dinheiro</option>
              <option value="PIX">PIX</option>
              <option value="CARTAO_CREDITO">Cartão de Crédito</option>
              <option value="CARTAO_DEBITO">Cartão de Débito</option>
              <option value="FATURADO">Fiado</option>
            </select>
            <input type="number" id="pay-amount" min="0.01" step="0.01" value="${remaining.toFixed(2)}" style="width:100px;">
            <button type="button" class="btn btn-secondary" id="add-pay">Add</button>
          </div>
        </div>

        <div class="actions" style="margin-top:18px">
          <button type="button" class="btn btn-primary" id="confirm-checkout" ${Math.round(totalReceived * 100) < Math.round(order.total * 100) ? "disabled" : ""}>Confirmar</button>
          <button type="button" class="btn btn-secondary" id="cancel-checkout">Cancelar</button>
        </div>
      </div>
    `;

    backdrop.querySelectorAll(".btn-remove-pay").forEach(btn => {
      btn.addEventListener("click", () => {
        payments.splice(Number(btn.dataset.idx), 1);
        render();
      });
    });

    backdrop.querySelector("#add-pay").addEventListener("click", () => {
      const method = backdrop.querySelector("#pay-method").value;
      const amount = Number(backdrop.querySelector("#pay-amount").value);
      if (amount > 0) {
        payments.push({ method, amount });
        render();
      }
    });

    backdrop.querySelector("#cancel-checkout").addEventListener("click", () => backdrop.remove());

    const confirmBtn = backdrop.querySelector("#confirm-checkout");
    if (!confirmBtn.disabled) {
      confirmBtn.addEventListener("click", async () => {
        const result = await withError(() => endpoints.checkout(order.id, { payments }));
        if (!result) return;
        backdrop.remove();

        // Fetch full order for receipt
        const fullOrder = await endpoints.getOrder(order.id).catch(() => null);

        // Show receipt prompt
        showReceiptModal(fullOrder || order, result.troco, payments);

        if (state.currentOrder && state.currentOrder.id === order.id) {
          state.currentOrder = null;
          state.pdvFilter = { search: "", category: "Todos" };
        }
        refreshCashBadge();
        if (state.view === "pdv") renderPdv();
        if (state.view === "orders") renderOrders();
      });
    }
  };

  render();
  backdrop.addEventListener("click", (e) => { if (e.target === backdrop) backdrop.remove(); });
}

// ─── ORDERS ──────────────────────────────────────────────────────────────────
async function renderOrders() {
  els.pageContent.innerHTML = `<div class="empty-state">Carregando pedidos...</div>`;
  const orders = await withError(() => endpoints.listOrders());
  if (!orders) return;

  els.pageContent.innerHTML = `
    <div class="card table-wrap">
      <table>
        <thead>
          <tr><th>ID</th><th>Cliente</th><th>Status</th><th>Total</th><th>Ações</th></tr>
        </thead>
        <tbody>
          ${orders.length ? orders.map((o) => `
            <tr id="order-row-${o.id}">
              <td>#${o.id}</td>
              <td>${escapeHtml(o.customer_name || "—")}</td>
              <td>${statusBadge(o.status)}</td>
              <td>${formatMoney(o.total)}</td>
              <td class="actions">
                <button type="button" class="btn btn-secondary btn-sm" data-view-order="${o.id}">Ver</button>
                ${o.status === "ABERTO" ? `<button type="button" class="btn btn-secondary btn-sm" data-edit-order="${o.id}">Editar</button>` : ""}
                ${o.status === "ABERTO" ? `<button type="button" class="btn btn-primary btn-sm" data-pay-order='${JSON.stringify({id: o.id, total: o.total}).replace(/'/g, "&#39;")}'>Pagar</button>` : ""}
                ${o.status === "ABERTO" && state.user.role === "admin"
                  ? `<button type="button" class="btn btn-danger btn-sm" data-cancel-order="${o.id}">Cancelar</button>`
                  : ""}
                <button type="button" class="btn btn-danger btn-sm" data-delete-order="${o.id}" style="background-color: #8B0000; border-color: #8B0000;">Excluir</button>
              </td>
            </tr>
          `).join("") : `<tr><td colspan="5" class="empty-state">Nenhum pedido</td></tr>`}
        </tbody>
      </table>
    </div>
  `;

  document.querySelectorAll("[data-view-order]").forEach((btn) => {
    btn.addEventListener("click", async () => showOrderDetail(Number(btn.dataset.viewOrder)));
  });
  document.querySelectorAll("[data-edit-order]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const orderId = Number(btn.dataset.editOrder);
      const order = await withError(() => endpoints.getOrder(orderId));
      if (order) {
        state.currentOrder = order;
        document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
        document.querySelector("[data-view='pdv']").classList.add("active");
        state.view = "pdv";
        els.pageTitle.textContent = "🛒 PDV";
        renderPdv();
      }
    });
  });
  document.querySelectorAll("[data-pay-order]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const order = JSON.parse(btn.dataset.payOrder);
      openCheckoutModal(order);
    });
  });
  document.querySelectorAll("[data-cancel-order]").forEach((btn) => {
    btn.addEventListener("click", () => openCancelModal(Number(btn.dataset.cancelOrder)));
  });
  document.querySelectorAll("[data-delete-order]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const orderId = Number(btn.dataset.deleteOrder);
      if (confirm(`Tem certeza que deseja APAGAR COMPLETAMENTE o pedido #${orderId}? Esta ação não pode ser desfeita.`)) {
        const password = await promptUserPassword();
        if (!password) return;
        const ok = await withError(() => endpoints.deleteOrder(orderId, password), "Pedido excluído com sucesso");
        if (ok) {
          if (state.currentOrder && state.currentOrder.id === orderId) state.currentOrder = null;
          await refreshCashBadge();
          renderOrders();
        }
      }
    });
  });
}

async function showOrderDetail(orderId) {
  const existingDetailRow = document.getElementById(`order-detail-row-${orderId}`);
  if (existingDetailRow) {
    existingDetailRow.remove();
    return;
  }

  // Close other open details rows to keep layout neat
  document.querySelectorAll(".order-detail-row").forEach(r => r.remove());

  const order = await withError(() => endpoints.getOrder(orderId));
  if (!order) return;

  const orderRow = document.getElementById(`order-row-${orderId}`);
  if (!orderRow) return;

  const detailRow = document.createElement("tr");
  detailRow.id = `order-detail-row-${orderId}`;
  detailRow.className = "order-detail-row";
  detailRow.innerHTML = `
    <td colspan="5" style="padding: 18px 24px; background: var(--surface-2); border-left: 5px solid var(--primary); transition: all 0.3s ease;">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:12px;">
        <h4 style="margin:0; font-size: 1.1rem; color: var(--text-base);">📋 Itens do Pedido #${order.id}</h4>
        <button type="button" class="btn btn-secondary btn-sm no-print" id="btn-print-order-${order.id}">🖨️ Imprimir Cupom</button>
      </div>
      ${order.notes ? `<div class="alert info" style="margin: 8px 0; padding: 10px 14px; font-size: 0.85rem; border-radius: 6px;">📝 <strong>Obs:</strong> ${escapeHtml(order.notes)}</div>` : ""}
      ${order.cancel_reason ? `<div class="alert cancel" style="margin: 8px 0; padding: 10px 14px; font-size: 0.85rem; border-radius: 6px;"><strong>Motivo do Cancelamento:</strong> ${escapeHtml(order.cancel_reason)}</div>` : ""}
      <table style="width: 100%; font-size: 0.9rem; border-collapse: collapse; margin-top: 10px;">
        <thead>
          <tr style="border-bottom: 2px solid var(--border-color);">
            <th style="background:none; text-align: left; padding: 6px 10px; color: var(--text-muted);">Produto</th>
            <th style="background:none; text-align: center; padding: 6px 10px; color: var(--text-muted);">Qtd</th>
            <th style="background:none; text-align: right; padding: 6px 10px; color: var(--text-muted);">Preço</th>
            <th style="background:none; text-align: right; padding: 6px 10px; color: var(--text-muted);">Subtotal</th>
          </tr>
        </thead>
        <tbody>
          ${order.items.map((i) => `
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
              <td style="padding:8px 10px; text-align: left;">${escapeHtml(i.product_name)}</td>
              <td style="padding:8px 10px; text-align: center;">${i.quantity}</td>
              <td style="padding:8px 10px; text-align: right;">${formatMoney(i.price)}</td>
              <td style="padding:8px 10px; text-align: right; font-weight: 500;">${formatMoney(i.subtotal)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
      <div style="text-align: right; margin-top: 14px; font-size: 0.95rem; line-height: 1.5;">
        ${order.discount > 0 ? `<p style="color:var(--success); margin: 3px 0;">Desconto: −${formatMoney(order.discount)}</p>` : ""}
        <p style="margin: 3px 0; font-size: 1.1rem;"><strong>Total: <span style="color: var(--primary);">${formatMoney(order.total)}</span></strong></p>
      </div>
    </td>
  `;

  orderRow.parentNode.insertBefore(detailRow, orderRow.nextSibling);

  document.getElementById(`btn-print-order-${order.id}`)?.addEventListener("click", () => printOrderReceipt(order));
}

function showReceiptModal(order, troco, payments) {
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  const printerName = localStorage.getItem("ldl_printer") || "IMP";
  const trocoFmt = formatMoney(troco || 0);
  backdrop.innerHTML = `
    <div class="modal" style="max-width:380px;text-align:center;">
      <div style="font-size:2.5rem;margin-bottom:8px;">✅</div>
      <h3 style="margin:0 0 6px;">Venda Concluída!</h3>
      <p style="color:var(--text-muted);margin:0 0 16px;">Troco: <strong style="color:var(--success);">${trocoFmt}</strong></p>
      <div style="background:var(--surface-2);border-radius:10px;padding:14px;margin-bottom:18px;text-align:left;font-size:0.85rem;">
        <div style="display:flex;justify-content:space-between;"><span>Impressora configurada:</span><strong>${escapeHtml(printerName)}</strong></div>
        <div style="margin-top:6px;color:var(--text-muted);font-size:0.78rem;">Configure a impressora padrão do Windows para <strong>${escapeHtml(printerName)}</strong> e o cupom irá direto para ela.</div>
      </div>
      <div style="display:flex;flex-direction:column;gap:10px;">
        <button type="button" class="btn btn-primary btn-block" id="btn-print-receipt">🖨️ Imprimir Cupom</button>
        <button type="button" class="btn btn-secondary btn-block" id="btn-skip-print">Fechar sem imprimir</button>
      </div>
    </div>
  `;
  document.body.appendChild(backdrop);

  backdrop.querySelector("#btn-print-receipt").addEventListener("click", () => {
    backdrop.remove();
    printOrderReceipt(order, troco, payments);
  });
  backdrop.querySelector("#btn-skip-print").addEventListener("click", () => {
    backdrop.remove();
    toast(`Venda concluída! Troco: ${trocoFmt}`, "success");
  });
}

function printOrderReceipt(order, troco, payments) {
  const win = window.open("", "_blank", "width=340,height=600");
  if (!win) { toast("Pop-up bloqueado. Permita pop-ups neste site.", "error"); return; }

  const items = (order.items || []).map(i =>
    `<tr>
      <td>${escapeHtml(i.product_name)}</td>
      <td style="text-align:center">${i.quantity}</td>
      <td style="text-align:right">${formatMoney(i.subtotal)}</td>
    </tr>`
  ).join("");

  const payLines = (payments || []).map(p =>
    `<tr><td>${formatPaymentMethod(p.method)}</td><td style="text-align:right">${formatMoney(p.amount)}</td></tr>`
  ).join("");

  const subtotal = (order.items || []).reduce((s, i) => s + i.subtotal, 0);
  const discount = order.discount || 0;
  const now = new Date().toLocaleString("pt-BR");

  win.document.write(`<!DOCTYPE html><html><head>
  <meta charset="UTF-8">
  <title>Cupom #${order.id}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    @page { margin: 4mm; size: 80mm auto; }
    body {
      font-family: 'Courier New', Courier, monospace;
      font-size: 11px;
      width: 72mm;
      color: #000;
      background: #fff;
    }
    .center { text-align: center; }
    .right  { text-align: right; }
    .bold   { font-weight: bold; }
    .big    { font-size: 14px; font-weight: bold; }
    .line   { border-top: 1px dashed #000; margin: 4px 0; }
    table   { width: 100%; border-collapse: collapse; }
    td      { padding: 2px 1px; vertical-align: top; }
    th      { padding: 2px 1px; border-bottom: 1px dashed #000; text-align: left; }
    th:last-child, td:last-child { text-align: right; }
    th:nth-child(2), td:nth-child(2) { text-align: center; }
    .total-row td { font-weight: bold; font-size: 13px; padding-top: 4px; }
    @media print {
      body { width: 72mm; }
      .no-print { display: none; }
    }
  </style>
</head><body>
  <div class="center big" style="margin-bottom:2px;">LAR DOCE LAR</div>
  <div class="center" style="font-size:10px;margin-bottom:2px;">Cupom não fiscal</div>
  <div class="line"></div>
  <div>Pedido: <span class="bold">#${order.id}</span></div>
  <div>Cliente: <span class="bold">${escapeHtml(order.customer_name || "—")}</span></div>
  <div>Data: ${now}</div>
  <div class="line"></div>
  <table>
    <thead><tr><th>Item</th><th>Qtd</th><th>Total</th></tr></thead>
    <tbody>${items}</tbody>
  </table>
  <div class="line"></div>
  ${discount > 0 ? `<table><tr><td>Subtotal</td><td class="right">${formatMoney(subtotal)}</td></tr><tr><td>Desconto</td><td class="right">−${formatMoney(discount)}</td></tr></table>` : ""}
  <table><tr class="total-row"><td>TOTAL</td><td class="right">${formatMoney(order.total)}</td></tr></table>
  <div class="line"></div>
  <div style="margin-bottom:2px;font-size:10px;">Pagamento:</div>
  <table>${payLines}</table>
  ${(troco > 0) ? `<div class="bold" style="margin-top:2px;">Troco: ${formatMoney(troco)}</div>` : ""}
  ${order.notes ? `<div class="line"></div><div style="font-size:10px;">Obs: ${escapeHtml(order.notes)}</div>` : ""}
  <div class="line"></div>
  <div class="center" style="font-size:10px;">Obrigado pela preferência!</div>
  <div class="center no-print" style="margin-top:12px;">
    <button onclick="window.print();" style="padding:6px 16px;font-size:12px;cursor:pointer;">🖨️ Imprimir</button>
    <button onclick="window.close();" style="padding:6px 16px;font-size:12px;cursor:pointer;margin-left:6px;">✕ Fechar</button>
  </div>
  <script>window.onload = function() { window.print(); }<\/script>
</body></html>`);
  win.document.close();
}

function openCancelModal(orderId) {
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = `
    <div class="modal">
      <h3>Cancelar pedido #${orderId}</h3>
      <label>Motivo (mín. 5 caracteres)</label>
      <textarea id="cancel-reason" rows="3" placeholder="Descreva o motivo"></textarea>
      <div class="actions" style="margin-top:18px">
        <button type="button" class="btn btn-danger" id="confirm-cancel">Confirmar cancelamento</button>
        <button type="button" class="btn btn-secondary" id="close-cancel">Fechar</button>
      </div>
    </div>
  `;
  document.body.appendChild(backdrop);
  backdrop.querySelector("#close-cancel").addEventListener("click", () => backdrop.remove());
  backdrop.querySelector("#confirm-cancel").addEventListener("click", async () => {
    const reason = backdrop.querySelector("#cancel-reason").value.trim();
    const ok = await withError(() => endpoints.cancelOrder(orderId, { reason }), "Pedido cancelado");
    if (!ok) return;
    backdrop.remove();
    renderOrders();
  });
}

// ─── PRODUCTS ─────────────────────────────────────────────────────────────────
async function renderProducts() {
  els.pageContent.innerHTML = `<div class="empty-state">Carregando produtos...</div>`;
  const products = await withError(() => endpoints.listProducts(false));
  if (!products) return;

  els.pageContent.innerHTML = `
    <div class="card">
      <h3>Novo produto</h3>
      <form id="product-form">
        <div class="form-row">
          <div><label>Nome</label><input name="name" required minlength="2"></div>
          <div><label>Categoria</label><input name="category"></div>
          <div><label>Preço</label><input name="price" type="number" min="0.01" step="0.01" required></div>
        </div>
        <button type="submit" class="btn btn-primary">Cadastrar</button>
      </form>
    </div>
    <div class="card table-wrap">
      <table>
        <thead><tr><th>Nome</th><th>Categoria</th><th>Preço</th><th>Status</th><th>Ações</th></tr></thead>
        <tbody>
          ${products.map((p) => `
            <tr>
              <td>${escapeHtml(p.name)}</td>
              <td>${escapeHtml(p.category || "—")}</td>
              <td>${formatMoney(p.price)}</td>
              <td>${p.is_active ? '<span class="badge open">Ativo</span>' : '<span class="badge cancel">Inativo</span>'}</td>
              <td class="actions">
                ${p.is_active ? `<button type="button" class="btn btn-secondary btn-sm" data-edit-product='${JSON.stringify(p)}'>Editar</button>
                <button type="button" class="btn btn-danger btn-sm" data-deactivate="${p.id}">Inativar</button>` : ""}
                <button type="button" class="btn btn-danger btn-sm" data-delete-product="${p.id}" style="background-color: #8B0000; border-color: #8B0000;">Excluir</button>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;

  document.getElementById("product-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const ok = await withError(() => endpoints.createProduct({
      name: fd.get("name"),
      category: fd.get("category") || null,
      price: Number(fd.get("price")),
    }), "Produto cadastrado");
    if (ok) { e.target.reset(); renderProducts(); }
  });

  document.querySelectorAll("[data-deactivate]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const ok = await withError(() => endpoints.deactivateProduct(Number(btn.dataset.deactivate)), "Produto inativado");
      if (ok) renderProducts();
    });
  });

  document.querySelectorAll("[data-delete-product]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (confirm("Tem certeza que deseja EXCLUIR este produto definitivamente?")) {
        const password = await promptUserPassword();
        if (!password) return;
        const ok = await withError(() => endpoints.deleteProduct(Number(btn.dataset.deleteProduct), password), "Produto excluído");
        if (ok) renderProducts();
      }
    });
  });

  document.querySelectorAll("[data-edit-product]").forEach((btn) => {
    btn.addEventListener("click", () => openEditProductModal(JSON.parse(btn.dataset.editProduct)));
  });
}

function openEditProductModal(product) {
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = `
    <div class="modal">
      <h3>Editar produto</h3>
      <label>Nome</label><input id="edit-name" value="${escapeAttr(product.name)}">
      <label>Categoria</label><input id="edit-category" value="${escapeAttr(product.category || "")}">
      <label>Preço</label><input id="edit-price" type="number" min="0.01" step="0.01" value="${product.price}">
      <div class="actions" style="margin-top:18px">
        <button type="button" class="btn btn-primary" id="save-product">Salvar</button>
        <button type="button" class="btn btn-secondary" id="close-product">Fechar</button>
      </div>
    </div>
  `;
  document.body.appendChild(backdrop);
  backdrop.querySelector("#close-product").addEventListener("click", () => backdrop.remove());
  backdrop.querySelector("#save-product").addEventListener("click", async () => {
    const ok = await withError(() => endpoints.updateProduct(product.id, {
      name: backdrop.querySelector("#edit-name").value,
      category: backdrop.querySelector("#edit-category").value || null,
      price: Number(backdrop.querySelector("#edit-price").value),
      is_active: true,
    }), "Produto atualizado");
    if (ok) { backdrop.remove(); renderProducts(); }
  });
}

// ─── CASH ────────────────────────────────────────────────────────────────────
async function renderCash() {
  els.pageContent.innerHTML = `<div class="empty-state">Carregando caixa...</div>`;
  const [status, flow] = await Promise.all([
    withError(() => endpoints.cashStatus()),
    state.user.role === "admin" ? withError(() => endpoints.listCashflow()) : Promise.resolve([]),
  ]);
  if (!status) return;

  const isAdmin = state.user.role === "admin";
  const session = status.session;

  let report = null;
  if (status.open && isAdmin) {
    report = await withError(() => endpoints.getCashReport());
  }

  els.pageContent.innerHTML = `
    <div class="card">
      <h3>Status do caixa</h3>
      ${status.open ? `
        <p>Sessão #${session.id} · Aberto em ${formatDateTime(session.opened_at)}</p>
        <p>Valor esperado na gaveta: <strong>${formatMoney(session.expected_amount)}</strong></p>
      ` : `<p class="alert warning">Nenhuma sessão aberta no momento.</p>`}

      ${isAdmin && status.open && report ? `
        <div style="margin: 20px 0; padding: 15px; background: #f0f7ff; border-radius: 8px; border-left: 5px solid #0066cc;">
          <h4>📊 Conferência de Valores</h4>
          <ul style="list-style: none; padding: 0; margin-top: 10px;">
            ${Object.entries(report.by_method).map(([method, amount]) => `
              <li style="padding: 5px 0; border-bottom: 1px solid #ddd; display: flex; justify-content: space-between;">
                <strong>${formatPaymentMethod(method)}</strong> <span>${formatMoney(amount)}</span>
              </li>
            `).join("")}
          </ul>
        </div>
      ` : ""}

      <div class="form-row">
        ${!status.open ? `
          <div>
            <label>Valor de abertura</label>
            <input type="number" id="open-amount" min="0" step="0.01" value="0">
            <button type="button" class="btn btn-primary btn-block" id="btn-open-cash">Abrir caixa</button>
          </div>
        ` : ""}
        ${status.open ? `
          <div>
            <label>Valor de fechamento</label>
            <input type="number" id="close-amount" min="0" step="0.01" value="${session.expected_amount.toFixed(2)}">
            <label>Senha liberação (Obrigatória)</label>
            <input type="password" id="close-password" placeholder="Senha do Admin">
            <button type="button" class="btn btn-danger btn-block" id="btn-close-cash" style="margin-top:12px;">Fechar caixa</button>
          </div>
        ` : ""}
        ${status.open ? `
          <div>
            <label>Suprimento</label>
            <input type="number" id="supply-amount" min="0.01" step="0.01">
            <input type="text" id="supply-desc" placeholder="Descrição">
            <button type="button" class="btn btn-secondary btn-block" id="btn-supply">Registrar suprimento</button>
          </div>
        ` : ""}
        ${isAdmin && status.open ? `
          <div>
            <label>Sangria</label>
            <input type="number" id="withdraw-amount" min="0.01" step="0.01">
            <input type="text" id="withdraw-desc" placeholder="Descrição">
            <button type="button" class="btn btn-secondary btn-block" id="btn-withdraw">Registrar sangria</button>
          </div>
        ` : ""}
      </div>
    </div>
    ${isAdmin && flow?.length ? `
      <div class="card table-wrap">
        <h3>Fluxo de caixa</h3>
        <table>
          <thead><tr><th>ID</th><th>Tipo</th><th>Valor</th><th>Pagamento</th><th>Descrição</th><th>Data</th></tr></thead>
          <tbody>
            ${flow.slice(0, 50).map((m) => `
              <tr>
                <td>${m.id}</td>
                <td>${m.type}</td>
                <td>${formatMoney(m.amount)}</td>
                <td>${formatPaymentMethod(m.payment_method)}</td>
                <td>${escapeHtml(m.description || "—")}</td>
                <td>${formatDateTime(m.created_at)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    ` : ""}
  `;

  document.getElementById("btn-open-cash")?.addEventListener("click", async () => {
    const opening_amount = Number(document.getElementById("open-amount").value);
    const ok = await withError(() => endpoints.openCash({ opening_amount }), "Caixa aberto");
    if (ok) { await refreshCashBadge(); navigate("pdv"); }
  });

  document.getElementById("btn-close-cash")?.addEventListener("click", async () => {
    const closing_amount = Number(document.getElementById("close-amount").value);
    const password = document.getElementById("close-password").value || null;
    const ok = await withError(() => endpoints.closeCash({ closing_amount, password }), "Caixa fechado");
    if (ok) { await refreshCashBadge(); renderCash(); }
  });

  document.getElementById("btn-supply")?.addEventListener("click", async () => {
    const amount = Number(document.getElementById("supply-amount").value);
    const description = document.getElementById("supply-desc").value.trim();
    const ok = await withError(() => endpoints.supplyCash({ amount, description }), "Suprimento registrado");
    if (ok) { refreshCashBadge(); renderCash(); }
  });

  document.getElementById("btn-withdraw")?.addEventListener("click", async () => {
    const amount = Number(document.getElementById("withdraw-amount").value);
    const description = document.getElementById("withdraw-desc").value.trim();
    const ok = await withError(() => endpoints.withdrawCash({ amount, description }), "Sangria registrada");
    if (ok) { refreshCashBadge(); renderCash(); }
  });
}

// ─── INVOICES ────────────────────────────────────────────────────────────────
async function renderInvoices() {
  els.pageContent.innerHTML = `<div class="empty-state">Carregando Fiados...</div>`;
  const invoices = await withError(() => endpoints.listInvoices());
  if (!invoices) return;

  if (invoices.length === 0) {
    els.pageContent.innerHTML = `
      <div class="empty-state" style="margin-top: 40px;">
        <span style="font-size: 3rem; margin-bottom: 16px; display: block;">🎉</span>
        <h2>Tudo em dia!</h2>
        <p>Nenhum cliente possui contas pendentes no fiado.</p>
      </div>
    `;
    return;
  }

  els.pageContent.innerHTML = `
    <div class="card table-wrap">
      <table>
        <thead>
          <tr>
            <th>Cliente</th>
            <th>1ª Compra</th>
            <th style="text-align:right">Total Devido</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${invoices.map((inv) => `
            <tr>
              <td><strong>${escapeHtml(inv.customer_name)}</strong></td>
              <td>${formatDateTime(inv.first_purchase).split(" ")[0].replace(",", "")}</td>
              <td style="text-align:right; font-weight:bold; color:var(--danger)">${formatMoney(inv.total)}</td>
              <td style="text-align:right">
                <button class="btn btn-sm btn-secondary btn-detail-invoice" data-customer="${escapeHtml(inv.customer_name)}">Ver Detalhes</button>
                <button class="btn btn-sm btn-primary btn-pay-invoice" data-customer="${escapeHtml(inv.customer_name)}" data-total="${inv.total}">Quitar Dívida</button>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;

  els.pageContent.querySelectorAll(".btn-detail-invoice").forEach((btn) => {
    btn.addEventListener("click", () => {
      const customer = btn.dataset.customer;
      const inv = invoices.find(i => i.customer_name === customer);
      if (inv) openInvoiceDetailModal(inv);
    });
  });

  els.pageContent.querySelectorAll(".btn-pay-invoice").forEach((btn) => {
    btn.addEventListener("click", () => {
      openPayInvoiceModal(btn.dataset.customer, Number(btn.dataset.total));
    });
  });
}

function openInvoiceDetailModal(inv) {
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  let html = `
    <div class="modal" style="max-width: 600px; max-height: 80vh; overflow-y: auto;">
      <h3>Detalhes da Conta: ${escapeHtml(inv.customer_name)}</h3>
      <p>Total Devido: <strong style="color:var(--danger)">${formatMoney(inv.total)}</strong></p>
      <hr style="margin: 10px 0;">
  `;
  inv.orders.forEach(o => {
    html += `
      <div style="margin-bottom: 12px; padding: 10px; border: 1px solid #ddd; border-radius: 4px;">
        <strong>Pedido #${o.id} - ${formatDateTime(o.created_at)}</strong> (Subtotal: ${formatMoney(o.total)})
        <ul style="margin: 5px 0 0 20px; font-size: 0.9em; color: var(--text-muted);">
          ${o.items.map(i => `<li>${i.quantity}x ${escapeHtml(i.product_name)} - ${formatMoney(i.subtotal)}</li>`).join("")}
        </ul>
      </div>
    `;
  });
  html += `
      <div class="actions" style="margin-top:18px">
        <button type="button" class="btn btn-secondary" id="close-detail">Fechar</button>
      </div>
    </div>
  `;
  backdrop.innerHTML = html;
  document.body.appendChild(backdrop);
  backdrop.querySelector("#close-detail").addEventListener("click", () => backdrop.remove());
}

function openPayInvoiceModal(customerName, total) {
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = `
    <div class="modal">
      <h3>Quitar Fiado</h3>
      <p>Recebendo conta de <strong>${customerName}</strong> no valor de <strong>${formatMoney(total)}</strong>.</p>
      <label>Forma de Pagamento</label>
      <select id="invoice-pay-method">
        <option value="DINHEIRO">Dinheiro</option>
        <option value="PIX">PIX</option>
        <option value="CARTAO_CREDITO">Cartão de Crédito</option>
        <option value="CARTAO_DEBITO">Cartão de Débito</option>
      </select>
      <div class="actions" style="margin-top:18px">
        <button type="button" class="btn btn-primary" id="confirm-pay">Quitar e Receber</button>
        <button type="button" class="btn btn-secondary" id="cancel-pay">Cancelar</button>
      </div>
    </div>
  `;
  document.body.appendChild(backdrop);
  const close = () => backdrop.remove();
  backdrop.querySelector("#cancel-pay").addEventListener("click", close);
  backdrop.querySelector("#confirm-pay").addEventListener("click", async () => {
    const method = backdrop.querySelector("#invoice-pay-method").value;
    const ok = await withError(() => endpoints.payInvoice(customerName, { payment_method: method }), "Conta quitada com sucesso!");
    if (ok) { close(); renderInvoices(); }
  });
}

// ─── REPORTS ─────────────────────────────────────────────────────────────────
async function renderReports() {
  const today = new Date().toISOString().slice(0, 10);
  els.pageContent.innerHTML = `
    <div class="card no-print">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <h3>Relatórios</h3>
        <button type="button" class="btn btn-secondary" onclick="window.print()">🖨️ Salvar PDF / Imprimir</button>
      </div>
      <div class="form-row" style="margin-top:12px">
        <div>
          <label>Tipo de Relatório</label>
          <select id="report-type">
            <option value="period">Fluxo de Caixa</option>
            <option value="products">Produtos Vendidos</option>
          </select>
        </div>
        <div>
          <label>Data Inicial</label>
          <input type="date" id="start-date" value="${today}">
        </div>
        <div>
          <label>Data Final</label>
          <input type="date" id="end-date" value="${today}">
        </div>
      </div>
      <button type="button" class="btn btn-primary" id="btn-report" style="margin-top:12px">Gerar relatório</button>
    </div>
    <div id="report-result" style="margin-top:16px"></div>
  `;

  const formatDt = (d) => d.split('-').reverse().join('/');

  const loadReport = async () => {
    const type = document.getElementById("report-type").value;
    const startDate = document.getElementById("start-date").value;
    const endDate = document.getElementById("end-date").value;

    if (type === "period") {
      const report = await withError(() => endpoints.periodReport(startDate, endDate));
      if (!report) return;
      const methods = Object.entries(report.by_method || {})
        .map(([k, v]) => `<li style="display: flex; justify-content: space-between; gap: 8px;"><span>${formatPaymentMethod(k)}</span><span style="text-align: right; word-break: break-all;">${formatMoney(v)}</span></li>`).join("");

      document.getElementById("report-result").innerHTML = `
        <div class="report-receipt">
          <div class="receipt-header">
            <h2>LarDoceLar</h2>
            <p>${startDate === endDate ? formatDt(startDate) : `De ${formatDt(startDate)} até ${formatDt(endDate)}`}</p>
          </div>
          <div class="receipt-body">
            <p><strong>Vendas (Total):</strong> ${formatMoney(report.total)}</p>
            <hr style="border: none; border-top: 1px dashed var(--text-muted); margin: 12px 0;">
            <p style="margin-bottom:8px"><strong>Por método de pagamento:</strong></p>
            <ul>${methods || "<li><span>Nenhum</span><span>—</span></li>"}</ul>
          </div>
        </div>
      `;
    } else {
      const products = await withError(() => endpoints.productsReport(startDate, endDate));
      if (!products) return;

      const totalRev = products.reduce((acc, p) => acc + p.total, 0);
      const totalQty = products.reduce((acc, p) => acc + p.quantity, 0);

      document.getElementById("report-result").innerHTML = `
        <div class="report-receipt" style="max-width: 600px;">
          <div class="receipt-header">
            <h2>LarDoceLar</h2>
            <p>${startDate === endDate ? formatDt(startDate) : `De ${formatDt(startDate)} até ${formatDt(endDate)}`}</p>
          </div>
          <div class="receipt-body">
            <table style="width:100%; border-collapse:collapse; margin-top:10px;">
              <thead>
                <tr style="border-bottom:1px solid #ddd;">
                  <th style="padding:4px; text-align:left;">Produto</th>
                  <th style="padding:4px; text-align:right;">Qtd</th>
                  <th style="padding:4px; text-align:right;">Vendas</th>
                </tr>
              </thead>
              <tbody>
                ${products.length ? products.map(p => `
                  <tr style="border-bottom:1px solid #eee;">
                    <td style="padding:4px;">${escapeHtml(p.product_name)}</td>
                    <td style="padding:4px; text-align:right;">${p.quantity}</td>
                    <td style="padding:4px; text-align:right;">${formatMoney(p.total)}</td>
                  </tr>
                `).join("") : '<tr><td colspan="3" style="text-align:center; padding:10px;">Nenhuma venda no período.</td></tr>'}
              </tbody>
            </table>
            <hr style="border: none; border-top: 1px dashed var(--text-muted); margin: 12px 0;">
            <p style="text-align:right;"><strong>Total Itens:</strong> ${totalQty}</p>
            <p style="text-align:right;"><strong>Total Vendas:</strong> ${formatMoney(totalRev)}</p>
          </div>
        </div>
      `;
    }
  };

  document.getElementById("btn-report").addEventListener("click", loadReport);
  loadReport();
}

// ─── USERS ───────────────────────────────────────────────────────────────────
async function renderUsers() {
  els.pageContent.innerHTML = `<div class="empty-state">Carregando usuários...</div>`;
  const users = await withError(() => endpoints.listUsers());
  if (!users) return;

  els.pageContent.innerHTML = `
    <div class="card">
      <h3>Novo usuário</h3>
      <form id="user-form">
        <div class="form-row">
          <div><label>Nome</label><input name="name" required minlength="3"></div>
          <div><label>Senha</label><input name="password" type="password" required minlength="4"></div>
          <div>
            <label>Papel</label>
            <select name="role">
              <option value="cashier">Caixa (cashier)</option>
              <option value="admin">Administrador</option>
            </select>
          </div>
        </div>
        <button type="submit" class="btn btn-primary">Cadastrar usuário</button>
      </form>
    </div>
    <div class="card table-wrap">
      <table>
        <thead><tr><th>ID</th><th>Nome</th><th>Papel</th><th>Ações</th></tr></thead>
        <tbody>
          ${users.map((u) => `
            <tr>
              <td>${u.id}</td>
              <td>${escapeHtml(u.name)}</td>
              <td>${u.role}</td>
              <td class="actions">
                <button type="button" class="btn btn-danger btn-sm" data-delete-user="${u.id}" style="background-color: #8B0000; border-color: #8B0000;">Excluir</button>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;

  document.querySelectorAll("[data-delete-user]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (confirm("Tem certeza que deseja EXCLUIR este usuário definitivamente?")) {
        const password = await promptUserPassword();
        if (!password) return;
        const ok = await withError(() => endpoints.deleteUser(Number(btn.dataset.deleteUser), password), "Usuário excluído");
        if (ok) renderUsers();
      }
    });
  });

  document.getElementById("user-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const ok = await withError(() => endpoints.createUser({
      name: fd.get("name"),
      password: fd.get("password"),
      role: fd.get("role"),
    }), "Usuário criado");
    if (ok) { e.target.reset(); renderUsers(); }
  });
}

// ─── UTILS ───────────────────────────────────────────────────────────────────
function statusBadge(status) {
  const map = { ABERTO: "open", FECHADO: "closed", CANCELADO: "cancel" };
  return `<span class="badge ${map[status] || ""}">${status}</span>`;
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function escapeAttr(text) {
  return escapeHtml(text).replaceAll("'", "&#39;");
}

// ─── INIT ────────────────────────────────────────────────────────────────────
async function init() {
  const setup = await endpoints.setup().catch(() => ({ needs_setup: false }));
  if (setup.needs_setup) {
    showLogin(true);
    return;
  }

  if (!getToken()) {
    showLogin(false);
    return;
  }

  const me = await withError(() => endpoints.me());
  if (!me) {
    showLogin(false);
    return;
  }
  setSession(getToken(), me);
  showApp();
}

els.loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = document.getElementById("login-name").value.trim();
  const password = document.getElementById("login-password").value;
  const data = await withError(() => endpoints.login({ name, password }));
  if (!data) return;
  setSession(data.token, { id: data.user_id, name, role: data.role });
  showApp();
});

els.setupForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = document.getElementById("setup-name").value.trim();
  const password = document.getElementById("setup-password").value;
  const created = await withError(() => endpoints.createUser({ name, password, role: "admin" }));
  if (!created) return;
  const login = await withError(() => endpoints.login({ name, password }));
  if (!login) return;
  setSession(login.token, { id: login.user_id, name, role: login.role });
  toast("Administrador criado com sucesso!", "success");
  showApp();
});

els.btnLogout.addEventListener("click", () => {
  clearSession();
  state.currentOrder = null;
  showLogin(false);
});

init();
