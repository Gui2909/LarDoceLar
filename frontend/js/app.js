import {
  endpoints,
  getToken,
  getUser,
  setSession,
  clearSession,
  formatMoney,
  formatDateTime,
} from "./api.js?v=2";

const state = {
  user: null,
  view: "pdv",
  currentOrder: null,
  cashStatus: null,
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
  { id: "pdv", label: "🛒 PDV", roles: ["admin", "cashier"] },
  { id: "orders", label: "📋 Pedidos", roles: ["admin", "cashier"] },
  { id: "products", label: "📦 Produtos", roles: ["admin"] },
  { id: "cash", label: "💰 Caixa", roles: ["admin", "cashier"] },
  { id: "invoices", label: "📄 Faturamentos", roles: ["admin", "cashier"] },
  { id: "reports", label: "📊 Relatórios", roles: ["admin"] },
  { id: "users", label: "👤 Usuários", roles: ["admin"] },
];

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
  
  navigate(state.view || "pdv");
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
  if (view !== "cash" && state.cashStatus && !state.cashStatus.open) {
    toast("Abertura de turno obrigatória. Abra o caixa primeiro.", "error");
    view = "cash";
  }
  state.view = view;
  renderNav();
  const titles = {
    pdv: "Ponto de Venda",
    orders: "Pedidos",
    products: "Produtos",
    stock: "Estoque",
    cash: "Caixa",
    invoices: "Faturamentos",
    reports: "Relatórios",
    users: "Usuários",
  };
  els.pageTitle.textContent = titles[view] || "LarDoceLar";
  const renderers = {
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
  if (!order) return;

  const cashAlert = !cash?.open
    ? `<div class="alert warning">Caixa fechado. Abra o caixa (menu Caixa) antes de finalizar vendas.</div>`
    : "";

  els.pageContent.innerHTML = `
    ${cashAlert}
    <div class="grid-2">
      <div>
        <div class="card">
          <h3>Produtos</h3>
          <div class="grid-3" id="product-grid">
            ${products.length ? products.map((p) => `
              <div class="product-card" data-product-id="${p.id}">
                <div class="name">${escapeHtml(p.name)}</div>
                <div class="meta">${escapeHtml(p.category || "Sem categoria")}</div>
                <div class="price">${formatMoney(p.price)}</div>
              </div>
            `).join("") : `<div class="empty-state">Cadastre produtos no menu Produtos.</div>`}
          </div>
        </div>
      </div>
      <div class="cart-panel card">
        <h3>Pedido #${order.id} - ${escapeHtml(order.customer_name || 'Cliente')}</h3>
        <div id="cart-items">
          ${order.items.length ? order.items.map((item) => cartItemHtml(order.id, item)).join("") : `<div class="empty-state">Clique em um produto para adicionar</div>`}
        </div>
        <div class="cart-total"><span>Total</span><span>${formatMoney(order.total)}</span></div>
        <button type="button" class="btn btn-primary btn-block" id="btn-checkout" ${order.items.length ? "" : "disabled"}>Finalizar venda</button>
        <button type="button" class="btn btn-secondary btn-block" id="btn-new-order">Novo pedido</button>
      </div>
    </div>
  `;

  document.querySelectorAll(".product-card").forEach((card) => {
    card.addEventListener("click", async () => {
      await withError(
        () => endpoints.addItem(order.id, { product_id: Number(card.dataset.productId), quantity: 1 }),
        "Item adicionado"
      );
      renderPdv();
    });
  });

  bindCartActions(order.id);
  document.getElementById("btn-checkout")?.addEventListener("click", () => openCheckoutModal(order));
  document.getElementById("btn-new-order")?.addEventListener("click", async () => {
    const customerName = await promptCustomerName();
    if (!customerName || customerName.length < 2) {
      if (customerName !== null) toast("Nome inválido", "error");
      return;
    }
    state.currentOrder = await withError(() => endpoints.createOrder({ customer_name: customerName }), "Novo pedido criado");
    renderPdv();
  });
}

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
    setTimeout(() => input.focus(), 50);

    const close = (val) => {
      backdrop.remove();
      resolve(val);
    };

    backdrop.querySelector("#cancel-customer").addEventListener("click", () => close(null));
    backdrop.querySelector("#confirm-customer").addEventListener("click", () => close(input.value.trim()));
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") close(input.value.trim());
    });
  });
}

function cartItemHtml(orderId, item) {
  return `
    <div class="cart-item" data-item-id="${item.id}">
      <div>
        <strong>${escapeHtml(item.product_name)}</strong>
        <div class="meta">${formatMoney(item.price)} · Subtotal ${formatMoney(item.subtotal)}</div>
        <div class="qty-controls">
          <button type="button" data-action="dec" data-order="${orderId}" data-item="${item.id}">−</button>
          <span>${item.quantity}</span>
          <button type="button" data-action="inc" data-order="${orderId}" data-item="${item.id}">+</button>
          <button type="button" data-action="remove" data-order="${orderId}" data-item="${item.id}">🗑️</button>
        </div>
      </div>
    </div>
  `;
}

