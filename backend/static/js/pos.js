/* eslint-env browser */
(function () {
  "use strict";

  const TAX_RATE = parseFloat(window.RMS_TAX_RATE || "0.14");
  const root = document.getElementById("pos-root");
  if (!root) return;

  const data = JSON.parse(document.getElementById("pos-data").textContent);
  // data = { categories: [{id, slug, name}], items: [{id, name, price, image_url, category_slug, modifier_groups: [...]}], tables: [{id, number}] }

  const state = {
    cart: [],          // [{ menuItemId, name, unitPrice, quantity, modifiers: [{optionId, name, priceDelta}], lineKey }]
    type: "dine_in",
    tableId: null,
    customerPhone: "",
    deliveryAddress: "",
    activeCategory: data.categories[0] ? data.categories[0].slug : null,
  };

  const $ = (sel) => root.querySelector(sel);

  function fmt(n) { return n.toFixed(2); }

  function lineSubtotal(line) {
    const modSum = line.modifiers.reduce((s, m) => s + parseFloat(m.priceDelta), 0);
    return (parseFloat(line.unitPrice) + modSum) * line.quantity;
  }

  function totals() {
    const sub = state.cart.reduce((s, l) => s + lineSubtotal(l), 0);
    const tax = sub * TAX_RATE;
    return { sub, tax, total: sub + tax };
  }

  function renderCategories() {
    const c = $(".pos-categories");
    c.innerHTML = "";
    data.categories.forEach((cat) => {
      const b = document.createElement("button");
      b.className = "pos-cat-btn" + (cat.slug === state.activeCategory ? " is-active" : "");
      b.textContent = cat.name;
      b.onclick = () => { state.activeCategory = cat.slug; renderAll(); };
      c.appendChild(b);
    });
  }

  function renderItems() {
    const grid = $(".pos-items");
    grid.innerHTML = "";
    data.items
      .filter((i) => i.category_slug === state.activeCategory)
      .forEach((it) => {
        const card = document.createElement("div");
        card.className = "pos-item";
        const img = it.image_url || "";
        card.innerHTML = `
          ${img ? `<img src="${img}" alt="">` : `<div style="height:80px;background:#eee;border-radius:4px"></div>`}
          <div class="name">${it.name}</div>
          <div class="price">${fmt(parseFloat(it.price))} EGP</div>`;
        card.onclick = () => addItem(it);
        grid.appendChild(card);
      });
  }

  function addItem(it) {
    if (it.modifier_groups && it.modifier_groups.length > 0) {
      openModifierPicker(it);
    } else {
      pushLine(it, []);
    }
  }

  function pushLine(it, mods) {
    const lineKey = `${it.id}::${mods.map((m) => m.optionId).sort().join(",")}`;
    const existing = state.cart.find((l) => l.lineKey === lineKey);
    if (existing) {
      existing.quantity += 1;
    } else {
      state.cart.push({
        menuItemId: it.id,
        name: it.name,
        unitPrice: it.price,
        quantity: 1,
        modifiers: mods,
        lineKey,
      });
    }
    renderCart();
  }

  function openModifierPicker(it) {
    const modal = $(".pos-modifier-modal");
    const panel = modal.querySelector(".panel");
    const chosen = {};
    let html = `<h5>${it.name}</h5>`;
    it.modifier_groups.forEach((g) => {
      html += `<div style="margin-top:.5rem"><strong>${g.name}${g.is_required ? " *" : ""}</strong></div>`;
      g.options.forEach((o) => {
        const id = `mod-${g.id}-${o.id}`;
        const inputType = g.max_select === 1 ? "radio" : "checkbox";
        html += `<label style="display:block"><input type="${inputType}" name="g${g.id}" value="${o.id}" id="${id}"> ${o.name} (+${fmt(parseFloat(o.price_delta))})</label>`;
      });
      chosen[g.id] = { group: g, picked: [] };
    });
    html += `<div style="margin-top:1rem;text-align:right"><button class="btn btn-secondary" id="modal-cancel">Cancel</button> <button class="btn btn-primary" id="modal-add">Add</button></div>`;
    panel.innerHTML = html;
    modal.classList.remove("hidden");

    panel.querySelectorAll("input").forEach((inp) => {
      inp.addEventListener("change", () => {
        const groupId = parseInt(inp.name.slice(1), 10);
        const optId = parseInt(inp.value, 10);
        const slot = chosen[groupId];
        if (slot.group.max_select === 1) {
          slot.picked = [optId];
        } else if (inp.checked) {
          slot.picked.push(optId);
        } else {
          slot.picked = slot.picked.filter((x) => x !== optId);
        }
      });
    });

    panel.querySelector("#modal-cancel").onclick = () => modal.classList.add("hidden");
    panel.querySelector("#modal-add").onclick = () => {
      const mods = [];
      for (const slot of Object.values(chosen)) {
        if (slot.group.is_required && slot.picked.length === 0) {
          alert(`Please pick a ${slot.group.name}.`);
          return;
        }
        slot.picked.forEach((optId) => {
          const opt = slot.group.options.find((o) => o.id === optId);
          mods.push({ optionId: optId, name: opt.name, priceDelta: opt.price_delta });
        });
      }
      modal.classList.add("hidden");
      pushLine(it, mods);
    };
  }

  function renderCart() {
    const lines = $(".pos-cart-lines");
    lines.innerHTML = "";
    state.cart.forEach((line, idx) => {
      const div = document.createElement("div");
      div.className = "pos-line";
      const modText = line.modifiers.map((m) => m.name).join(", ");
      div.innerHTML = `
        <div class="row1"><span>${line.name}</span><span>${fmt(lineSubtotal(line))}</span></div>
        ${modText ? `<div class="modifiers">${modText}</div>` : ""}
        <div class="qty">
          <button data-act="dec" data-idx="${idx}">−</button>
          <span>${line.quantity}</span>
          <button data-act="inc" data-idx="${idx}">+</button>
          <button data-act="rm" data-idx="${idx}" style="margin-left:auto">×</button>
        </div>`;
      lines.appendChild(div);
    });
    lines.querySelectorAll("button").forEach((b) => {
      b.onclick = () => {
        const i = parseInt(b.dataset.idx, 10);
        if (b.dataset.act === "inc") state.cart[i].quantity++;
        if (b.dataset.act === "dec" && state.cart[i].quantity > 1) state.cart[i].quantity--;
        if (b.dataset.act === "rm") state.cart.splice(i, 1);
        renderCart();
      };
    });
    const t = totals();
    $(".pos-totals .sub-val").textContent = fmt(t.sub);
    $(".pos-totals .tax-val").textContent = fmt(t.tax);
    $(".pos-totals .total-val").textContent = fmt(t.total);
  }

  function renderTypeTabs() {
    root.querySelectorAll(".pos-type-btn").forEach((b) => {
      b.classList.toggle("is-active", b.dataset.type === state.type);
      b.onclick = () => { state.type = b.dataset.type; renderTypeFields(); };
    });
    renderTypeFields();
  }

  function renderTypeFields() {
    $(".pos-table-wrap").style.display = state.type === "dine_in" ? "block" : "none";
    $(".pos-phone-wrap").style.display = state.type !== "dine_in" ? "block" : "none";
    $(".pos-address-wrap").style.display = state.type === "delivery" ? "block" : "none";
  }

  function csrfToken() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : "";
  }

  async function confirm() {
    if (state.cart.length === 0) { alert("Cart is empty."); return; }
    if (state.type === "dine_in") state.tableId = parseInt($("select[name='table']").value, 10);
    state.customerPhone = $("input[name='phone']").value;
    state.deliveryAddress = $("textarea[name='address']").value;

    const body = {
      type: state.type,
      table: state.tableId,
      customer_phone: state.customerPhone,
      delivery_address: state.deliveryAddress,
      items: state.cart.map((l) => ({
        menu_item: l.menuItemId,
        quantity: l.quantity,
        modifiers: l.modifiers.map((m) => m.optionId),
      })),
    };

    const btn = $("#pos-confirm");
    btn.disabled = true;
    try {
      const resp = await fetch("/cashier/orders/create/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        credentials: "same-origin",
        body: JSON.stringify(body),
      });
      const json = await resp.json();
      if (resp.ok) {
        window.location.href = json.redirect;
      } else {
        alert("Error: " + (json.error || resp.statusText));
        btn.disabled = false;
      }
    } catch (e) {
      alert("Network error: " + e);
      btn.disabled = false;
    }
  }

  function renderAll() {
    renderCategories();
    renderItems();
    renderCart();
  }

  renderTypeTabs();
  renderAll();
  $("#pos-confirm").onclick = confirm;
})();
