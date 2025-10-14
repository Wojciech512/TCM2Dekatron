"use strict";
(() => {
    const formatUntil = (value) => {
        if (typeof value !== "number") {
            return null;
        }
        const date = new Date(value * 1000);
        return Number.isNaN(date.getTime()) ? null : date.toLocaleString();
    };
    const handleButtonClick = (button) => {
        var _a;
        const endpoint = button.getAttribute("data-strike-endpoint");
        if (!endpoint) {
            return;
        }
        const label = (_a = button.getAttribute("data-strike-label")) !== null && _a !== void 0 ? _a : "STRIKE";
        button.disabled = true;
        fetch(endpoint, {
            method: "GET",
            credentials: "same-origin",
            headers: {
                Accept: "application/json",
            },
        })
            .then((response) => {
            if (!response.ok) {
                throw response;
            }
            return response.json();
        })
            .then((payload) => {
            var _a, _b;
            const until = formatUntil((_a = payload === null || payload === void 0 ? void 0 : payload.active_until) !== null && _a !== void 0 ? _a : null);
            const message = until
                ? `${label} wyzwolony. Aktywny do: ${until}.`
                : `${label} wyzwolony.`;
            (_b = window.TCMToast) === null || _b === void 0 ? void 0 : _b.call(window, message, { type: "success" });
        })
            .catch((error) => {
            if (!window.TCMToast) {
                return;
            }
            const baseMessage = `${label} — nie udało się wyzwolić.`;
            if (error instanceof Response) {
                error
                    .json()
                    .then((body) => {
                    var _a, _b, _c;
                    if (typeof body === "object" && body !== null) {
                        const detail = (_a = body.detail) !== null && _a !== void 0 ? _a : body.message;
                        (_b = window.TCMToast) === null || _b === void 0 ? void 0 : _b.call(window, detail ? `${baseMessage} ${detail}` : baseMessage, { type: "error", duration: 6000 });
                        return;
                    }
                    (_c = window.TCMToast) === null || _c === void 0 ? void 0 : _c.call(window, baseMessage, { type: "error", duration: 6000 });
                })
                    .catch(() => {
                    var _a;
                    (_a = window.TCMToast) === null || _a === void 0 ? void 0 : _a.call(window, baseMessage, { type: "error", duration: 6000 });
                });
            }
            else {
                window.TCMToast(baseMessage, { type: "error", duration: 6000 });
            }
        })
            .finally(() => {
            button.disabled = false;
        });
    };
    const init = () => {
        const buttons = document.querySelectorAll("[data-strike-endpoint]");
        if (!buttons.length) {
            return;
        }
        buttons.forEach((button) => {
            button.addEventListener("click", () => {
                handleButtonClick(button);
            });
        });
    };
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init, { once: true });
    }
    else {
        init();
    }
})();
