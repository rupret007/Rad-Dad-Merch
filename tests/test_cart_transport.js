#!/usr/bin/env node
"use strict";

// Execute the shipped browser script with synthetic DOM, HTTP and clocks.
// This test never starts a server, sends a request, or submits a hold.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../src/digital_merch/web/static/app.js"), "utf8");
const cases = [];
const test = (name, run) => cases.push({ name, run });
async function settle() { for (let i = 0; i < 15; i += 1) await Promise.resolve(); }
function payload(count = 2) { return { digital_only: true, items: count ? [{ sku: "fixture-study", qty: count }] : [], count }; }

function fixture(options = {}) {
  let document;
  let nextTimer = 1;
  let now = 0;
  const timers = new Map();
  const requests = [];
  const nativeSubmissions = [];
  const imperativeSubmissions = [];
  const serialized = [];
  let reloads = 0;

  class Element {
    constructor(tag = "div", attrs = {}) {
      this.tagName = tag.toUpperCase(); this.attrs = { ...attrs }; this.children = [];
      this.parentNode = null; this.listeners = {}; this._text = ""; this._disabled = Boolean(attrs.disabled);
      this.checked = Boolean(attrs.checked); this.value = attrs.value || "";
      this.classList = {
        add: name => this.setAttribute("class", [this.getAttribute("class") || "", name].join(" ").trim()),
        remove: name => this.setAttribute("class", (this.getAttribute("class") || "").split(/\s+/).filter(value => value !== name).join(" ")),
      };
    }
    get name() { return this.getAttribute("name") || ""; }
    get type() { return this.getAttribute("type") || (this.tagName === "BUTTON" ? "submit" : "text"); }
    get action() { return this.getAttribute("action") || ""; }
    get id() { return this.getAttribute("id") || ""; }
    get href() { return this.getAttribute("href") || ""; }
    set href(value) { this.setAttribute("href", value); }
    get hidden() { return Object.hasOwn(this.attrs, "hidden"); }
    set hidden(value) { if (value) this.setAttribute("hidden", ""); else this.removeAttribute("hidden"); }
    get disabled() { return this._disabled; }
    set disabled(value) {
      this._disabled = Boolean(value);
      if (value && document?.activeElement === this) document.activeElement = document.body;
    }
    get textContent() { return this._text + this.children.map(child => child.textContent).join(""); }
    set textContent(value) { this._text = String(value); this.children = []; }
    set innerHTML(_value) { throw new Error("Status messages must remain text, not parsed HTML"); }
    get elements() { return this.querySelectorAll("input, button, select, textarea"); }
    setAttribute(name, value) { this.attrs[name] = String(value); }
    getAttribute(name) { return Object.hasOwn(this.attrs, name) ? this.attrs[name] : null; }
    removeAttribute(name) { delete this.attrs[name]; }
    appendChild(child) { child.parentNode = this; this.children.push(child); return child; }
    contains(node) { return node === this || this.children.some(child => child.contains(node)); }
    matches(selector) {
      const split = selector.lastIndexOf(" ");
      if (split >= 0) return this.matches(selector.slice(split + 1)) && Boolean(this.parentNode?.closest(selector.slice(0, split)));
      const tag = selector.match(/^[a-z]+/i);
      if (tag && this.tagName !== tag[0].toUpperCase()) return false;
      const id = selector.match(/#([\w-]+)/);
      if (id && this.id !== id[1]) return false;
      for (const match of selector.matchAll(/\[([\w-]+)(?:=["']([^"']*)["'])?\]/g)) {
        if (this.getAttribute(match[1]) === null) return false;
        if (match[2] !== undefined && this.getAttribute(match[1]) !== match[2]) return false;
      }
      return true;
    }
    closest(selector) { return this.matches(selector) ? this : this.parentNode?.closest(selector) || null; }
    querySelectorAll(selectors) {
      const choices = selectors.split(",").map(selector => selector.trim());
      return this.children.flatMap(child => [
        ...(choices.some(selector => child.matches(selector)) ? [child] : []), ...child.querySelectorAll(selectors),
      ]);
    }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
    addEventListener(name, handler) { (this.listeners[name] ||= []).push(handler); }
    focus() {
      if (!this.disabled && !this.closest("[hidden]") && document.body.contains(this)) document.activeElement = this;
    }
    submit() { imperativeSubmissions.push(this.action); }
  }

  const body = new Element("body");
  const meta = new Element("meta", { name: "csrf-token", content: "fixture-csrf-token" });
  const status = body.appendChild(new Element("section", { id: "cart-update-status", hidden: "", tabindex: "-1" }));
  const live = status.appendChild(new Element("p", { id: "live-status", "aria-live": "polite" }));
  const review = status.appendChild(new Element("a", { id: "cart-review-link", href: "/cart", hidden: "" }));
  const count = body.appendChild(new Element("span", { "data-cart-count": "" })); count.textContent = "1";
  const otherCount = body.appendChild(new Element("span", { "data-cart-count": "" })); otherCount.textContent = "1";
  const outside = body.appendChild(new Element("button", { id: "outside-cart", type: "button" }));
  function form(action, fields) {
    const form = body.appendChild(new Element("form", { action, method: "post" }));
    for (const [name, value] of Object.entries(fields)) form.appendChild(new Element("input", { name, value, type: "hidden" }));
    return form;
  }
  const setForm = form("/cart", { csrf: "fixture-csrf-token", action: "set", sku: "fixture-study" });
  const minus = setForm.appendChild(new Element("button", { name: "qty", value: "0", type: "submit" }));
  const plus = setForm.appendChild(new Element("button", { name: "qty", value: "2", type: "submit" }));
  const addForm = form("/cart", { csrf: "fixture-csrf-token", action: "add", sku: "fixture-other", qty: "1" });
  const add = addForm.appendChild(new Element("button", { type: "submit" }));
  const unavailable = addForm.appendChild(new Element("button", { type: "submit", disabled: "disabled" }));
  const checkoutForm = form("/checkout", { csrf: "fixture-csrf-token", action: "request", confirm_digital_hold: "1" });
  const checkout = checkoutForm.appendChild(new Element("button", { type: "submit" }));
  const guardedButtons = [minus, plus, add, unavailable, checkout];
  document = {
    body, activeElement: body,
    getElementById(id) { return body.querySelector("#" + id); },
    querySelector(selector) { return selector === 'meta[name="csrf-token"]' ? meta : body.querySelector(selector); },
    querySelectorAll(selector) { return body.querySelectorAll(selector); },
  };
  class FixtureFormData {
    constructor(form) {
      this.values = form.elements.filter(element => element.name && !element.disabled && element.tagName !== "BUTTON"
        && !["submit", "button"].includes(element.type) && (!["checkbox", "radio"].includes(element.type) || element.checked))
        .map(element => [element.name, element.value]);
      serialized.push({ values: this.values, buttonStates: guardedButtons.map(button => button.disabled) });
    }
    [Symbol.iterator]() { return this.values[Symbol.iterator](); }
  }
  class FixtureAbortController {
    constructor() {
      this.signal = { aborted: false, listeners: [], addEventListener(_name, handler) { this.listeners.push(handler); } };
    }
    abort() { this.signal.aborted = true; this.signal.listeners.forEach(handler => handler()); }
  }
  function fetch(url, init) {
    assert.equal(url, "/api/cart", "Every transport write stays on the existing cart API");
    if (options.fetchThrows) throw new Error("Synchronous fixture transport failure");
    let resolve, reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    requests.push({ url, init, resolve, reject });
    // Deliberately allow late completion after abort, as a committed request or
    // stalled JSON response can outlive cancellation. The UI must keep its hold.
    return promise;
  }
  const setTimeout = (handler, delay) => { const id = nextTimer++; timers.set(id, { handler, at: now + delay }); return id; };
  const clearTimeout = id => timers.delete(id);
  const window = {
    location: { pathname: options.pathname || "/catalog", reload() { reloads += 1; } },
    setTimeout, clearTimeout,
    ...(options.noFetch ? {} : { fetch }),
    ...(options.noAbortController ? {} : { AbortController: FixtureAbortController }),
  };
  const context = vm.createContext({
    document, window, URLSearchParams, FormData: FixtureFormData, setTimeout, clearTimeout,
    ...(options.noFetch ? {} : { fetch }),
    ...(options.noAbortController ? {} : { AbortController: FixtureAbortController }),
  });
  vm.runInContext(source, context, { timeout: 1000 });
  function submit(form = setForm, submitter = plus) {
    const event = { submitter, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } };
    for (const listener of form.listeners.submit || []) listener(event);
    if (!event.defaultPrevented) nativeSubmissions.push(form.action);
    return event;
  }
  return {
    document, status, live, review, count, otherCount, outside, requests, serialized, guardedButtons,
    setForm, plus, minus, addForm, add, checkoutForm, checkout, unavailable,
    nativeSubmissions, imperativeSubmissions, submit, timers,
    get reloads() { return reloads; },
    async respond(httpStatus, body, index = requests.length - 1) {
      requests[index].resolve({ ok: httpStatus >= 200 && httpStatus < 300, status: httpStatus, json: () => Promise.resolve(body) });
      await settle();
    },
    async malformedJson(httpStatus = 200) {
      requests[requests.length - 1].resolve({ ok: httpStatus >= 200 && httpStatus < 300, status: httpStatus, json: () => Promise.reject(new SyntaxError("Invalid fixture JSON")) });
      await settle();
    },
    async reject(error = new TypeError("Fixture connection lost")) { requests[requests.length - 1].reject(error); await settle(); },
    async advance(milliseconds) {
      now += milliseconds;
      for (const [id, timer] of [...timers.entries()].sort((a, b) => a[1].at - b[1].at)) {
        if (timer.at <= now) { timers.delete(id); timer.handler(); }
      }
      await settle();
    },
  };
}

