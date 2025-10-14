"use strict";
(() => {
    const parseDoorChannels = (raw) => {
        if (!raw) {
            return [];
        }
        try {
            const parsed = JSON.parse(raw);
            return Array.isArray(parsed) ? parsed.filter((item) => typeof item === "string") : [];
        }
        catch (error) {
            console.warn("Nie można sparsować konfiguracji kanałów drzwi", error);
            return [];
        }
    };
    const updateInputElement = (element, value, isDoor) => {
        const isActive = Boolean(value);
        if (isDoor) {
            element.textContent = isActive ? "OPEN" : "CLOSED";
            element.classList.toggle("bad", isActive);
            element.classList.toggle("ok", !isActive);
        }
        else {
            element.textContent = isActive ? "FLOOD" : "OK";
            element.classList.toggle("bad", isActive);
            element.classList.toggle("ok", !isActive);
        }
    };
    const updateOutputElement = (element, active) => {
        const isActive = Boolean(active);
        element.textContent = isActive ? "ON" : "OFF";
        element.classList.toggle("on", isActive);
        element.classList.toggle("off", !isActive);
    };
    const updateSensorElement = (element, value) => {
        element.textContent = value === null || value === undefined ? "—" : String(value);
    };
    const init = () => {
        const configElement = document.getElementById("dashboard-config");
        if (!(configElement instanceof HTMLElement)) {
            return;
        }
        const refreshUrl = configElement.getAttribute("data-refresh-url");
        if (!refreshUrl) {
            return;
        }
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
                        updateInputElement(element, value, isDoor);
                    });
                }
                if (data.outputs) {
                    Object.entries(data.outputs).forEach(([name, active]) => {
                        const element = document.querySelector(`[data-output="${name}"]`);
                        if (!element) {
                            return;
                        }
                        updateOutputElement(element, active);
                    });
                }
                if (data.sensors) {
                    Object.entries(data.sensors).forEach(([sensorName, sensorValue]) => {
                        const element = document.querySelector(`[data-sensor="${sensorName}"]`);
                        if (!element) {
                            return;
                        }
                        updateSensorElement(element, sensorValue);
                    });
                }
            }
            catch (error) {
                // ignorujemy przejściowe błędy
            }
        };
        window.setInterval(() => {
            void refreshState();
        }, 5000);
        void refreshState();
    };
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init, { once: true });
    }
    else {
        init();
    }
})();
