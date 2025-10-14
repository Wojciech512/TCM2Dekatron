# Scenariusze E2E

Testy końcowe zakładają, że środowisko zostało uruchomione jednym z poleceń:

- `make dev` – dla szybkich iteracji lokalnych,
- `make prod` – dla weryfikacji konfiguracji z reverse proxy (wymaga wcześniejszego `make ca`).

Scenariusze są obecnie szkicami. Każdy z nich wykorzystuje wspólny pakiet klienta `client-universal.tar.gz` wygenerowany przez `make ca` do uwierzytelnienia Operatora, Technika i Serwisu.
