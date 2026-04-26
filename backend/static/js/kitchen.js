/* eslint-env browser */
(function () {
  "use strict";

  const root = document.getElementById("kitchen-root");
  if (!root) return;

  const initialOrders = JSON.parse(document.getElementById("kitchen-orders-data").textContent);
  const wsBase = document.body.dataset.wsBase || `ws://${location.hostname}:19000`;
  const wsUrl = `${wsBase}/ws/kds/`;

  const grid = document.getElementById("kitchen-grid");
  const ordersByUuid = new Map();

  initialOrders.forEach((o) => ordersByUuid.set(o.uuid, o));
  render();

  function render() {
    grid.innerHTML = "";
    if (ordersByUuid.size === 0) {
      grid.innerHTML = '<p class="text-muted">No active orders.</p>';
      return;
    }
    const sorted = [...ordersByUuid.values()].sort((a, b) =>
      (a.created_at || "").localeCompare(b.created_at || "")
    );
    sorted.forEach((o) => grid.appendChild(card(o)));
  }

  function card(o) {
    const div = document.createElement("div");
    div.className = "col-md-4";
    div.dataset.uuid = o.uuid;
    const border = o.status === "preparing" ? "warning" : (o.status === "ready" ? "success" : "primary");
    const lines = (o.items || []).map((it) => {
      const mods = (it.modifiers && it.modifiers.length) ? ` — ${it.modifiers.join(", ")}` : "";
      const notes = it.notes ? `<div class="text-info">📝 ${it.notes}</div>` : "";
      return `<li>${it.quantity}× ${it.name}${mods}${notes}</li>`;
    }).join("");
    let buttonHtml = "";
    if (o.status === "confirmed") {
      buttonHtml = '<button name="status" value="preparing" class="btn btn-sm btn-warning">Start preparing</button>';
    } else if (o.status === "preparing") {
      buttonHtml = '<button name="status" value="ready" class="btn btn-sm btn-success">Mark ready</button>';
    } else if (o.status === "ready") {
      buttonHtml = '<button name="status" value="served" class="btn btn-sm btn-secondary">Mark served</button>';
    }

    const csrfInput = document.querySelector("[name=csrfmiddlewaretoken]");
    const csrf = csrfInput ? csrfInput.value : "";
    div.innerHTML = `
      <div class="card border-${border}">
        <div class="card-body">
          <h5 class="card-title">${o.number} — ${o.order_type}</h5>
          <p class="card-subtitle text-muted small">${o.status} · live</p>
          <ul class="list-unstyled small mt-2 mb-2">${lines}</ul>
          <form method="post" action="/kitchen/orders/${o.uuid}/status/">
            <input type="hidden" name="csrfmiddlewaretoken" value="${csrf}">
            ${buttonHtml}
          </form>
        </div>
      </div>`;
    return div;
  }

  function applyEvent(evt) {
    if (evt.event === "order.new") {
      ordersByUuid.set(evt.payload.uuid, evt.payload);
      render();
    } else if (evt.event === "order.updated") {
      const existing = ordersByUuid.get(evt.payload.uuid);
      if (evt.payload.status === "served" || evt.payload.status === "cancelled") {
        ordersByUuid.delete(evt.payload.uuid);
      } else if (existing) {
        ordersByUuid.set(evt.payload.uuid, { ...existing, ...evt.payload });
      } else {
        ordersByUuid.set(evt.payload.uuid, evt.payload);
      }
      render();
    }
  }

  let ws = null;
  let attempts = 0;

  function connect() {
    ws = new WebSocket(wsUrl);
    ws.onopen = () => {
      attempts = 0;
      const banner = document.getElementById("ws-banner");
      if (banner) banner.textContent = "🟢 live";
    };
    ws.onmessage = (e) => {
      try {
        const evt = JSON.parse(e.data);
        applyEvent(evt);
      } catch (_) { /* ignore non-JSON */ }
    };
    ws.onclose = () => {
      const banner = document.getElementById("ws-banner");
      if (banner) banner.textContent = "🔴 reconnecting…";
      attempts++;
      const delay = Math.min(30000, 500 * Math.pow(2, attempts));
      setTimeout(connect, delay);
    };
    ws.onerror = () => { try { ws.close(); } catch (_) {} };
  }

  connect();
})();
