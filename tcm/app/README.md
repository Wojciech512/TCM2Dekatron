# Struktura aplikacji FastAPI

```
tcm/app/
  api/          # Routery FastAPI (state, inputs, outputs, sensors, strike, ui)
  core/         # Warstwa sprzętowa i pętla sterująca
  security/     # Autoryzacja, sesje, CSRF, role
  services/     # Dostęp do bazy, konfiguracji, logów, strike
  templates/    # Szablony Jinja2
  static/       # Zasoby front-end (CSS/JS)
  main.py       # Fabryka aplikacji + rejestracja background tasków
```

Moduły `api`, `core`, `security` i `services` korzystają z `ConfigService`, który scala konfigurację YAML + secrets. Zadania w tle rejestrują się w `startup` i kończą w `shutdown` z wykorzystaniem flag `asyncio.Event`.