function assertUnlocked(ui) {
  assert.deepEqual(ui.guardedButtons.map(button => button.disabled), [false, false, false, true, false], "Restore each prior disabled state");
}
function assertUnknown(ui) {
  assert.equal(ui.status.hidden, false, "Uncertain outcome remains visible");
  assert.ok(ui.live.textContent.trim(), "A visible explanation accompanies the review link");
  assert.equal(ui.review.hidden, false);
  assert.equal(ui.review.href, "/cart", "Recovery is an explicit existing GET cart page");
  assert.ok(ui.document.activeElement === ui.status, "Move keyboard focus to recovery guidance");
  assert.ok(ui.guardedButtons.every(button => button.disabled));
  assert.equal(ui.count.textContent, "1", "Unknown results never invent a new cart count");
  assert.equal(ui.reloads, 0);
  assert.equal(ui.status.getAttribute("data-state"), "unknown");
  for (const form of [ui.setForm, ui.addForm, ui.checkoutForm]) assert.equal(form.getAttribute("aria-busy"), "false");
  assert.equal(ui.imperativeSubmissions.length, 0, "Never replay a possibly committed write through form.submit");
  const attempts = ui.requests.length;
  assert.equal(ui.submit(ui.addForm, ui.add).defaultPrevented, true);
  assert.equal(ui.submit(ui.checkoutForm, ui.checkout).defaultPrevented, true);
  assert.equal(ui.requests.length, attempts, "Review is required before any further write");
  assert.equal(ui.nativeSubmissions.length, 0);
}

