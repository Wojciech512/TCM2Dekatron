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
### Widoki i nawigacja
- ✅ Zdefiniowano trzy główne panele: Operator, Technik, Serwis.
- ⏳ Zaprojektowanie układu ekranów i menu nawigacyjnego (dashboard + widoki szczegółowe).
- ⏳ Przygotowanie warstwy wizualnej (kolory alarmów, czytelne etykiety w języku polskim).
- ⏳ Zapewnienie automatycznego odświeżania danych w panelach (stany I/O, logi, konfiguracja).

### Dostępność i użyteczność
- ⏳ Testy użyteczności z docelowymi użytkownikami (operatorzy, technicy, serwis).
- ⏳ Przygotowanie instrukcji ekranowych i podpowiedzi, które ułatwią pracę nietechnicznym użytkownikom.
- ⏳ Wprowadzenie spójnych ikon i oznaczeń alarmów (np. kolory, symbole ostrzegawcze).

## Poziomy dostępu – przegląd funkcji
- **Operator**: podgląd stanów wejść/wyjść, odczyt logów, brak możliwości zmiany konfiguracji.
- **Technik**: wszystkie uprawnienia operatora + edycja progów temperatur, ustawień sieciowych oraz nazwy/opisu urządzenia.
- **Serwis**: wszystkie uprawnienia technika + manualne sterowanie wyjściami, tryb testowy, rozszerzanie konfiguracji I/O; dostęp warunkowany przełącznikiem DIP.

## Backend (monolit aplikacyjny)
### Warstwa logiki i danych
- ✅ Zebrano wymagania dotyczące logiki urządzenia i dostępów użytkowników.
- ⏳ Przygotowanie struktur danych dla stanów wejść/wyjść oraz historii zdarzeń.
- ⏳ Zaimplementowanie harmonogramów odczytu czujników i aktualizacji logiki co 0,25 s.
- ⏳ Zarządzanie konfiguracją bazową i rozszerzoną (zapisywanie, odczyt, reset).

### Warstwa komunikacji
- ⏳ Implementacja API HTTP i integracji z bazą konfiguracji.
- ⏳ Obsługa sesji użytkowników oraz podział ról (Operator, Technik, Serwis).
- ⏳ Zapewnienie warstwy autoryzacji dla operacji manualnych i trybu testowego.

## Widoki aplikacji i poziomy dostępu
### Panel Operatora (podstawowy dostęp)
- ✅ Określono zakres informacji (stany wejść/wyjść, logi urządzenia).
- ⏳ **Monitoring wejść**
  - Wyświetlanie statusu każdego drzwi (4 w wersji bazowej, do 6 po rozszerzeniu) wraz z opisem lokalizacji.
  - Wskazanie statusu czujników zalania (1 w wersji bazowej, 2 po rozszerzeniu) z wyróżnieniem alarmów.
- ⏳ **Monitoring wyjść**
  - Widoczność kluczowych wyjść: K1 Alarm, K2 Klimatyzacja, K3 Oświetlenie, K4 Grzałka, K5 Wentylatory 230 VAC, T1 Wentylatory 48 VDC.
  - Lista pozostałych przekaźników (K6–K8) i tranzystorów (T2–T8) z opisami zastosowań.
- ⏳ **Logi i alarmy**
  - Dostęp do dziennika zdarzeń (filtry po typie zdarzenia, czasie).
  - Czytelne komunikaty alarmowe (np. „Drzwi otwarte”, „Wykryto zalanie”, „Przegrzanie”).
- ⏳ **Automatyczne aktualizacje**
  - Odświeżanie widoku bez konieczności ręcznego przeładowania.
  - Automatyczne pojawianie się dodatkowych czujników po ich aktywacji w panelu serwisowym.

