# Plan wdrożenia TCM 2.0

Dokument opisuje w prosty sposób, co już zostało przygotowane oraz jakie kroki są jeszcze przed nami, aby uruchomić system TCM 2.0 od podstaw. Zestawiono to tak, by osoby nietechniczne mogły łatwo śledzić postęp.

## Jak czytać statusy
- ✅ **Zrobione** – element gotowy do odbioru.
- ⏳ **Do zrobienia** – zadanie zaplanowane, czeka na realizację.

## Serwisy
### app (kontener z aplikacją)
- ✅ Ustalono listę funkcji, które aplikacja musi obsłużyć.
- ⏳ Przygotowanie kontenera z aplikacją (budowanie obrazu, konfiguracja środowiska).
- ⏳ Ustalenie sposobu przechowywania konfiguracji (sekrety, zmienne środowiskowe).
- ⏳ Przygotowanie procesu uruchomienia i monitoringu aplikacji w środowisku docelowym.

### reverse proxy (NGINX)
- ✅ Określono, że reverse proxy ma obsłużyć HTTPS i przekierowania do aplikacji.
- ⏳ Przygotowanie konfiguracji NGINX (certyfikaty, reguły przekierowań, ograniczenia dostępu do paneli).
- ⏳ Testy komunikacji pomiędzy reverse proxy a aplikacją.

## Frontend (interfejs użytkownika)
- ✅ Zdefiniowano trzy główne panele: Operator, Technik, Serwis.
- ⏳ Zaprojektowanie układu ekranów i nawigacji (dashboard, menu, widoki szczegółowe).
- ⏳ Przygotowanie warstwy wizualnej (kolory alarmów, czytelne opisy w języku polskim).
- ⏳ Zapewnienie automatycznego odświeżania stanów wejść/wyjść oraz wyświetlania logów.
- ⏳ Testy użyteczności z docelowymi użytkownikami.

## Backend (monolit aplikacyjny)
- ✅ Zebrano wymagania dotyczące logiki urządzenia i dostępów użytkowników.
- ⏳ Przygotowanie struktur danych dla stanów wejść/wyjść i historii zdarzeń.
- ⏳ Implementacja API HTTP i integracji z bazą konfiguracji.
- ⏳ Obsługa sesji użytkowników oraz podział ról (Operator, Technik, Serwis).
- ⏳ Zaimplementowanie harmonogramów odczytu czujników i aktualizacji logiki co 0,25 s.

## Widoki aplikacji
### Panel Operatora
- ✅ Określono zakres informacji (stany wejść/wyjść, logi urządzenia).
- ⏳ Przygotowanie dashboardu ze stanami drzwi, czujników zalania i kluczowych wyjść (alarm, oświetlenie, klimatyzacja, grzałka, wentylatory).
- ⏳ Udostępnienie podglądu logów zdarzeń z możliwością filtrowania.
- ⏳ Zapewnienie, że dodatkowe czujniki aktywowane w panelu serwisowym automatycznie pojawią się w widoku operatora.

### Panel Technika
- ✅ Ustalono zakres uprawnień dodatkowych (progi temperatur, ustawienia sieciowe, nazwa urządzenia).
- ⏳ Formularze do zmiany progów temperatur, histerezy i parametrów sieciowych (IP, maska, brama, DNS).
- ⏳ Zapewnienie walidacji danych i zapisu zmian do trwałej konfiguracji.
- ⏳ Prezentacja potwierdzeń i komunikatów o błędach dla technika.
- ⏳ Mechanizm aktualizacji nazwy i opisu urządzenia widocznego w pozostałych panelach.

### Panel Serwisu
- ✅ Określono funkcje serwisowe (tryb manualny, tryb testowy, przypisanie dodatkowych wejść/wyjść).
- ⏳ Zabezpieczenie dostępu przełącznikiem serwisowym (DIP) oraz rolą użytkownika.
- ⏳ Interfejs do ręcznego sterowania każdym wyjściem wraz z ostrzeżeniami.
- ⏳ Przygotowanie bazowej konfiguracji (4 drzwi, 1 czujnik zalania) oraz formularza pozwalającego aktywować kolejne wejścia, które po przypisaniu staną się widoczne dla operatora i technika.
- ⏳ Kreator dodawania kolejnych drzwi i czujników zalania oraz przypisywania wyjść tranzystorowych, z kontrolą uniknięcia podwójnych przydziałów.
- ⏳ Implementacja trybu testowego (konfigurowany czas trwania, interwały przełączania wyjść) uruchamiającego kolejno każde wyjście oraz raportującego postęp.
- ⏳ Tryb manualny z przyciskami do natychmiastowego załączania/wyłączania pojedynczych wyjść i wyraźnym oznaczeniem aktywnego trybu.

