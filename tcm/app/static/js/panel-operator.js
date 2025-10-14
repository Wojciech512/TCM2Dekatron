(function () {
  "use strict";

  function handleButtonClick(button) {
    var endpoint = button.getAttribute("data-strike-endpoint");
    if (!endpoint) {
      return;
    }

    var label = button.getAttribute("data-strike-label") || "STRIKE";
    button.disabled = true;

    fetch(endpoint, {
      method: "GET",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
      },
    })
      .then(function (response) {
        if (!response.ok) {
          throw response;
        }
        return response.json();
      })
      .then(function (payload) {
        var until =
          payload && payload.active_until
            ? new Date(payload.active_until * 1000).toLocaleString()
            : null;
        var message = until
          ? label + " wyzwolony. Aktywny do: " + until + "."
          : label + " wyzwolony.";
        if (window.TCMToast) {
          window.TCMToast(message, { type: "success" });
        }
      })
      .catch(function (error) {
        if (!window.TCMToast) {
          return;
        }

        var message = label + " — nie udało się wyzwolić.";
        if (error && typeof error.json === "function") {
          error
            .json()
            .then(function (body) {
              var detail = body && (body.detail || body.message);
              window.TCMToast(detail ? message + " " + detail : message, {
                type: "error",
                duration: 6000,
              });
            })
            .catch(function () {
              window.TCMToast(message, { type: "error", duration: 6000 });
            });
        } else {
          window.TCMToast(message, { type: "error", duration: 6000 });
        }
      })
      .finally(function () {
        button.disabled = false;
      });
  }

  function init() {
    var buttons = document.querySelectorAll("[data-strike-endpoint]");
    if (!buttons.length) {
      return;
    }

    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
        handleButtonClick(button);
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
