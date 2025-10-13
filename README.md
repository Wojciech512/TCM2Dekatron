# Plan migracji TCM 2.0 do FastAPI

Repozytorium zawiera kompletną implementację aplikacji TCM 2.0 w FastAPI z Jinja2, wraz z dokumentacją i artefaktami konfiguracyjnymi dla docelowego wdrożenia w Docker Compose.

## Kluczowe dokumenty
* `docs/migration_blueprint.md` – główny plan migracji, architektura, bezpieczeństwo, testy.
* `tcm/config/app.yaml` – przykładowa konfiguracja YAML bez sekretów.
* `tcm/compose.yaml` – definicja stosu Docker Compose (aplikacja + reverse proxy).
* `tcm/docker/*.Dockerfile` – obrazy aplikacji i reverse proxy.
* `tcm/deploy/ca/README.md` – procedura CA i mTLS.
* `tcm/scripts/*.sh` – 
* CA i instalacja systemd.

## Uruchomienie lokalne (tryb developerski)

### Kontener Docker z trybem developerskim
1. Zbuduj obrazy: `docker compose -f tcm/compose.yaml build`.
2. Uruchom środowisko z autoreloadem: `docker compose -f tcm/compose.yaml -f tcm/compose.dev.yaml up app`.
   - Plik `tcm/compose.dev.yaml` ustawia `TCM_APP_MODE=development` i montuje katalog `tcm/app` z repozytorium, więc każda zmiana kodu lub szablonów jest przeładowywana w kontenerze.
   - Domyślnie aplikacja startuje w trybie produkcyjnym; tryb developerski trzeba świadomie włączyć poprzez dodatkowy plik Compose lub ustawienie `TCM_APP_MODE=development`.

Ustaw zmienne środowiskowe lub pliki secrets (`TCM_SECRET_KEY`, `TCM_FERNET_KEY`, `TCM_ADMIN_HASH`, `TCM_DB_PATH`).

W repozytorium dostępny jest skrypt automatyzujący generowanie plików Docker secrets:

```bash
python tcm/scripts/generate_secrets.py
```

Skrypt wygeneruje klucze (`app_secret_key`, `app_fernet_key`) oraz poprosi o hasło dla konta administratora, tworząc hasz Argon2 (`admin_bootstrap_hash`). W przypadku potrzeby ręcznej generacji wartości można nadal użyć poleceń `python -c`:

* `TCM_ADMIN_HASH=...`: `python -c "from passlib.hash import argon2; print(argon2.using(type='ID', rounds=3, memory_cost=65536, parallelism=2).hash('twoje_hasło'))"`
* `TCM_FERNET_KEY=...`: `python -c "import os,base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"`
* `TCM_SECRET_KEY=...`: `python -c "import secrets; print(secrets.token_hex(64))"`

## Tryb aplikacji sterowany zmienną środowiskową

Kontener aplikacyjny honoruje zmienną `TCM_APP_MODE`:

* `production` (domyślnie) – uruchamia Uvicorn bez autoreloadu i z konfiguracją bezpieczną dla środowisk docelowych.
* `development` – włącza autoreload i logowanie na poziomie `debug`, przeznaczone do pracy lokalnej.

Wartość można nadać przez `.env`, `docker compose` (`-e TCM_APP_MODE=development`) albo dodatkowy plik Compose (`tcm/compose.dev.yaml`). Nieprawidłowa wartość spowoduje przerwanie startu kontenera.

W kontenerach stosuj `tcm/compose.yaml`, który uruchamia usługę FastAPI i reverse proxy NGINX z TLS/mTLS.

## Formatowanie i linting

### Python

Zainstaluj zależności deweloperskie: `pip install -r requirements-dev.txt -c constraints.txt`.

* Formatowanie: `black tcm`
* Sortowanie importów: `isort tcm`
* Linting: `flake8 tcm`

### Szablony i zasoby statyczne

Zainstaluj narzędzia Node: `npm install`.

* Sprawdzenie formatowania: `npm run lint`
* Formatowanie: `npm run format`

Prettier korzysta z pluginu `prettier-plugin-jinja-template`, dzięki czemu formatuje pliki Jinja2 (`*.html`, `*.jinja`, `*.j2`).
