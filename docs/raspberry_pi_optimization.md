# Optymalizacja aplikacji FastAPI na Raspberry Pi 3

Poniższe wskazówki pozwalają ograniczyć zużycie pamięci RAM, CPU i przestrzeni flash podczas uruchamiania aplikacji FastAPI + Jinja2 + Tailwind w docker-compose na Raspberry Pi 3 (1 GB RAM, ~100 MB wolnej pamięci flash).

## 1. Multi-stage Docker build i minimalne obrazy

### `Dockerfile` aplikacji (`app/Dockerfile`)
```dockerfile
# --- Stage 1: build frontendu ---
FROM node:20-alpine AS frontend
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY tailwind.config.js tsconfig.json ./
COPY src ./src
RUN npm run build && \
    npm run tailwind:build

# --- Stage 2: runtime ---
FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# Zainstaluj systemowe zależności wymagane przez aplikację
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsqlite3-0 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --from=frontend /build/dist ./static
COPY --from=frontend /build/tailwind.css ./static/css/tailwind.css
COPY app ./app

# Usuń cache pip i pliki tymczasowe
RUN find /root/.cache -type f -delete || true

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-server-header", "--log-level", "warning", "--timeout-keep-alive", "10"]
```

### `Dockerfile` proxy (`proxy/Dockerfile`)
```dockerfile
FROM nginx:1.25-alpine
COPY proxy/nginx.conf /etc/nginx/nginx.conf
```

* Multi-stage build usuwa Node.js z finalnego obrazu.
* `python:3.11-slim` i `nginx:alpine` minimalizują rozmiar warstw.
* `pip install --no-cache-dir` i czyszczenie cache zmniejszają finalny rozmiar.

## 2. Konfiguracja `docker-compose.yml`

```yaml
version: "3.9"
services:
  app:
    build:
      context: .
      dockerfile: app/Dockerfile
    environment:
      UVICORN_LOG_LEVEL: warning
    command: >-
      uvicorn app.main:app
      --host 0.0.0.0
      --port 8000
      --workers 1
      --no-server-header
      --log-level warning
      --timeout-keep-alive 10
      --limit-concurrency 10
    restart: unless-stopped
    mem_limit: 300m
    cpus: "0.6"
    volumes:
      - app-data:/data
      - type: tmpfs
        target: /tmp
        tmpfs:
          size: 64M
  proxy:
    build:
      context: .
      dockerfile: proxy/Dockerfile
    ports:
      - "443:443"
    depends_on:
      - app
    restart: unless-stopped
    volumes:
      - ./proxy/certs:/etc/nginx/certs:ro
      - ./static:/usr/share/nginx/html:ro
      - type: tmpfs
        target: /var/log/nginx
        tmpfs:
          size: 16M
volumes:
  app-data:
```

* Limituj pamięć i CPU kontenerów, by uniknąć swapowania.
* Montuj katalogi logów i `/tmp` na `tmpfs`, aby zmniejszyć zapis na flash.
* Udostępnij katalog statyczny Nginxowi jako `read-only`.

## 3. Konfiguracja Nginx (`proxy/nginx.conf`)

```nginx
user  nginx;
worker_processes  1;
error_log  /var/log/nginx/error.log warn;
pid        /var/run/nginx.pid;

worker_rlimit_nofile 1024;

events {
    worker_connections  256;
    multi_accept on;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    sendfile      on;
    tcp_nodelay   on;
    keepalive_timeout  15;
    types_hash_max_size 2048;

    log_format minimal '$remote_addr $status $body_bytes_sent $request_time';
    access_log off;

    server {
        listen 443 ssl http2;
        ssl_certificate     /etc/nginx/certs/fullchain.pem;
        ssl_certificate_key /etc/nginx/certs/privkey.pem;
        ssl_session_cache   shared:SSL:1m;
        ssl_session_timeout 1h;

        client_body_buffer_size 8k;
        client_max_body_size    2m;

        location /static/ {
            root /usr/share/nginx/html;
            expires 30d;
            add_header Cache-Control "public, max-age=2592000, immutable";
        }

        location / {
            proxy_pass         http://app:8000;
            proxy_http_version 1.1;
            proxy_set_header   Host $host;
            proxy_set_header   X-Real-IP $remote_addr;
            proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header   X-Forwarded-Proto $scheme;
            proxy_read_timeout 30s;
            proxy_connect_timeout 5s;
            proxy_send_timeout 30s;
        }
    }
}
```

