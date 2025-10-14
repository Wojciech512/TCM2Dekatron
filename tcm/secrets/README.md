# Sekrety aplikacji

`make prod` oczekuje, że pliki z sekretami będą dostępne w wolumenie `/var/lib/tcm/secrets` (albo zostaną wygenerowane przy pierwszym uruchomieniu kontenera).

Minimalny zestaw plików:

- `app_secret_key`
- `app_fernet_key`
- `admin_bootstrap_hash`

Aby przygotować je z wyprzedzeniem, uruchom:

```bash
python tcm/scripts/generate_secrets.py
```

Skrypt tworzy pliki w `tcm/secrets/`, ustawia odpowiednie uprawnienia i może przyjąć hasło administratora z argumentu `--admin-password`. Przy migracji do środowiska docelowego skopiuj pliki na docelowy wolumen lub ustaw zmienną `TCM_ADMIN_BOOTSTRAP_PASSWORD`, aby kontener wygenerował hash samodzielnie.
