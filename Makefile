dev:
	docker compose -f tcm/docker/compose.dev.yaml up --build

prod:
	docker compose -f tcm/docker/compose.yaml up -d --build

logs:
	docker compose logs -f
