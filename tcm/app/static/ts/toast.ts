interface ToastPayload {
  message: string;
  type?: string;
  duration?: number;
}

interface ToastOptions {
  type?: string;
  duration?: number;
}

function hideToast(toast: HTMLElement | null): void {
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
}

function parseInitialToast(raw: string | null): ToastPayload | null {
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as ToastPayload | null;
    return parsed ?? null;
  } catch (error) {
    console.warn("Nieprawidłowe dane powiadomienia początkowego", error);
    return null;
  }
}

function initToastSystem(): void {
  const container = document.getElementById("toast-container");
  if (!(container instanceof HTMLElement)) {
    return;
  }

  const makeToast = (data: ToastPayload | null): HTMLElement | null => {
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
    close.addEventListener("click", (event: MouseEvent) => {
      event.preventDefault();
      hideToast(toast);
    });
    toast.appendChild(close);

    container.appendChild(toast);
    window.requestAnimationFrame(() => {
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

  window.TCMToast = (message: string | ToastPayload, options?: ToastOptions) => {
    const data: ToastPayload =
      typeof message === "string" ? { message } : { ...(message ?? { message: "" }) };

    if (typeof message === "string" && options) {
      Object.assign(data, options);
    }

    return makeToast(data);
  };

  const initialData = parseInitialToast(container.getAttribute("data-initial-toast"));
  if (initialData) {
    makeToast(initialData);
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initToastSystem, { once: true });
} else {
  initToastSystem();
}

export {};
