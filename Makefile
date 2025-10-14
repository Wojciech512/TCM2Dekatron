dev:
	docker compose -f tcm/compose.dev.yaml up --build

prod:
	docker compose -f tcm/compose.yaml up -d --build

logs:
	docker compose logs -f