test("serialize the clicked quantity and fields before disabling shared cart controls", async () => {
  const ui = fixture(); ui.plus.focus();
  assert.equal(ui.submit().defaultPrevented, true);
  assert.equal(ui.requests.length, 1);
  const request = ui.requests[0];
  assert.deepEqual(Object.fromEntries(new URLSearchParams(request.init.body)), {
    csrf: "fixture-csrf-token", action: "set", sku: "fixture-study", qty: "2",
  });
  assert.deepEqual(ui.serialized[0].buttonStates, [false, false, false, true, false]);
  assert.equal(request.init.method, "POST");
  assert.equal(request.init.credentials, "same-origin");
  assert.equal(request.init.headers["X-CSRF-Token"], "fixture-csrf-token");
  assert.equal(request.init.headers["Content-Type"], "application/x-www-form-urlencoded");
  assert.equal(request.init.signal.aborted, false);
  assert.ok(ui.guardedButtons.every(button => button.disabled));
  assert.equal(ui.outside.disabled, false);
  assert.equal(ui.status.hidden, false);
  for (const form of [ui.setForm, ui.addForm, ui.checkoutForm]) assert.equal(form.getAttribute("aria-busy"), "true");
  assert.ok(ui.live.textContent.trim());
  assert.equal(ui.review.hidden, true);
  assert.equal(ui.submit().defaultPrevented, true);
  assert.equal(ui.submit(ui.addForm, ui.add).defaultPrevented, true);
  assert.equal(ui.submit(ui.checkoutForm, ui.checkout).defaultPrevented, true);
  assert.equal(ui.requests.length, 1, "One in-flight cart request across all forms");
  assert.equal(ui.nativeSubmissions.length, 0);
});

