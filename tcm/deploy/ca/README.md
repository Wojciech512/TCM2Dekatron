# Procedura tworzenia lokalnego CA dla TCM 2.0

1. Uruchom `make ca` (alias na `tcm/scripts/gen-ca.sh --force`) na zaufanej stacji offline. Skrypt utworzy:
   * `root-ca/` – klucz i certyfikat root (do przechowywania offline);
   * `intermediate/` – podległy CA do podpisywania certyfikatów serwera i klientów;
   * katalog `output/` z paczkami: `client-<rola>.tar.gz`, `ca-chain.crt`, `crl.pem`, `server.crt.pem`, `server.key.pem`.
   * katalog `tcm/deploy/reverse-proxy/certs/` z gotową konfiguracją TLS/mTLS dla NGINX.
2. Zabezpiecz klucze prywatne (nośniki szyfrowane, sejf).
3. Artefakty NGINX w `tcm/deploy/reverse-proxy/certs/` są gotowe do użycia przez proces budowania obrazu.
4. Dystrybuuj paczki klienckie zgodnie z rolą (Operator/Technik/Serwis). Certyfikaty instalowane w przeglądarkach + urządzeniach diagnostycznych.
5. W NGINX aktualizuj plik `ca-clients.crt` przy każdym nowym certyfikacie klienckim (dołącz łańcuch do intermediate CA).
6. Rotacja:
   * uruchom ponownie `make ca`, aby wygenerować nowe certyfikaty i nadpisać zawartość `certs/` (skrypt wymaga flagi `--force`, którą target `make ca` ustawia automatycznie);
   * unieważnij stare poprzez aktualizację `crl.pem` i wskazanie `ssl_crl` w konfiguracji NGINX.
7. Dokumentuj wydania certyfikatów w logach audytowych (typ `AUTH`).
