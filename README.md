# Plan migracji TCM 2.0 do FastAPI

Repozytorium zawiera dokumentację i artefakty konfiguracyjne wymagane do migracji aplikacji TCM 2.0 na FastAPI z Jinja2 oraz konteneryzacją w Docker Compose.

## Kluczowe dokumenty
* `docs/migration_blueprint.md` – główny plan migracji, architektura, bezpieczeństwo, testy.
* `tcm/config/app.yaml` – przykładowa konfiguracja YAML bez sekretów.
* `tcm/compose.yaml` – definicja stosu Docker Compose (aplikacja + reverse proxy).
* `tcm/docker/*.Dockerfile` – obrazy aplikacji i reverse proxy.
* `tcm/deploy/ca/README.md` – procedura CA i mTLS.
* `tcm/scripts/*.sh` – generowanie CA i instalacja systemd.

## Kolejne kroki
1. Zaimplementować moduły FastAPI w strukturze `tcm/app/` zgodnie z blueprintem.
2. Przenieść logikę sterowania z `app.py` do `tcm/app/core/`.
3. Przygotować migracje bazy SQLite (SQLAlchemy + Alembic) dla tabel użytkowników i logów.
4. Zintegrować CSRF, sesje i kontrolę dostępu na poziomie routerów.
5. Utworzyć testy e2e zgodnie z opisem w `tcm/tests/e2e/README.md`.
