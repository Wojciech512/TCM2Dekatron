# Scenariusze E2E (stubowane)

1. **Autoryzacja ról** – skrypt symulujący logowanie operator/technik/serwis z użyciem certyfikatu klienta.
2. **Widok dashboardu** – test Selenium sprawdzający prezentację wejść/wyjść i temperatur.
3. **Alarm drzwi** – stub MCP23S17 ustawiający bit drzwi na HIGH → oczekiwany wpis w bazie `events`.
4. **Alarm zalania** – stub MCP23S17 ustawiający bit zalania na LOW → alarm i wpis w `events`.
5. **Strike** – endpoint `/api/v1/strike/<id>/trigger` zwraca 200 dla skonfigurowanego tranzystora i 403 dla braku mapowania.
6. **Brak czujnika** – symulacja timeoutu DHT11 i DS18B20 → aplikacja powinna ustawić `None` i wpisać zdarzenie `SENSOR` o poziomie `warning`.
7. **mTLS** – próba połączenia z błędnym certyfikatem klienta zakończona kodem 403.