### Panel Technika (rozszerzony dostęp)
- ✅ Ustalono zakres uprawnień dodatkowych (progi temperatur, ustawienia sieciowe, nazwa urządzenia).
- ⏳ **Konfiguracja temperatur**
  - Formularze do zmiany progów klimatyzacji (K2), grzałki (K4) i wentylacji awaryjnej (K5 + T1).
  - Ustawianie histerezy i potwierdzenie zapisu każdej zmiany.
- ⏳ **Ustawienia sieciowe**
  - Edycja IP, maski, bramy, DNS z walidacją formatu i informacją o koniecznym restarcie (jeśli wymagany).
- ⏳ **Identyfikacja urządzenia**
  - Zmiana nazwy i opisu urządzenia prezentowanych w nagłówkach wszystkich paneli oraz w logach.
- ⏳ **Bezpieczeństwo konfiguracji**
  - Podgląd historii zmian ustawień (kto i kiedy modyfikował parametry).
  - Zapewnienie, że konfiguracja jest trwała po restarcie (zapis do pamięci nieulotnej).

### Panel Serwisu (pełny dostęp + DIP)
- ✅ Określono funkcje serwisowe (tryb manualny, tryb testowy, przypisanie dodatkowych wejść/wyjść).
- ⏳ **Zabezpieczenie dostępu**
  - Wymóg aktywnego przełącznika serwisowego (DIP) oraz roli „Serwis”.
  - Automatyczne blokowanie panelu po wyłączeniu przełącznika.
- ⏳ **Tryb manualny**
  - Przełącznik globalny aktywujący manualne sterowanie z wyraźnym ostrzeżeniem.
  - Lista wyjść K1–K8 i T1–T8 z przyciskami ON/OFF oraz czytelnym statusem.
  - Logowanie każdej ręcznej operacji i możliwość szybkiego powrotu do trybu automatycznego.
- ⏳ **Konfiguracja wejść/wyjść**
  - Predefiniowana konfiguracja bazowa (Drzwi 1–4, Czujnik zalania 1).
  - Aktywacja dodatkowych drzwi 5–6 i drugiego czujnika zalania poprzez kreator krok po kroku.
  - Przypisywanie wyjść tranzystorowych do elektrozaczepów z kontrolą unikalności.
  - Edycja opisów drzwi/czujników tak, aby były widoczne w pozostałych panelach.
- ⏳ **Tryb testowy**
  - Ustawianie czasu trwania testu (np. 5 h) oraz interwału przełączania (np. co 30 min).
  - Automatyczne załączanie kolejnych wyjść w zadanej sekwencji i prezentacja postępu.
  - Raport końcowy z wynikami testów (które wyjścia przeszły/nie przeszły).

## Logika działania urządzenia
### Ogólne zasady
- ✅ Spisano reguły sterowania na podstawie czujników i wejść (drzwi, zalanie, temperatura).
- ⏳ Implementacja harmonogramu odczytu danych z czujników DS18B20 i DHT11.
- ⏳ Zarządzanie priorytetami alarmów (drzwi > zalanie > temperatura).

### Sterowanie temperaturą i wentylacją
- ⏳ Klimatyzacja (K2):
  - Włączenie po przekroczeniu zadanego progu temperatury.
  - Wyłączenie po spadku poniżej progu minus histereza.
- ⏳ Grzałka (K4):
  - Włączenie po spadku temperatury poniżej progu zimna.
  - Wyłączenie po osiągnięciu progu + histereza.
- ⏳ Wentylatory awaryjne (K5 + T1):
  - Uruchomienie po przekroczeniu progu przegrzania.
  - Opcjonalne wyłączenie klimatyzacji podczas pracy awaryjnej (potwierdzenie z klientem).

### Reakcje na zdarzenia
- ⏳ Otwarcie dowolnych drzwi:
  - Natychmiastowe wyłączenie klimatyzacji, wentylatorów i grzałki.
  - Załączenie oświetlenia (K3) i alarmu (K1) z komunikatem „Drzwi otwarte”.
