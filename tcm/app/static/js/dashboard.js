(function () {
  "use strict";

  function parseDoorChannels(raw) {
    if (!raw) {
      return [];
    }

    try {
      var parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      console.warn("Nie można sparsować konfiguracji kanałów drzwi", error);
      return [];
    }
  }

  function init() {
    var configElement = document.getElementById("dashboard-config");
    if (!configElement) {
      return;
    }

    var refreshUrl = configElement.getAttribute("data-refresh-url");
    if (!refreshUrl) {
      return;
    }

    var doorChannels = parseDoorChannels(
      configElement.getAttribute("data-door-channels")
    );

    async function refreshState() {
      try {
        var response = await fetch(refreshUrl, { cache: "no-store" });
        if (!response.ok) {
          return;
        }

        var data = await response.json();
        if (data.inputs) {
          Object.entries(data.inputs).forEach(function (_ref) {
            var channel = _ref[0];
            var value = _ref[1];
            var element = document.querySelector('[data-input="' + channel + '"]');
            if (!element) {
              return;
            }

            var isDoor = doorChannels.indexOf(channel) !== -1;
            if (isDoor) {
              element.textContent = value ? "OPEN" : "CLOSED";
              element.classList.toggle("bad", !!value);
              element.classList.toggle("ok", !value);
            } else {
              element.textContent = value ? "FLOOD" : "OK";
              element.classList.toggle("bad", !!value);
              element.classList.toggle("ok", !value);
            }
          });
        }

        if (data.outputs) {
          Object.entries(data.outputs).forEach(function (_ref2) {
            var name = _ref2[0];
            var active = _ref2[1];
            var element = document.querySelector('[data-output="' + name + '"]');
            if (!element) {
              return;
            }

            element.textContent = active ? "ON" : "OFF";
            element.classList.toggle("on", !!active);
            element.classList.toggle("off", !active);
          });
        }

        if (data.sensors) {
          Object.entries(data.sensors).forEach(function (_ref3) {
            var sensorName = _ref3[0];
            var sensorValue = _ref3[1];
            var element = document.querySelector(
              '[data-sensor="' + sensorName + '"]'
            );
            if (!element) {
              return;
            }

            element.textContent =
              sensorValue === null || sensorValue === undefined
                ? "—"
                : sensorValue;
          });
        }
      } catch (error) {
        // ignorujemy przejściowe błędy
      }
    }

    setInterval(refreshState, 5000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
