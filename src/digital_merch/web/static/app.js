(function () {
  var live = document.getElementById("live-status");
  var csrfMeta = document.querySelector('meta[name="csrf-token"]');
  if (!csrfMeta || !live) {
    return;
  }

  function announce(message) {
    live.textContent = message;
  }

  function refreshCount(count) {
    document.querySelectorAll("[data-cart-count]").forEach(function (node) {
      node.textContent = String(count);
    });
  }

  document.querySelectorAll('form[action="/cart"]').forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.fetch) {
        return;
      }
      event.preventDefault();
      var data = new URLSearchParams(new FormData(form));
      if (event.submitter && event.submitter.name) {
        data.set(event.submitter.name, event.submitter.value);
      }
      fetch("/api/cart", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "X-CSRF-Token": csrfMeta.getAttribute("content") || ""
        },
        body: data.toString(),
        credentials: "same-origin"
      })
        .then(function (response) {
          return response.json().then(function (payload) {
            return { ok: response.ok, payload: payload };
          });
        })
        .then(function (result) {
          if (!result.ok) {
            announce(result.payload.error || "Cart update failed.");
            return;
          }
          refreshCount(result.payload.count || 0);
          announce("Digital study hold cart updated. Nothing was charged, printed, or posted.");
          if (window.location.pathname === "/cart") {
            window.location.reload();
          }
        })
        .catch(function () {
          form.submit();
        });
    });
  });
})();
