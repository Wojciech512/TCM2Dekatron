# Certyfikaty i klucze CA

1. Uruchom `make ca`. Skrypt wygeneruje lokalny root i intermediate CA, certyfikaty serwera oraz paczkę kliencką `client-universal.tar.gz`.
2. W katalogu `tcm/deploy/reverse-proxy/certs/` znajdziesz gotowe pliki TLS/mTLS używane podczas `make prod`.
3. Przechowuj katalogi `root-ca/` i `intermediate/` w bezpiecznej lokalizacji offline.
4. W razie konieczności powtórnego wydania certyfikatów użyj `make clean-ca`, a następnie ponownie `make ca`.