* `access_log off` i niski poziom logów ograniczają zapis.
* Bezpośrednie serwowanie `/static/` omija backend.
* Krótkie timeouty i niewielkie bufory ograniczają zużycie pamięci.

## 4. Ustawienia FastAPI/Uvicorn

### `app/main.py`
```python
import logging

from fastapi import FastAPI
from .db import get_connection

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.WARNING)

app = FastAPI(docs_url=None, redoc_url=None)

@app.on_event("startup")
async def on_startup() -> None:
    conn = get_connection()
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA auto_vacuum=INCREMENTAL;")
    conn.commit()
```

### Minimalny worker Gunicorna (opcjonalnie)
Jeżeli wymagany jest Gunicorn:
```bash
gunicorn app.main:app \
    --bind 0.0.0.0:8000 \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 1 \
    --access-logfile - \
    --error-logfile - \
    --log-level warning \
    --timeout 30 \
    --graceful-timeout 15
```

## 5. Dostęp do SQLite

### Połączenie z bazą (`app/db.py`)
```python
import sqlite3
from pathlib import Path

DB_PATH = Path("/data/app.db")

_CONNECTION = None

def get_connection() -> sqlite3.Connection:
    global _CONNECTION
    if _CONNECTION is None:
        _CONNECTION = sqlite3.connect(DB_PATH, check_same_thread=False)
        _CONNECTION.row_factory = sqlite3.Row
        _CONNECTION.execute("PRAGMA journal_mode=WAL;")
        _CONNECTION.execute("PRAGMA synchronous=NORMAL;")
        _CONNECTION.execute("PRAGMA temp_store=MEMORY;")
        _CONNECTION.execute("PRAGMA cache_size=-20000;")  # ~20 MB w RAM
        _CONNECTION.execute("PRAGMA busy_timeout=2000;")
        _CONNECTION.commit()
    return _CONNECTION


def vacuum_incremental(pages: int = 100) -> None:
    conn = get_connection()
    conn.execute("PRAGMA incremental_vacuum(%d);" % pages)
    conn.commit()
```

### Okresowe czyszczenie (`app/tasks.py`)
```python
import asyncio
import logging

from .db import vacuum_incremental

logger = logging.getLogger(__name__)

async def maintenance_loop() -> None:
    while True:
        await asyncio.sleep(3600)
        try:
            vacuum_incremental()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Incremental vacuum failed: %s", exc)
```
Uruchom `maintenance_loop` jako tło podczas startu aplikacji.

## 6. Redukcja obciążenia front-endu

### `tailwind.config.js`
```js
module.exports = {
  content: [
    "./app/templates/**/*.html",
    "./app/static/**/*.js"
  ],
  theme: {
    extend: {}
  },
  corePlugins: {
    container: false,
  },
  plugins: [],
};
```

### Komendy npm
```json
{
  "scripts": {
    "tailwind:build": "npx tailwindcss -m -i ./src/styles.css -o ./dist/tailwind.css --minify",
    "build": "vite build --emptyOutDir"
  }
}
```

* `content` ogranicza CSS do używanych klas.
* Minifikacja i rezygnacja z niepotrzebnych pluginów zmniejsza rozmiar statycznych plików.
* Preferuj prosty layout w HTML bez JS lub tylko z natywnym JS.

## 7. Logi i trwałość danych

* Ustaw `logging.handlers.BufferingHandler` w Pythonie, aby flush następował np. co 100 wpisów.
* Skonfiguruj rotację logów:

```conf
/var/log/app/app.log {
    size 512k
    rotate 4
    compress
    missingok
    notifempty
}
```

* Regularnie eksportuj bazę:

```bash
sqlite3 /data/app.db \
  '.backup "/media/usb/app-$(date +%F).db"'
```

* Usuwaj stare wpisy w tle:

```sql
DELETE FROM measurements WHERE created_at < datetime('now', '-90 days');
```

## 8. Minimalizacja żądań i polling

* Zastąp polling wykorzystaniem Server-Sent Events:

```python
from fastapi import Request
from fastapi.responses import EventSourceResponse

@app.get("/events")
async def events(request: Request) -> EventSourceResponse:
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            payload = await get_payload()
            yield {"event": "update", "data": payload}
            await asyncio.sleep(10)
    return EventSourceResponse(event_generator())
```

* Jeżeli polling jest konieczny, zwiększ interwał do ≥10 s.

Stosując powyższe zmiany ograniczysz wielkość obrazów Docker, zużycie RAM/CPU i liczbę zapisów na pamięć flash, co pozwoli stabilnie uruchomić aplikację na Raspberry Pi 3.
