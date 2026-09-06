(function () {
  var live = document.getElementById("live-status");
  var status = document.getElementById("cart-update-status");
  var review = document.getElementById("cart-review-link");
  var csrfMeta = document.querySelector('meta[name="csrf-token"]');
  if (!csrfMeta || !live || !status || !review) return;

  var state = "idle";
  var activeRequest = null;
  var savedButtons = [];
  var forms = document.querySelectorAll('form[action="/cart"], form[action="/checkout"]');

  function announce(message, outcome, needsReview) {
    status.hidden = false;
    status.setAttribute("data-state", outcome);
    live.textContent = message;
    review.hidden = !needsReview;
  }

  function focusStatus() {
    status.focus();
  }

  function lockButtons() {
    savedButtons = [];
    document.querySelectorAll('form[action="/cart"] button, form[action="/checkout"] button').forEach(function (button) {
      savedButtons.push({ button: button, disabled: button.disabled });
      button.disabled = true;
    });
    forms.forEach(function (form) { form.setAttribute("aria-busy", "true"); });
  }

  function finish(request, nextState) {
    if (activeRequest !== request) return false;
    clearTimeout(request.timer);
    activeRequest = null;
    state = nextState;
    forms.forEach(function (form) { form.setAttribute("aria-busy", "false"); });
    if (state === "idle") {
      savedButtons.forEach(function (saved) { saved.button.disabled = saved.disabled; });
    }
    return true;
  }

  function uncertain(request) {
    if (!finish(request, "unknown")) return;
    announce("We couldn't confirm that cart change. Review your current hold cart before editing or requesting a hold. The change was not sent again.", "unknown", true);
    focusStatus();
  }

  document.querySelectorAll('form[action="/checkout"]').forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (state !== "idle") {
        event.preventDefault();
        focusStatus();
      }
    });
  });

  document.querySelectorAll('form[action="/cart"]').forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (state !== "idle") {
        event.preventDefault();
        focusStatus();
        return;
      }
      // Without the enhancement, native forms preserve the clicked button.
      if (!window.fetch || !window.AbortController) return;
      if (!event.submitter && form.querySelector('button[name="qty"]')) return;

      var data = new URLSearchParams(new FormData(form));
      var submitter = event.submitter;
      if (submitter && submitter.name) data.set(submitter.name, submitter.value);
      event.preventDefault();
      state = "pending";
      lockButtons();
      announce("Updating your hold cart. Please wait before making another change.", "pending", false);
      var request = { controller: new window.AbortController(), timer: null };
      activeRequest = request;
      request.timer = setTimeout(function () {
        // Aborting a response cannot prove the server did not apply the POST.
        uncertain(request);
        request.controller.abort();
      }, 10000);

      var responsePromise;
      try {
        responsePromise = fetch("/api/cart", {
          method: "POST",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRF-Token": csrfMeta.getAttribute("content") || ""
          },
          body: data.toString(),
          credentials: "same-origin",
          signal: request.controller.signal
        });
      } catch (error) {
        uncertain(request);
        return;
      }
      responsePromise
        .then(function (response) {
          return response.json().then(function (payload) {
            return { ok: response.ok, code: response.status, payload: payload };
          });
        })
        .then(function (result) {
          if (activeRequest !== request) return;
          var payload = result.payload;
          if (!result.ok && result.code === 400 && payload && payload.ok === false && typeof payload.error === "string") {
            finish(request, "idle");
            announce(payload.error.trim() || "Cart update rejected. Review the quantities and try again.", "error", false);
            focusStatus();
            return;
          }
          if (!result.ok || result.code !== 200 || !payload || payload.digital_only !== true || !Array.isArray(payload.items) ||
              !Number.isInteger(payload.count) || payload.count < 0 || payload.count > 12) {
            uncertain(request);
            return;
          }
          var refreshCart = window.location.pathname === "/cart" || window.location.pathname === "/checkout";
          finish(request, refreshCart ? "refreshing" : "idle");
          document.querySelectorAll("[data-cart-count]").forEach(function (node) {
            node.textContent = String(payload.count);
          });
          announce("Hold cart updated. Nothing was charged, printed, or posted.", "success", true);
          if (refreshCart) {
            window.location.reload();
          } else if (submitter && document.activeElement === document.body) {
            submitter.focus();
          }
        })
        .catch(function () { uncertain(request); });
    });
  });
})();