function bindCartActions(orderId) {
  document.querySelectorAll("[data-action]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const itemId = Number(btn.dataset.item);
      const order = await withError(() => endpoints.getOrder(orderId));
      if (!order) return;
      const item = order.items.find((i) => i.id === itemId);
      if (!item) return;

      if (btn.dataset.action === "remove") {
        await withError(() => endpoints.removeItem(orderId, itemId), "Item removido");
      } else if (btn.dataset.action === "inc") {
        await withError(() => endpoints.updateItem(orderId, itemId, { quantity: item.quantity + 1 }));
      } else if (btn.dataset.action === "dec") {
        if (item.quantity <= 1) {
          await withError(() => endpoints.removeItem(orderId, itemId), "Item removido");
        } else {
          await withError(() => endpoints.updateItem(orderId, itemId, { quantity: item.quantity - 1 }));
        }
      }
      renderPdv();
    });
  });
}

function openCheckoutModal(order) {
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = `
    <div class="modal">
      <h3>Finalizar venda</h3>
      <p>Total: <strong>${formatMoney(order.total)}</strong></p>
      <label>Forma de pagamento</label>
      <select id="pay-method">
        <option value="DINHEIRO">Dinheiro</option>
        <option value="PIX">PIX</option>
        <option value="CARTAO_CREDITO">Cartão de Crédito</option>
        <option value="CARTAO_DEBITO">Cartão de Débito</option>
        <option value="FATURADO">Faturado (Fiado)</option>
      </select>
      <label>Valor recebido</label>
      <input type="number" id="pay-amount" min="0.01" step="0.01" value="${order.total.toFixed(2)}">
      <div class="actions" style="margin-top:18px">
        <button type="button" class="btn btn-primary" id="confirm-checkout">Confirmar</button>
        <button type="button" class="btn btn-secondary" id="cancel-checkout">Cancelar</button>
      </div>
    </div>
  `;
  document.body.appendChild(backdrop);

  backdrop.querySelector("#cancel-checkout").addEventListener("click", () => backdrop.remove());
  backdrop.addEventListener("click", (e) => { if (e.target === backdrop) backdrop.remove(); });
  backdrop.querySelector("#confirm-checkout").addEventListener("click", async () => {
    const payment_method = backdrop.querySelector("#pay-method").value;
    const amount_received = Number(backdrop.querySelector("#pay-amount").value);
    const result = await withError(() =>
      endpoints.checkout(order.id, { payment_method, amount_received })
    );
    if (!result) return;
    backdrop.remove();
    toast(`Venda concluída! Troco: ${formatMoney(result.troco)}`, "success");
    state.currentOrder = null;
    refreshCashBadge();
    renderPdv();
  });
}

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
            <tr>
              <td>#${o.id}</td>
              <td>${escapeHtml(o.customer_name || "—")}</td>
              <td>${statusBadge(o.status)}</td>
              <td>${formatMoney(o.total)}</td>
              <td class="actions">
                <button type="button" class="btn btn-secondary btn-sm" data-view-order="${o.id}">Ver</button>
                ${o.status === "ABERTO" && state.user.role === "admin"
                  ? `<button type="button" class="btn btn-danger btn-sm" data-cancel-order="${o.id}">Cancelar</button>`
                  : ""}
              </td>
            </tr>
          `).join("") : `<tr><td colspan="4" class="empty-state">Nenhum pedido</td></tr>`}
        </tbody>
      </table>
    </div>
    <div id="order-detail"></div>
  `;

  document.querySelectorAll("[data-view-order]").forEach((btn) => {
    btn.addEventListener("click", async () => showOrderDetail(Number(btn.dataset.viewOrder)));
  });
  document.querySelectorAll("[data-cancel-order]").forEach((btn) => {
    btn.addEventListener("click", () => openCancelModal(Number(btn.dataset.cancelOrder)));
  });
}

