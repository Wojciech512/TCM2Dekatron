# Certyfikaty i klucze CA

## 1. Generowanie kompletu CA

1. Upewnij się, że masz zainstalowane `openssl` (>= 1.1) oraz `make`.
2. Na odizolowanej maszynie uruchom:
   ```bash
   make ca
   ```
3. Skrypt `tcm/scripts/gen-ca.sh` zbuduje hierarchię `root -> intermediate` i utworzy:
   - certyfikaty serwera potrzebne reverse proxy,
   - uniwersalny pakiet klienta mTLS dla Operatora/Technika/Serwisu,
   - łańcuch CA oraz listę CRL.
4. Artefakty znajdziesz w katalogu `tcm/deploy/ca/output/` (tymczasowe) oraz `tcm/deploy/reverse-proxy/certs/` (docelowe pliki dla NGINX).

> Jeśli chcesz odtworzyć całość od zera, użyj `make clean-ca`, a następnie ponów `make ca`.

## 2. Co zawiera każdy katalog

| Lokalizacja | Pliki | Zastosowanie | Wskazówki bezpieczeństwa |
| --- | --- | --- | --- |
| `tcm/deploy/ca/root-ca/` | `root.key.pem`, `root.crt.pem` | Klucz i certyfikat nadrzędnego CA. Podpisuje intermediate. | Trzymaj **offline**, tylko do przechowywania długoterminowego. Kopię `root.crt.pem` możesz przekazać administratorom do importu jako zaufany główny urząd. |
| `tcm/deploy/ca/intermediate/` | `intermediate.key.pem`, `intermediate.crt.pem`, `openssl.cnf`, baza CRL | Intermediate CA podpisuje serwer oraz klientów. | Przechowuj offline, zabezpieczone hasłem/dyskami szyfrowanymi. Dostęp tylko podczas wystawiania nowych certyfikatów. |
| `tcm/deploy/ca/output/server.*` | `server.key.pem`, `server.crt.pem`, `server.csr.pem` | Materiały TLS dla reverse proxy. | `server.key.pem` pozostaje na serwerze reverse proxy; zabezpiecz uprawnieniami 600. Certyfikat (`server.crt.pem`) możesz udostępnić do inspekcji. |
| `tcm/deploy/ca/output/ca-chain.crt` | Połączony certyfikat intermediate + root | Łańcuch zaufania serwera. | Dołączany do konfiguracji NGINX oraz klientom. Plik może być publiczny. |
| `tcm/deploy/ca/output/crl.pem` | Lista unieważnionych certyfikatów | Publikowana w reverse proxy. | Aktualizuj przy odwoływaniu certyfikatów klienta. |
| `tcm/deploy/ca/ca-clients.crt` | Kopia `ca-chain.crt` dla dystrybucji do klientów | Import do zaufanych urzędów w systemach użytkowników. | Może być publiczny. |
| `tcm/deploy/ca/output/client-universal.tar.gz` | `universal.key.pem`, `universal-fullchain.pem`, `universal.p12` | Pakiet mTLS dla Operatora/Technika/Serwisu. | Chronić jak hasło: przekazywać szyfrowanym kanałem. Po imporcie usunąć z dysku. |

## 3. Dystrybucja i import dla klientów

1. Przekaż użytkownikowi plik `client-universal.tar.gz` wraz z osobnym kanałem przekazu hasła eksportu (`Test123!`).
2. Po rozpakowaniu (`tar -xzf client-universal.tar.gz`):
   - **`universal.p12`** – zawiera klucz prywatny i łańcuch. To plik, który użytkownik importuje do magazynu certyfikatów przeglądarki/systemu.
   - **`universal.key.pem`** – surowy klucz prywatny. Nie jest wymagany do importu, ale może przydać się automatom (np. skrypty curl). Usuń po wykorzystaniu.
   - **`universal-fullchain.pem`** – certyfikat klienta z dołączonym CA. Użyteczny dla narzędzi CLI.
3. Instrukcje importu do przeglądarek:
   - **Firefox**: `Ustawienia → Prywatność i bezpieczeństwo → Certyfikaty → Wyświetl certyfikaty → Importuj`, wskaż `universal.p12`, podaj hasło `Test123!`, zaznacz „zawsze ufaj temu certyfikatowi klienta”.
   - **Chrome/Edge (Windows)**: `Ustawienia → Prywatność i zabezpieczenia → Zarządzaj certyfikatami → Importuj`, wybierz magazyn „Osobisty”, wgraj `universal.p12`, hasło `Test123!`.
   - **Chrome (macOS)**: Otwórz „Pęk kluczy”, przeciągnij `universal.p12` do `login`, wpisz hasło `Test123!`, ustaw zawsze ufaj certyfikatowi.
4. W systemach automatycznych (np. curl) użyj `universal.key.pem` + `universal-fullchain.pem` i upewnij się, że pliki mają prawa `600` oraz są przechowywane na zaszyfrowanym dysku.

## 4. Co zabezpieczyć, co można udostępnić

- **Maksymalna ochrona**: `root.key.pem`, `intermediate.key.pem`, `universal.key.pem`, archiwum `client-universal.tar.gz` (dopóki użytkownik nie zaimportuje certyfikatu), hasło `Test123!`. Trzymaj w sejfie haseł lub menedżerze tajemnic. Rozważ natychmiastowe przepakowanie `universal.p12` z własnym hasłem (`openssl pkcs12 -export ...`) przed dystrybucją.
- **Ograniczony dostęp (serwer)**: `server.key.pem`, konfiguracja NGINX w `tcm/deploy/reverse-proxy/certs/`. Udostępniaj tylko operatorom platformy.
- **Można rozpowszechniać**: `root.crt.pem`, `ca-chain.crt`, `ca-clients.crt`, `server.crt.pem`, `crl.pem`. Pozwalają klientom zweryfikować połączenie.

## 5. Odnowienie lub unieważnienie

1. Aby wygenerować nowy pakiet (np. po kompromitacji), usuń poprzednie artefakty: `make clean-ca`.
2. Ponownie uruchom `make ca` i przeprowadź dystrybucję jak wyżej.
3. Jeśli potrzebujesz unieważnić klienta, dodaj jego numer seryjny do `tcm/deploy/ca/intermediate/index.txt`, uruchom ponownie `make ca` (target sam wymusza regenerację) lub `./tcm/scripts/gen-ca.sh --force`, a następnie zaktualizuj `crl.pem` na reverse proxy.

> Pamiętaj, aby po każdej operacji dystrybucji usunąć tymczasowe kopie kluczy z maszyn roboczych.
