# Struktura aplikacji FastAPI

```
tcm/app/
  api/          # Routery FastAPI (state, v1 endpoints)
  core/         # Warstwa sprzętowa, konfiguracja i pętla sterująca
  security/     # Autoryzacja, sesje, CSRF, role
  services/     # Rejestr zdarzeń, użytkownicy, strike
  templates/    # Szablony Jinja2 (dashboard + panele)
  static/       # Zasoby front-end (CSS)
  main.py       # Fabryka aplikacji + rejestracja background tasków
```

`main.py` ładuje konfigurację YAML (`tcm/config/app.yaml`), sekrety z Docker secrets lub zmiennych środowisk i przygotowuje:

* `HardwareInterface` obsługujący MCP23S17 (z symulacją gdy brak bibliotek RPi),
* `ControlLoop` uruchamiany jako background task (pętle: szybka i logiki),
* serwisy `EventLogger`, `UserStore` (SQLite) oraz `StrikeService` (sterowanie elektrozaczepami),
* warstwę webową (sesje, CSRF, szablony, rate limiting via SlowAPI).

Panele Operator/Technik/Serwis renderowane są z danych runtime (`GLOBAL_STATE`) i konfiguracji.
