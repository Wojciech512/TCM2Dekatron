# TCM 2.0 → FastAPI Migration Blueprint

## 1. Cel i zakres
Ten dokument opisuje migrację aplikacji TCM 2.0 z Flask do FastAPI wraz z modernizacją bezpieczeństwa, architektury oraz konteneryzacją. Zakres obejmuje przeniesienie istniejącej logiki sterującej, interfejsów użytkownika i API, dodanie trwałego rejestru zdarzeń, wdrożenie TLS/mTLS, uporządkowanie konfiguracji oraz przygotowanie infrastruktury uruchomieniowej na Raspberry Pi.

## 2. Mapowanie routingu Flask → FastAPI
Poniższa tabela utrzymuje 1:1 semantykę endpointów z `app.py` i definiuje odpowiedniki w FastAPI.

| Funkcja (Flask) | Ścieżka | Metoda | Nowy moduł FastAPI | Router FastAPI |
| --- | --- | --- | --- | --- |
| `index` | `/` | GET | `tcm/app/main.py` (Jinja) | `ui_router` |
| `login` | `/login` | GET/POST | `tcm/app/security/routes.py` | `auth_router` |
| `logout` | `/logout` | POST | `tcm/app/security/routes.py` | `auth_router` |
| `panel_operator` | `/panel/operator` | GET | `tcm/app/api/ui.py` | `ui_router` |
| `panel_technik` | `/panel/technik` | GET | `tcm/app/api/ui.py` | `ui_router` |
| `panel_serwis` | `/panel/serwis` | GET/POST | `tcm/app/api/ui.py` | `ui_router` |
| `api_state` | `/api/state` | GET | `tcm/app/api/state.py` | `api_state_router` |
| `api_inputs` | `/api/v1/inputs` | GET | `tcm/app/api/inputs.py` | `api_inputs_router` |
| `api_outputs` | `/api/v1/outputs` | GET/POST | `tcm/app/api/outputs.py` | `api_outputs_router` |
| `api_sensors` | `/api/v1/sensors` | GET | `tcm/app/api/sensors.py` | `api_sensors_router` |
| `trigger_strike` | `/api/v1/strike/<name>/trigger` | POST | `tcm/app/api/strike.py` | `api_strike_router` |
| `download_logs` | `/logs` | GET | `tcm/app/services/logs.py` | `logs_router` |

### Główne zmiany
* FastAPI Application Factory (`tcm/app/main.py`) tworzy obiekt `FastAPI`, rejestruje routery i podłącza sesje z wykorzystaniem middleware Starlette.
* Funkcje renderujące szablony zastąpione `Jinja2Templates` (Starlette).
* Obsługa formularzy wymaga dodania CSRF tokenu podpisanego `SECRET_KEY` (przechowywanego poza repozytorium).
* Logika sterująca działa jako zadanie w tle (BackgroundTask) wystartowane w `startup`.

## 3. Cykl życia i zadania w tle
* **Kontroler sprzętowy** – moduł `tcm/app/core/controller.py` implementuje pętlę logiczną, która:
  * pobiera konfigurację z `ConfigService` i mapowania z bazy/logiki;
  * odczytuje wejścia MCP23S17 oraz czujniki DHT11/DS18B20;
  * steruje przekaźnikami i tranzystorami zgodnie z mapowaniami i trybem manualnym.
* **Taski cykliczne**:
  * szybka pętla (`FAST_EVENTS_TICK_SEC = 0.25s`) monitoruje drzwi i przyciski, aby zapewnić anti-glitch; wartości jak w `app.py`.【F:app.py†L76-L91】
  * pętla logiki (`LOGIC_INTERVAL_SEC = 60s`) wykonuje reguły temperatur i alarmów.【F:app.py†L71-L85】
  * odświeżanie czujników zalania (`FLOOD_REFRESH_SEC = 120s`).【F:app.py†L86-L91】
* Taski korzystają z `asyncio.create_task` z sygnalizacją zatrzymania przy `shutdown`.

## 4. Warstwa sprzętowa / I/O
### Mapowanie kanałów
* **Relays K1..K8** → `MCP23S17 GPIOA` (bity 0..7) z mapowaniem obecnym w `RELAY_PIN_MAP`.【F:app.py†L122-L134】
* **Transistory T1..T8** → `MCP23S17 GPIOB` (bity 0..7) wg `TRANSISTOR_PIN_MAP`.【F:app.py†L113-L121】
* **Wejścia drzwi/zalań** → `GPIOA` bity 0..7 (do 6 drzwi + 2 zalania); anti-glitch bazuje na logice aktualnej pętli.
* **DIP-switch** – `GPIOB` dla wyboru panelu serwisowego.

### Czujniki
* **DHT11** – utrzymać obsługę i piny `DHT_PIN_BATT=4`, `DHT_PIN_CAB=5`.【F:app.py†L39-L44】
* **DS18B20** – opcjonalnie aktywowany w konfiguracji (`config/app.yaml: sensors.ds18b20.enabled`).
* Buzzer na pinie 22 (GPIO).【F:app.py†L35-L43】

### Strike
* Dozwolone tranzystory `T2..T8` zgodnie z `ALLOWED_STRIKE_TRANSISTORS`.【F:app.py†L47-L51】
* Konfiguracja w YAML (`strikes.*.transistor`) z czasem podtrzymania (domyślnie 10 s).