- ⏳ Aktywacja czujnika zalania:
  - Załączenie alarmu (K1) z komunikatem „Wykryto zalanie”.
  - Pozostawienie innych wyjść w aktualnym stanie.
- ⏳ Przekroczenie progu temperatury wentylatorów:
  - Uruchomienie K5 i T1 oraz alarm „Przegrzanie”.
  - Potwierdzenie decyzji o wyłączeniu klimatyzacji podczas alarmu przegrzania.
- ⏳ Przekroczenie progów dla klimatyzacji lub grzałki:
  - Załączenie odpowiedniego wyjścia bez alarmu.

### Stany wyjątkowe i logowanie
- ⏳ Tryb bezpieczny przy braku danych z czujników (blokada wyjść, sygnał ostrzegawczy).
- ⏳ Ciągłe prowadzenie dziennika zdarzeń wraz z przyczynami i czasem wystąpienia.
- ⏳ Udostępnienie logów do odczytu w panelach zgodnie z poziomami dostępu.

## Komunikacja – protokoły
### HTTP (panel i API)
- ✅ Potwierdzono, że interfejs webowy i REST API będą działały w oparciu o HTTPS.
- ⏳ Dokumentacja endpointów (odczyt stanów I/O, sterowanie wyjściami, konfiguracja).
- ⏳ Weryfikacja mechanizmów autoryzacji między panelami a API.

### API (integracje zewnętrzne)
- ⏳ Przygotowanie stabilnych endpointów do integracji z systemami zewnętrznymi (np. BMS).
- ⏳ Określenie limitów i scenariuszy błędów (timeouty, komunikaty).
- ⏳ Publikacja przykładowych zapytań i odpowiedzi dla integratorów.

### SNMP (monitoring)
- ⏳ Implementacja agenta SNMP z OID odczytującymi stany wejść, wyjść i alarmów.
- ⏳ Konfiguracja bezpieczeństwa (community string lub SNMPv3).
- ⏳ Testy odczytu z zewnętrznym menedżerem SNMP.

## Dostosowanie I/O (wejścia/wyjścia)
### Wyjścia przekaźnikowe (K1–K8)
- ✅ Mapa funkcji: K1 Alarm, K2 Klimatyzacja, K3 Światło, K4 Grzałka, K5 Wentylatory 230 VAC, K6–K8 rezerwowe.
- ⏳ Definicja scenariuszy sterowania dla rezerwowych kanałów (np. dodatkowe alarmy, sygnalizacje).

### Wyjścia tranzystorowe (T1–T8)
- ✅ Mapa funkcji: T1 Wentylatory 48 VDC, T2 Elektrozaczep drzwi 1, T3–T8 dostępne dla kolejnych drzwi.
- ⏳ Konfiguracja czasów podtrzymania elektrozaczepów i zabezpieczenia przed przegrzaniem.

### Wejścia cyfrowe
- ✅ Czujniki drzwi: 6 wejść krańcówek (A0–A5) z możliwością opisania każdej pary drzwi.
- ✅ Czujniki zalania: 2 wejścia (A6–A7) z progami detekcji zalania.
- ⏳ Obsługa przełącznika serwisowego (DIP) umożliwiającego dostęp do panelu serwisowego.

### Czujniki środowiskowe
- ✅ DS18B20 – cyfrowy pomiar temperatury głównej szafy.
- ✅ DHT11 – pomiar temperatury i wilgotności pomocniczej.
- ⏳ Mechanizmy kalibracji i diagnostyki (np. test odczytu, alarm przy braku odpowiedzi czujnika).

### Konfiguracje sprzętowe
- ⏳ Przygotowanie konfiguracji bazowej (4 drzwi, 1 czujnik zalania) oraz maksymalnej (6 drzwi, 2 czujniki zalania).
- ⏳ Kreator przypisywania wyjść do drzwi wraz z kontrolą unikalności.
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
