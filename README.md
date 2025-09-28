# Plan migracji TCM 2.0 do FastAPI

Repozytorium zawiera kompletną implementację aplikacji TCM 2.0 w FastAPI z Jinja2, wraz z dokumentacją i artefaktami konfiguracyjnymi dla docelowego wdrożenia w Docker Compose.

## Kluczowe dokumenty
* `docs/migration_blueprint.md` – główny plan migracji, architektura, bezpieczeństwo, testy.
* `tcm/config/app.yaml` – przykładowa konfiguracja YAML bez sekretów.
* `tcm/compose.yaml` – definicja stosu Docker Compose (aplikacja + reverse proxy).
* `tcm/docker/*.Dockerfile` – obrazy aplikacji i reverse proxy.
* `tcm/deploy/ca/README.md` – procedura CA i mTLS.
* `tcm/scripts/*.sh` – generowanie CA i instalacja systemd.

## Uruchomienie lokalne (tryb developerski)
1. Zainstaluj zależności: `pip install -r requirements.txt`.
2. Ustaw zmienne środowiskowe lub pliki secrets (`TCM_SECRET_KEY`, `TCM_FERNET_KEY`, `TCM_ADMIN_HASH`, `TCM_DB_PATH`).
3. Uruchom aplikację: `uvicorn tcm.app.main:app --reload`.
4. Interfejs WWW będzie dostępny pod `https://localhost:8000` (za reverse proxy w produkcji).

W kontenerach stosuj `tcm/compose.yaml`, który uruchamia usługę FastAPI i reverse proxy NGINX z TLS/mTLS.
