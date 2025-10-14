(() => {
  const container = document.getElementById("toast-container");
  if (!(container instanceof HTMLElement)) {
    return;
  }

  type ToastElement = HTMLDivElement;

  const hideToast = (toast: ToastElement | null): void => {
    if (!toast) {
      return;
    }

    toast.classList.remove("show");
    toast.addEventListener(
      "transitionend",
      () => {
        toast.remove();
      },
      { once: true }
    );
  };

  const makeToast = (data: TCMToastOptions | null): ToastElement | null => {
    if (!data) {
      return null;
    }

    const toast = document.createElement("div");
    toast.className = `toast ${data.type ?? "info"}`;

    const message = document.createElement("div");
    message.textContent = data.message ?? "";
    toast.appendChild(message);

    const close = document.createElement("button");
    close.type = "button";
    close.setAttribute("aria-label", "Zamknij powiadomienie");
    close.textContent = "X";
    close.addEventListener("click", (event) => {
      event.preventDefault();
      hideToast(toast);
    });
    toast.appendChild(close);

    container.appendChild(toast);
    requestAnimationFrame(() => {
      toast.classList.add("show");
    });

    const timeout = typeof data.duration === "number" ? data.duration : 4000;
    if (timeout > 0) {
      window.setTimeout(() => {
        hideToast(toast);
      }, timeout);
    }

    return toast;
  };

  const parseInitialToast = (raw: string | null): TCMToastOptions | null => {
    if (!raw) {
      return null;
    }

    try {
      const parsed = JSON.parse(raw) as TCMToastOptions | null;
      return parsed ?? null;
    } catch (error) {
      console.warn("Nieprawidłowe dane powiadomienia początkowego", error);
      return null;
    }
  };

  const showToast = (
    message: TCMToastInput,
    options?: TCMToastOptions
  ): ToastElement | null => {
    const data: TCMToastOptions =
      typeof message === "string" ? { message } : { ...(message ?? {}) };

    if (typeof message === "string" && options) {
      Object.assign(data, options);
    }

    return makeToast(data);
  };

  window.TCMToast = showToast;

  const initialData = parseInitialToast(container.getAttribute("data-initial-toast"));
  if (initialData) {
    makeToast(initialData);
  }
})();
