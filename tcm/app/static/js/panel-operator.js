function handleButtonClick(button) {
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
        var _a;
        const until = payload && payload.active_until
            ? new Date(payload.active_until * 1000).toLocaleString()
            : null;
        const message = until
            ? `${label} wyzwolony. Aktywny do: ${until}.`
            : `${label} wyzwolony.`;
        (_a = window.TCMToast) === null || _a === void 0 ? void 0 : _a.call(window, message, { type: "success" });
    })
        .catch((error) => {
        var _a;
        const message = `${label} — nie udało się wyzwolić.`;
        if (error instanceof Response && typeof error.json === "function") {
            error
                .json()
                .then((body) => {
                var _a, _b;
                const detail = (_a = body === null || body === void 0 ? void 0 : body.detail) !== null && _a !== void 0 ? _a : body === null || body === void 0 ? void 0 : body.message;
                (_b = window.TCMToast) === null || _b === void 0 ? void 0 : _b.call(window, detail ? `${message} ${detail}` : message, {
                    type: "error",
                    duration: 6000,
                });
            })
                .catch(() => {
                var _a;
                (_a = window.TCMToast) === null || _a === void 0 ? void 0 : _a.call(window, message, { type: "error", duration: 6000 });
            });
        } else {
          window.TCMToast(message, { type: "error", duration: 6000 });
        }
        else {
            (_a = window.TCMToast) === null || _a === void 0 ? void 0 : _a.call(window, message, { type: "error", duration: 6000 });
        }
    })
        .finally(() => {
        button.disabled = false;
    });
}
function initOperatorPanel() {
    const buttons = document.querySelectorAll("[data-strike-endpoint]");
    if (!buttons.length) {
        return;
    }
    buttons.forEach((button) => {
        button.addEventListener("click", () => {
            handleButtonClick(button);
        });
    });
}
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initOperatorPanel, { once: true });
}
else {
    initOperatorPanel();
}
export {};
