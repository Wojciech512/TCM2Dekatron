# Aplikacja FastAPI

Kod aplikacji znajduje się w katalogu `tcm/app`. Najczęściej edytowane moduły to:

```
tcm/app/
  api/        # endpointy REST
  core/       # konfiguracja, integracje z hardware i pętla sterująca
  security/   # sesje, role, CSRF
  services/   # logi, użytkownicy, obsługa strike
  templates/  # szablony Jinja2
  static/     # pliki statyczne
  main.py     # fabryka aplikacji FastAPI
```

Aplikację uruchamiasz wyłącznie przez Docker Compose:

- `make dev` → tryb developerski z autoreloadem (`tcm/compose.dev.yaml`).
- `make prod` → tryb produkcyjny (`tcm/compose.yaml`).

Sekrety (`app_secret_key`, `app_fernet_key`, `admin_bootstrap_hash`) powinny znajdować się w wolumenie `/var/lib/tcm/secrets` lub zostać wygenerowane wcześniej poleceniem `python tcm/scripts/generate_secrets.py`.
