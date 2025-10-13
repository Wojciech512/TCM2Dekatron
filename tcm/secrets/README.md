# Docker secrets (nie commitować prawdziwych wartości)

W produkcji pliki są zapisywane w wolumenie kontenera pod `/var/lib/tcm/secrets`. Brakujące wartości zostaną wygenerowane automatycznie podczas startu aplikacji (na podstawie zmiennej `TCM_ADMIN_BOOTSTRAP_PASSWORD`).

* `app_secret_key` – 64 losowe bajty (hex/base64) dla podpisywania sesji i CSRF.
* `app_fernet_key` – klucz Fernet (32 bajty base64) do szyfrowania logów.
* `admin_bootstrap_hash` – hasz Argon2 domyślnego konta administratora.

Generator znajdujący się w repozytorium ułatwia automatyczne tworzenie tych plików:

```bash
python tcm/scripts/generate_secrets.py
```

Domyślnie pliki są zapisywane w `tcm/secrets/`. Skrypt poprosi o hasło dla konta administratora (lub przyjmie je z opcji `--admin-password`), a następnie utworzy wymagane pliki z prawami `600`. Flaga `--print` pozwala wypisać wartości na stdout, a `--force` nadpisać istniejące pliki.

Pliki w repozytorium mogą zawierać tylko instrukcje – bez sekretów.
