(() => {
  interface StrikeSuccessResponse {
    active_until?: number | null;
  }

  const formatUntil = (value: number | null | undefined): string | null => {
    if (typeof value !== "number") {
      return null;
    }

    const date = new Date(value * 1000);
    return Number.isNaN(date.getTime()) ? null : date.toLocaleString();
  };

  const handleButtonClick = (button: HTMLButtonElement): void => {
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
        return response.json() as Promise<StrikeSuccessResponse>;
      })
      .then((payload) => {
        const until = formatUntil(payload?.active_until ?? null);
        const message = until
          ? `${label} wyzwolony. Aktywny do: ${until}.`
          : `${label} wyzwolony.`;
        window.TCMToast?.(message, { type: "success" });
      })
      .catch((error: unknown) => {
        if (!window.TCMToast) {
          return;
        }

        const baseMessage = `${label} — nie udało się wyzwolić.`;

        if (error instanceof Response) {
          error
            .json()
            .then((body: unknown) => {
              if (typeof body === "object" && body !== null) {
                const detail =
                  (body as { detail?: string; message?: string }).detail ??
                  (body as { detail?: string; message?: string }).message;
                window.TCMToast?.(
                  detail ? `${baseMessage} ${detail}` : baseMessage,
                  { type: "error", duration: 6000 }
                );
                return;
              }

              window.TCMToast?.(baseMessage, { type: "error", duration: 6000 });
            })
            .catch(() => {
              window.TCMToast?.(baseMessage, { type: "error", duration: 6000 });
            });
        } else {
          window.TCMToast(baseMessage, { type: "error", duration: 6000 });
        }
      })
      .finally(() => {
        button.disabled = false;
      });
  };

  const init = (): void => {
    const buttons = document.querySelectorAll<HTMLButtonElement>(
      "[data-strike-endpoint]"
    );

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
  } else {
    init();
  }
})();