test("catalog success updates every count, preserves disabled buttons, and restores lost submitter focus", async () => {
  const ui = fixture(); ui.plus.focus(); ui.submit(); await ui.respond(200, payload());
  assertUnlocked(ui);
  assert.equal(ui.count.textContent, "2"); assert.equal(ui.otherCount.textContent, "2");
  assert.equal(ui.status.hidden, false); assert.ok(ui.live.textContent.trim());
  assert.equal(ui.review.hidden, false); assert.equal(ui.review.href, "/cart");
  assert.ok(ui.document.activeElement === ui.plus, "Restore the original button when disabling it lost focus");
  assert.equal(ui.reloads, 0); assert.equal(ui.timers.size, 0);
  assert.equal(ui.submit(ui.addForm, ui.add).defaultPrevented, true);
  assert.equal(ui.requests.length, 2, "Confirmed completion permits a new explicit attempt");
});

test("success does not steal focus after the operator moves elsewhere", async () => {
  const ui = fixture(); ui.plus.focus(); ui.submit(); ui.outside.focus(); await ui.respond(200, payload());
  assert.ok(ui.document.activeElement === ui.outside);
  assertUnlocked(ui);
});

test("implicit submit keeps native form fields without borrowing another submitter", async () => {
  const ui = fixture(); ui.submit(ui.addForm, null);
  const fields = Object.fromEntries(new URLSearchParams(ui.requests[0].init.body));
  assert.equal(fields.action, "add"); assert.equal(fields.qty, "1"); assert.equal(fields.sku, "fixture-other");
  await ui.respond(200, payload()); assertUnlocked(ui);
});

test("a quantity form without a known clicked button preserves native submission", async () => {
  const ui = fixture();
  assert.equal(ui.submit(ui.setForm, null).defaultPrevented, false);
  assert.deepEqual(ui.nativeSubmissions, ["/cart"]);
  assert.equal(ui.requests.length, 0); assert.equal(ui.serialized.length, 0); assertUnlocked(ui);
});

for (const pathname of ["/cart", "/checkout"]) test(pathname + " success reloads the confirmed cart summary once", async () => {
  const ui = fixture({ pathname }); ui.submit(); await ui.respond(200, payload());
  assert.equal(ui.reloads, 1); assert.equal(ui.count.textContent, "2");
  assert.ok(ui.guardedButtons.every(button => button.disabled), "Stale forms stay locked until the new GET page arrives");
  assert.equal(ui.submit(ui.addForm, ui.add).defaultPrevented, true);
  assert.equal(ui.submit(ui.checkoutForm, ui.checkout).defaultPrevented, true);
  assert.equal(ui.requests.length, 1); assert.equal(ui.nativeSubmissions.length, 0);
  assert.equal(ui.imperativeSubmissions.length, 0); assert.equal(ui.timers.size, 0);
});

for (const count of [0, 12]) test("valid boundary count " + count + " is accepted", async () => {
  const ui = fixture(); ui.submit(); await ui.respond(200, payload(count));
  assert.equal(ui.count.textContent, String(count)); assertUnlocked(ui); assert.equal(ui.review.hidden, false);
});

test("a known HTTP 400 rejection is visible text and permits an explicit corrected attempt", async () => {
  const ui = fixture(); ui.submit();
  const error = 'Quantity unavailable. <img src="fixture.invalid" onerror="unsafe()">';
  await ui.respond(400, { ok: false, error });
  assertUnlocked(ui); assert.equal(ui.status.hidden, false); assert.equal(ui.live.textContent, error);
  assert.equal(ui.review.hidden, true); assert.equal(ui.count.textContent, "1"); assert.equal(ui.timers.size, 0);
  ui.submit(); assert.equal(ui.requests.length, 2);
});

