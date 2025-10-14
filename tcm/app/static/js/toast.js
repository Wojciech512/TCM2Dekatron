(function () {
  "use strict";

  var container = document.getElementById("toast-container");

  if (!container) {
    return;
  }

  function hideToast(toast) {
    if (!toast) {
      return;
    }

    toast.classList.remove("show");
    toast.addEventListener(
      "transitionend",
      function () {
        toast.remove();
      },
      { once: true }
    );
  }

  function makeToast(data) {
    if (!data) {
      return null;
    }

    var toast = document.createElement("div");
    toast.className = "toast " + (data.type || "info");

    var message = document.createElement("div");
    message.textContent = data.message || "";
    toast.appendChild(message);

    var close = document.createElement("button");
    close.type = "button";
    close.setAttribute("aria-label", "Zamknij powiadomienie");
    close.textContent = "X";
    close.addEventListener("click", function (event) {
      event.preventDefault();
      hideToast(toast);
    });
    toast.appendChild(close);

    container.appendChild(toast);
    requestAnimationFrame(function () {
      toast.classList.add("show");
    });

    var timeout = typeof data.duration === "number" ? data.duration : 4000;
    if (timeout > 0) {
      setTimeout(function () {
        hideToast(toast);
      }, timeout);
    }

    return toast;
  }

  function parseInitialToast(raw) {
    if (!raw) {
      return null;
    }

    try {
      var parsed = JSON.parse(raw);
      return parsed || null;
    } catch (error) {
      console.warn("Nieprawidłowe dane powiadomienia początkowego", error);
      return null;
    }
  }

  window.TCMToast = function (message, options) {
    var data = typeof message === "string" ? { message: message } : message || {};

    if (typeof message === "string" && options) {
      for (var key in options) {
        if (Object.prototype.hasOwnProperty.call(options, key)) {
          data[key] = options[key];
        }
      }
    }

    return makeToast(data);
  };

  var initialData = parseInitialToast(container.getAttribute("data-initial-toast"));
  if (initialData) {
    makeToast(initialData);
  }
})();
