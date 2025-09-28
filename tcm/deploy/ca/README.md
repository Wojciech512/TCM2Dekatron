# Procedura tworzenia lokalnego CA dla TCM 2.0

1. Uruchom `scripts/gen-ca.sh` na zaufanej stacji offline. Skrypt utworzy:
   * `root-ca/` – klucz i certyfikat root (do przechowywania offline);
   * `intermediate/` – podległy CA do podpisywania certyfikatów serwera i klientów;
   * katalog `output/` z paczkami: `server.tar.gz`, `clients/<rola>.tar.gz`, `ca-chain.crt`, `crl.pem`.
2. Zabezpiecz klucze prywatne (nośniki szyfrowane, sejf).
3. Wgraj `server.tar.gz` na Raspberry Pi i rozpakuj do `tcm/deploy/reverse-proxy/certs/`.
4. Dystrybuuj paczki klienckie zgodnie z rolą (Operator/Technik/Serwis). Certyfikaty instalowane w przeglądarkach + urządzeniach diagnostycznych.
5. W NGINX aktualizuj plik `ca-clients.crt` przy każdym nowym certyfikacie klienckim (dołącz łańcuch do intermediate CA).
6. Rotacja:
   * wygeneruj nowe certyfikaty → zastąp w `certs/` → restart usługi reverse-proxy;
   * unieważnij stare poprzez aktualizację `crl.pem` i wskazanie `ssl_crl` w konfiguracji NGINX.
7. Dokumentuj wydania certyfikatów w logach audytowych (typ `AUTH`).
