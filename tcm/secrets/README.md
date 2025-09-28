# Docker secrets (nie commitować prawdziwych wartości)

W produkcji pliki powinny być generowane podczas wdrożenia i kopiowane do `/run/secrets/` przez Docker:

* `app_secret_key` – 64 losowe bajty (hex/base64) dla podpisywania sesji i CSRF.
* `app_fernet_key` – klucz Fernet (32 bajty base64) do szyfrowania logów.
* `admin_bootstrap_hash` – hasz Argon2 domyślnego konta administratora.

Pliki w repozytorium mogą zawierać tylko instrukcje – bez sekretów.