## 5. Logika sterująca
Reguły kopiują aktualne zachowanie:
* Progi temperatur `grzałka`, `klimatyzacja`, `went` + histereza; dostępne do edycji w panelu technika.
* Drzwi otwarte → alarm + światło, wyłączenie grzałki/klimy/wentylatorów (priorytet bezpieczeństwa).
* Zalanie → alarm + powiadomienie.
* Przegrzanie (`temp >= went`) → alarm + aktywacja wentylatorów 48 V i 230 V.
* Tryb ręczny (panel serwis) ze stanami na mapowaniach logicznych do K/T.
* Anti-glitch drzwi i anti-flap dla zalania utrzymają buforowanie stanów jak w oryginalnej pętli.

## 6. Bezpieczeństwo
* **Hashowanie haseł** – Argon2id (`argon2-cffi`) z per-user salt, przechowywane w tabeli `users` (zastępuje sekcję `users` w `config.json`).【F:app.py†L92-L111】
* **Role** – operator, technik, serwis, przechowywane w bazie; autoryzacja w middleware + dekoratory.
* **Sekrety** – `SECRET_KEY`, `FERNET_KEY`, `ADMIN_BOOTSTRAP_HASH` dostarczane jako Docker secrets.
* **Sesje** – Signed/Encrypted cookie (Starlette `SessionMiddleware`) z `max_age` i atrybutami `HttpOnly`, `Secure`, `SameSite='Strict'`; rotacja klucza co 24h przez `KeyManager`.
* **CSRF** – token generowany per-sesja i weryfikowany w formularzach POST.
* **mTLS** – NGINX wymusza klienta z certyfikatu lokalnego CA.

## 7. Baza danych
* Engine: SQLite (opcjonalnie z rozszerzeniem SQLCipher na produkcji).
* Tabele:
  * `users(id, username, password_hash, role, salt, created_at, updated_at, last_login_at, must_rotate)`.
  * `events(id, created_at, type, severity, source, payload_json, encrypted_blob)` – indeks po `created_at` i `type`.
  * `config_snapshots(id, created_at, author_id, diff_json)` – audyt zmian konfiguracji.
* Eksport logów: endpoint generuje plik JSONL; wiersz = `{"ts":..., "type":..., "payload":...}`.
* Szyfrowanie wrażliwych pól (np. `payload_json` dla danych personalnych) przy użyciu `Fernet`.

## 8. Konfiguracja
* `config/app.yaml` przechowuje dane sieciowe, progi, mapowania i interwały.
* Wrażliwe dane (hasła, klucze) przeniesione do `secrets/` (Docker secrets) i `.env`.
* `ConfigService` łączy YAML + secrets + zmienne środowiskowe i weryfikuje schemat (Pydantic Settings).

## 9. Konteneryzacja
* `tcm/docker/app.Dockerfile` – obraz `python:3.12-slim-bookworm`, instalacja zależności z `requirements.txt` + `constraints.txt`, użytkownik `tcm` (UID 1000), `uvicorn` jako entrypoint.
* `tcm/docker/proxy.Dockerfile` – NGINX 1.24 alpine (multi-arch) + certyfikaty.
* `tcm/compose.yaml` – dwie usługi (`reverse-proxy`, `app`), sieci `frontend` (TLS) i `backend`, mount `/dev/spidev*`, `gpio` przez `devices`/`tmpfs`.
* Healthcheck HTTP `/health` (FastAPI) i `CMD curl` w NGINX.
* Logi do stdout + wolumen `logs/` dla SQLite.

## 10. Systemd + automatyczne uruchamianie
* `scripts/install-systemd.sh` instaluje jednostkę `tcm-compose.service` uruchamiającą `docker compose up -d` podczas bootu RPi.
* Jednostka ustawia `Restart=always`, `After=network-online.target`, `Requires=docker.service`.

## 11. CA i mTLS
* `scripts/gen-ca.sh` tworzy lokalny root CA (offline) i intermediate; generuje certyfikaty serwera (`server.local`) i klientów (`operator`, `technik`, `serwis`).
* Certyfikaty klientów wgrywane na urządzenia dostępowe; NGINX weryfikuje `ssl_verify_client on;` i mapuje OU → rola.
* Rotacja: nowe certyfikaty generowane i dystrybuowane, stare unieważniane przez CRL publikowany w NGINX.

## 12. Testy akceptacyjne (wysokopoziomowe)
1. **Logowanie i role** – weryfikacja przekierowań paneli, zmian hasła, wymuszenia rotacji.
2. **Widok I/E/O** – sprawdzenie prezentacji K1..K5, T1, drzwi i zalania.
3. **Alarm drzwi** – symulacja otwarcia drzwi → alarm + światło + wpis logu.
4. **Alarm zalania** – wejście zalania aktywne → alarm i log.
5. **Alarm temperatury** – przegrzanie → wentylatory 48V i 230V aktywne.
6. **Strike** – dostępny tylko gdy przypisany (T2..T8); odmowa 403 gdy brak przypisania.
7. **Brak czujnika** – odłączenie DHT/DS18B20 → wartości `None` i bezpieczny tryb (wyłączenie grzałki/klimy, alarm informacyjny).
8. **mTLS** – połączenie bez certyfikatu klienta → 400/401; z certyfikatem spoza CA → odrzucenie.

## 13. Polityka aktualizacji
* Aktualizacje obrazów poprzez `docker compose pull && docker compose up -d`.
* Zależności Python zamrożone w `requirements.lock`; aktualizacja kwartalna po testach regresyjnych.
* Kopie zapasowe SQLite wykonywane cronem (`sqlite3 .backup`).

