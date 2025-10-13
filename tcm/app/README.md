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

`main.py` ładuje konfigurację YAML (`tcm/config/app.yaml`), sekrety z wolumenu `/var/lib/tcm/secrets` lub zmiennych środowisk i przygotowuje:

* `HardwareInterface` obsługujący MCP23S17 (z symulacją gdy brak bibliotek RPi),
* `ControlLoop` uruchamiany jako background task (pętle: szybka i logiki),
* serwisy `EventLogger`, `UserStore` (SQLite) oraz `StrikeService` (sterowanie elektrozaczepami),
* warstwę webową (sesje, CSRF, szablony, rate limiting via SlowAPI).

Panele Operator/Technik/Serwis renderowane są z danych runtime (`GLOBAL_STATE`) i konfiguracji.

## Dziennik zdarzeń

* Interfejs webowy udostępnia stronę `/logs` z paginacją i filtrowaniem według typu zdarzenia.
* Eksport do PDF dostępny jest z poziomu UI oraz endpointu `/logs/export/pdf`.
* Liczbę rekordów na stronę można ustawić przez zmienną `TCM_LOGS_PAGE_SIZE` (domyślnie 10).
* Ograniczenie rozmiaru dziennika ustawia `TCM_LOGS_MAX_RECORDS` (domyślnie 5000 wpisów, starsze rekordy są rotowane).
