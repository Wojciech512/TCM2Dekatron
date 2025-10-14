# TCM 2.0 na FastAPI

Repozytorium zawiera kompletną aplikację TCM 2.0 (backend FastAPI + reverse proxy NGINX) wraz z narzędziami do generowania certyfikatów i uruchamiania środowisk w Docker Compose.

## Wymagania

- Docker z Compose v2
- `make`
- (opcjonalnie) Python 3.11+ do skryptów pomocniczych

## Generowanie certyfikatów i sekretów

1. **Certyfikaty mTLS** – uruchom `make ca`. Polecenie wywołuje `tcm/scripts/gen-ca.sh`, tworzy kompletny zestaw lokalnego CA i kopiuje certyfikaty do `tcm/deploy/reverse-proxy/certs/`. Gotowa paczka kliencka `client-universal.tar.gz` zawiera certyfikat współdzielony przez Operatora, Technika i Serwis.
2. **Sekrety aplikacji** – w razie potrzeby uruchom `python tcm/scripts/generate_secrets.py`, aby przygotować pliki w `tcm/secrets/` lub wypisać wartości i przenieść je do docelowego wolumenu (`/var/lib/tcm/secrets`). Skrypt poprosi o hasło administracyjne i wygeneruje `app_secret_key`, `app_fernet_key` oraz `admin_bootstrap_hash`.

## Uruchomienie w trybie developerskim

```bash
make dev
```

Target buduje wymagane obrazy i uruchamia `docker compose` z plikiem `tcm/compose.dev.yaml`. Kontener aplikacji startuje w trybie `development` (autoreload, logi `debug`) i montuje katalog `tcm/app`, dzięki czemu zmiany w kodzie są natychmiast widoczne.

## Uruchomienie w trybie produkcyjnym

```bash
make prod
```

Target w razie potrzeby automatycznie generuje certyfikaty (`make ca`), a następnie buduje i podnosi usługę według `tcm/compose.yaml`. Aplikacja działa w trybie `production`. Po starcie możesz śledzić logi poleceniem `make logs`.

## Przydatne dodatkowe polecenia

- `make clean-ca` – usuwa wygenerowane certyfikaty, aby rozpocząć proces od nowa.
- `docker compose -f tcm/compose.yaml down` – zatrzymanie środowiska produkcyjnego.
- `docker compose -f tcm/compose.dev.yaml down` – zatrzymanie środowiska developerskiego.

## Gdzie szukać kolejnych informacji

- `tcm/deploy/ca/README.md` – skrócona procedura CA i opis artefaktów.
- `tcm/app/README.md` – struktura katalogów aplikacji.
- `docs/migration_blueprint.md` – szczegółowy plan migracji i architektury.
