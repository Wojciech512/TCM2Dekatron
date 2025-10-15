function parseDoorChannels(raw) {
    if (!raw) {
        return [];
    }
    try {
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
    }
    catch (error) {
        console.warn("Nie można sparsować konfiguracji kanałów drzwi", error);
        return [];
    }
}
function initDashboard() {
    const configElement = document.getElementById("dashboard-config");
    if (!(configElement instanceof HTMLElement)) {
        return;
    }
    const refreshUrlAttr = configElement.getAttribute("data-refresh-url");
    if (!refreshUrlAttr) {
        return;
    }
    const refreshUrl = refreshUrlAttr;
    const doorChannels = parseDoorChannels(configElement.getAttribute("data-door-channels"));
    const refreshState = async () => {
        try {
            const response = await fetch(refreshUrl, { cache: "no-store" });
            if (!response.ok) {
                return;
            }
            const data = (await response.json());
            if (data.inputs) {
                Object.entries(data.inputs).forEach(([channel, value]) => {
                    const element = document.querySelector(`[data-input="${channel}"]`);
                    if (!element) {
                        return;
                    }
                    const isDoor = doorChannels.includes(channel);
                    if (isDoor) {
                        element.textContent = value ? "OPEN" : "CLOSED";
                        element.classList.toggle("bad", Boolean(value));
                        element.classList.toggle("ok", !value);
                    }
                    else {
                        element.textContent = value ? "FLOOD" : "OK";
                        element.classList.toggle("bad", Boolean(value));
                        element.classList.toggle("ok", !value);
                    }
                });
            }
            if (data.outputs) {
                Object.entries(data.outputs).forEach(([name, active]) => {
                    const element = document.querySelector(`[data-output="${name}"]`);
                    if (!element) {
                        return;
                    }
                    element.textContent = active ? "ON" : "OFF";
                    element.classList.toggle("on", Boolean(active));
                    element.classList.toggle("off", !active);
                });
            }
            if (data.sensors) {
                Object.entries(data.sensors).forEach(([sensorName, sensorValue]) => {
                    const element = document.querySelector(`[data-sensor="${sensorName}"]`);
                    if (!element) {
                        return;
                    }
                    element.textContent =
                        sensorValue === null || sensorValue === undefined ? "—" : String(sensorValue);
                });
            }
        }
        catch (error) {
        }
    };
    const REFRESH_INTERVAL = 15000;
    let refreshTimer;
    const scheduleRefresh = (delay = REFRESH_INTERVAL) => {
        if (refreshTimer !== undefined) {
            window.clearTimeout(refreshTimer);
        }
        refreshTimer = window.setTimeout(async () => {
            if (document.hidden) {
                scheduleRefresh();
                return;
            }
            await refreshState();
            scheduleRefresh();
        }, delay);
    };
    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) {
            refreshState().finally(() => scheduleRefresh());
        }
    });
    refreshState().finally(() => scheduleRefresh(REFRESH_INTERVAL));
}
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDashboard, { once: true });
}
else {
    initDashboard();
}
export {};
