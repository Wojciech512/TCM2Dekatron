interface StrikeResponse {
  active_until?: number | null;
}

function handleButtonClick(button: HTMLButtonElement): void {
  const endpoint = button.getAttribute("data-strike-endpoint");
  if (!endpoint) {
    return;
  }

  const label = button.getAttribute("data-strike-label") ?? "STRIKE";
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
      return response.json() as Promise<StrikeResponse>;
    })
    .then((payload) => {
      const until =
        payload && payload.active_until
          ? new Date(payload.active_until * 1000).toLocaleString()
          : null;
      const message = until
        ? `${label} wyzwolony. Aktywny do: ${until}.`
        : `${label} wyzwolony.`;
      window.TCMToast?.(message, { type: "success" });
    })
    .catch((error: Response | unknown) => {
      const message = `${label} — nie udało się wyzwolić.`;

      if (error instanceof Response && typeof error.json === "function") {
        error
          .json()
          .then((body: { detail?: string; message?: string } | null) => {
            const detail = body?.detail ?? body?.message;
            window.TCMToast?.(detail ? `${message} ${detail}` : message, {
              type: "error",
              duration: 6000,
            });
          })
          .catch(() => {
            window.TCMToast?.(message, { type: "error", duration: 6000 });
          });
      } else {
        window.TCMToast?.(message, { type: "error", duration: 6000 });
      }
    })
    .finally(() => {
      button.disabled = false;
    });
}

function initOperatorPanel(): void {
  const buttons = document.querySelectorAll<HTMLButtonElement>("[data-strike-endpoint]");
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
} else {
  initOperatorPanel();
}

export {};