## Logika działania urządzenia
- ✅ Spisano reguły sterowania na podstawie czujników i wejść (drzwi, zalanie, temperatura).
- ⏳ Implementacja sterowania klimatyzacją, grzałką i wentylacją z histerezą.
- ⏳ Obsługa alarmów: otwarcie drzwi, zalanie, przegrzanie – wraz z odpowiednimi komunikatami.
- ⏳ Reakcja bezpieczeństwa przy braku danych z czujników (wyłączenie sterowania, alarm serwisowy).
- ⏳ Utrzymanie dziennika zdarzeń (zapisywanie przyczyn alarmów i zmian stanów).

## Komunikacja – protokoły
- ✅ Wybrano protokoły: HTTP (panel i API), SNMP (monitoring zewnętrzny).
- ⏳ Przygotowanie dokumentacji API dla integratorów.
- ⏳ Implementacja i konfiguracja agenta SNMP z odpowiednimi OID do odczytu stanów.
- ⏳ Testy komunikacji z systemami nadrzędnymi (zapytania HTTP, odczyt SNMP).

## Dostosowanie I/O (wejścia/wyjścia)
- ✅ Sporządzono mapę sprzętową: 8 przekaźników (K1–K8), 8 tranzystorów (T1–T8), 6 wejść drzwi, 2 czujniki zalania, czujniki DS18B20 i DHT11.
- ⏳ Przygotowanie konfiguracji bazowej (4 drzwi, 1 czujnik zalania) i maksymalnej (6 drzwi, 2 czujniki zalania).
- ⏳ Implementacja przypisywania wyjść do drzwi (elektrozaczepy) z kontrolą unikalności.
- ⏳ Kalibracja czasów działania wyjść (np. czas otwarcia drzwi, czasy testowe).
- ⏳ Testy końcowe sprzęt + oprogramowanie (symulacja scenariuszy alarmowych i normalnych).

---

## Informacje techniczne dla zespołu developerskiego

Poniższa sekcja zachowuje dotychczasowe wskazówki dotyczące uruchamiania środowiska.

### Wymagania
- Docker z Compose v2
- `make`
- (opcjonalnie) Python 3.11+ do skryptów pomocniczych

### Generowanie certyfikatów i sekretów
1. **Certyfikaty mTLS** – uruchom `make ca`. Polecenie wywołuje `tcm/scripts/gen-ca.sh`, tworzy kompletny zestaw lokalnego CA i kopiuje certyfikaty do `tcm/deploy/reverse-proxy/certs/`. Gotowa paczka kliencka `client-universal.tar.gz` zawiera certyfikat współdzielony przez Operatora, Technika i Serwis.
2. **Sekrety aplikacji** – w razie potrzeby uruchom `python tcm/scripts/generate_secrets.py`, aby przygotować pliki w `tcm/secrets/` lub wypisać wartości i przenieść je do docelowego wolumenu (`/var/lib/tcm/secrets`). Skrypt poprosi o hasło administracyjne i wygeneruje `app_secret_key`, `app_fernet_key` oraz `admin_bootstrap_hash`.

### Uruchomienie w trybie developerskim
```bash
make dev
```
Target buduje wymagane obrazy i uruchamia `docker compose` z plikiem `tcm/compose.dev.yaml`. Kontener aplikacji startuje w trybie `development` (autoreload, logi `debug`) i montuje katalog `tcm/app`, dzięki czemu zmiany w kodzie są natychmiast widoczne.

### Uruchomienie w trybie produkcyjnym
```bash
make prod
```
Target w razie potrzeby automatycznie generuje certyfikaty (`make ca`), a następnie buduje i podnosi usługę według `tcm/compose.yaml`. Aplikacja działa w trybie `production`. Po starcie możesz śledzić logi poleceniem `make logs`.

### Przydatne dodatkowe polecenia
- `make clean-ca` – usuwa wygenerowane certyfikaty, aby rozpocząć proces od nowa.
- `docker compose -f tcm/compose.yaml down` – zatrzymanie środowiska produkcyjnego.
- `docker compose -f tcm/compose.dev.yaml down` – zatrzymanie środowiska developerskiego.

### Gdzie szukać kolejnych informacji
- `tcm/deploy/ca/README.md` – skrócona procedura CA i opis artefaktów.
- `tcm/app/README.md` – struktura katalogów aplikacji.
- `docs/migration_blueprint.md` – szczegółowy plan migracji i architektury.
