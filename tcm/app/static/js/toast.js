"use strict";
(() => {
    const container = document.getElementById("toast-container");
    if (!(container instanceof HTMLElement)) {
        return;
    }
    const hideToast = (toast) => {
        if (!toast) {
            return;
        }
        toast.classList.remove("show");
        toast.addEventListener("transitionend", () => {
            toast.remove();
        }, { once: true });
    };
    const makeToast = (data) => {
        var _a, _b;
        if (!data) {
            return null;
        }
        const toast = document.createElement("div");
        toast.className = `toast ${(_a = data.type) !== null && _a !== void 0 ? _a : "info"}`;
        const message = document.createElement("div");
        message.textContent = (_b = data.message) !== null && _b !== void 0 ? _b : "";
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
    const parseInitialToast = (raw) => {
        if (!raw) {
            return null;
        }
        try {
            const parsed = JSON.parse(raw);
            return parsed !== null && parsed !== void 0 ? parsed : null;
        }
        catch (error) {
            console.warn("Nieprawidłowe dane powiadomienia początkowego", error);
            return null;
        }
    };
    const showToast = (message, options) => {
        const data = typeof message === "string" ? { message } : { ...(message !== null && message !== void 0 ? message : {}) };
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