test("a blank known HTTP 400 rejection provides visible fallback guidance and unlocks", async () => {
  for (const error of ["", " \t "]) {
    const ui = fixture(); ui.submit(); await ui.respond(400, { ok: false, error });
    assertUnlocked(ui); assert.equal(ui.status.hidden, false);
    assert.equal(ui.live.textContent, "Cart update rejected. Review the quantities and try again.");
    assert.equal(ui.status.getAttribute("data-state"), "error");
    assert.equal(ui.review.hidden, true); assert.equal(ui.count.textContent, "1");
    ui.submit(); assert.equal(ui.requests.length, 2);
  }
});

test("network loss becomes an explicit review hold without replaying the write", async () => {
  const ui = fixture(); ui.submit(); await ui.reject(); assertUnknown(ui);
});

test("a synchronous transport exception also stops without native replay", async () => {
  const ui = fixture({ fetchThrows: true }); ui.submit(); await settle(); assertUnknown(ui);
});

test("a response whose JSON cannot be read requires review", async () => {
  const ui = fixture(); ui.submit(); await ui.malformedJson(); assertUnknown(ui);
});

for (const [name, httpStatus, body] of [
  ["server failure", 500, { ok: false, error: "Try again" }],
  ["unexpected successful status", 201, payload()],
  ["missing rejection receipt", 400, { error: "Missing ok:false" }],
  ["wrong digital-only value", 200, { ...payload(), digital_only: false }],
  ["missing items", 200, { digital_only: true, count: 2 }],
  ["non-array items", 200, { ...payload(), items: {} }],
  ["string count", 200, { ...payload(), count: "2" }],
  ["negative count", 200, { ...payload(), count: -1 }],
  ["too-large count", 200, { ...payload(), count: 13 }],
  ["fractional count", 200, { ...payload(), count: 1.5 }],
  ["null response", 200, null],
]) test(name + " cannot claim the cart was updated", async () => {
  const ui = fixture(); ui.submit(); await ui.respond(httpStatus, body); assertUnknown(ui);
});

test("the ten-second deadline holds the outcome even after a late success arrives", async () => {
  const ui = fixture({ pathname: "/checkout" }); ui.submit();
  await ui.advance(9999); assert.equal(ui.requests[0].init.signal.aborted, false); assert.equal(ui.review.hidden, true);
  await ui.advance(1); assert.equal(ui.requests[0].init.signal.aborted, true); assertUnknown(ui);
  const message = ui.live.textContent;
  await ui.respond(200, payload());
  assertUnknown(ui); assert.equal(ui.live.textContent, message, "A late success must not unlock or reload an uncertain page");
});

test("the deadline covers a stalled JSON body after HTTP headers arrived", async () => {
  const ui = fixture(); ui.submit(); let finishJson;
  ui.requests[0].resolve({ ok: true, status: 200, json: () => new Promise(resolve => { finishJson = resolve; }) });
  await settle(); await ui.advance(10000); assertUnknown(ui);
  finishJson(payload()); await settle(); assertUnknown(ui);
});

for (const capability of ["noFetch", "noAbortController"]) test(capability + " retains the original native form path", async () => {
  const ui = fixture({ [capability]: true });
  assert.equal(ui.submit().defaultPrevented, false);
  assert.deepEqual(ui.nativeSubmissions, ["/cart"]);
  assert.equal(ui.requests.length, 0); assert.equal(ui.serialized.length, 0);
  assertUnlocked(ui); assert.equal(ui.status.hidden, true); assert.equal(ui.review.hidden, true);
});

test("idle checkout continues through its existing native hold confirmation form", async () => {
  const ui = fixture();
  assert.equal(ui.submit(ui.checkoutForm, ui.checkout).defaultPrevented, false);
  assert.deepEqual(ui.nativeSubmissions, ["/checkout"]); assert.equal(ui.requests.length, 0);
});

(async () => {
  let failures = 0;
  for (const { name, run } of cases) {
    try {
      await run();
      console.log("PASS: " + name);
    } catch (error) {
      failures += 1;
      console.error("FAIL: " + name + "\n" + (error.stack || error));
    }
  }
  if (failures) throw new Error(failures + " of " + cases.length + " cart transport cases failed.");
  console.log("Cart transport verified: " + cases.length + " offline browser-state cases passed.");
})().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