async function showOrderDetail(orderId) {
  const order = await withError(() => endpoints.getOrder(orderId));
  if (!order) return;
  const container = document.getElementById("order-detail");
  container.innerHTML = `
    <div class="card">
      <h3>Pedido #${order.id} - ${escapeHtml(order.customer_name || 'Cliente')} · ${order.status}</h3>
      <table>
        <thead><tr><th>Produto</th><th>Qtd</th><th>Preço</th><th>Subtotal</th></tr></thead>
        <tbody>
          ${order.items.map((i) => `
            <tr>
              <td>${escapeHtml(i.product_name)}</td>
              <td>${i.quantity}</td>
              <td>${formatMoney(i.price)}</td>
              <td>${formatMoney(i.subtotal)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
      <p><strong>Total: ${formatMoney(order.total)}</strong></p>
    </div>
  `;
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
                <button type="button" class="btn btn-danger btn-sm" data-deactivate="${p.id}">Inativar</button>` : "—"}
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
          <p>Confira os totais movimentados neste turno por método de pagamento:</p>
          <ul style="list-style: none; padding: 0; margin-top: 10px;">
            ${Object.entries(report.by_method).map(([method, amount]) => `
              <li style="padding: 5px 0; border-bottom: 1px solid #ddd; display: flex; justify-content: space-between;">
                <strong>${method}</strong> <span>${formatMoney(amount)}</span>
              </li>
            `).join("")}
          </ul>
        </div>
      ` : ""}

      <div class="form-row">
        ${isAdmin && !status.open ? `
          <div>
            <label>Valor de abertura</label>
            <input type="number" id="open-amount" min="0" step="0.01" value="0">
            <button type="button" class="btn btn-primary btn-block" id="btn-open-cash">Abrir caixa</button>
          </div>
        ` : ""}
        ${isAdmin && status.open ? `
          <div>
            <label>Valor de fechamento</label>
            <input type="number" id="close-amount" min="0" step="0.01" value="${session.expected_amount.toFixed(2)}">
            <label>Senha liberação (Opcional)</label>
            <input type="password" id="close-password" placeholder="Senha gerente">
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
                <td>${m.payment_method || "—"}</td>
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
    if (ok) { 
      await refreshCashBadge(); 
      navigate("pdv"); 
    }
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

async function renderInvoices() {
  els.pageContent.innerHTML = `<div class="empty-state">Carregando Faturamentos...</div>`;
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
            <th>Vencimento</th>
            <th style="text-align:right">Total Devido</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${invoices.map((inv) => `
            <tr>
              <td><strong>${escapeHtml(inv.customer_name)}</strong></td>
              <td>${formatDateTime(inv.first_purchase).split(" ")[0]}</td>
              <td>${formatDateTime(inv.due_date).split(" ")[0]}</td>
              <td style="text-align:right; font-weight:bold; color:var(--danger)">${formatMoney(inv.total)}</td>
              <td style="text-align:right">
                <button class="btn btn-sm btn-primary btn-pay-invoice" data-customer="${escapeHtml(inv.customer_name)}" data-total="${inv.total}">Quitar Dívida</button>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;

  els.pageContent.querySelectorAll(".btn-pay-invoice").forEach((btn) => {
    btn.addEventListener("click", () => {
      openPayInvoiceModal(btn.dataset.customer, Number(btn.dataset.total));
    });
  });
}

function openPayInvoiceModal(customerName, total) {
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = `
    <div class="modal">
      <h3>Quitar Faturamento</h3>
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
    if (ok) {
      close();
      renderInvoices();
    }
  });
}

async function renderReports() {
  const today = new Date().toISOString().slice(0, 10);
  els.pageContent.innerHTML = `
    <div class="card">
      <h3>Relatório por Período</h3>
      <div class="form-row">
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
      <div id="report-result" style="margin-top:16px"></div>
    </div>
  `;

  const loadReport = async () => {
    const startDate = document.getElementById("start-date").value;
    const endDate = document.getElementById("end-date").value;
    const report = await withError(() => endpoints.periodReport(startDate, endDate));
    if (!report) return;
    const methods = Object.entries(report.by_method || {})
      .map(([k, v]) => `<li><span>${k}</span><span>${formatMoney(v)}</span></li>`).join("");
      
    const formatDt = (d) => d.split('-').reverse().join('/');
    
    document.getElementById("report-result").innerHTML = `
      <div class="report-receipt">
        <div class="receipt-header">
          <h2>LarDoceLar</h2>
          <p>Operador do caixa: ${state.user.name} (${state.user.role})</p>
          <p>Vendas de ${formatDt(report.start_date)} até ${formatDt(report.end_date)}</p>
        </div>
        <div class="receipt-body">
          <p><strong>Lançamentos:</strong> ${report.items}</p>
          <p><strong>Total movimentado:</strong> ${formatMoney(report.total)}</p>
          <hr style="border: none; border-top: 1px dashed var(--text-muted); margin: 12px 0;">
          <p style="margin-bottom:8px"><strong>Por método de pagamento:</strong></p>
          <ul>${methods || "<li><span>Nenhum</span><span>—</span></li>"}</ul>
        </div>
        <div class="receipt-footer">
          <p>Gerado em ${new Date().toLocaleString('pt-BR')}</p>
        </div>
      </div>
    `;
  };

  document.getElementById("btn-report").addEventListener("click", loadReport);
  loadReport();
}

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
        <thead><tr><th>ID</th><th>Nome</th><th>Papel</th></tr></thead>
        <tbody>
          ${users.map((u) => `
            <tr><td>${u.id}</td><td>${escapeHtml(u.name)}</td><td>${u.role}</td></tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;

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

function statusBadge(status) {
  const map = {
    ABERTO: "open",
    FECHADO: "closed",
    CANCELADO: "cancel",
  };
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
