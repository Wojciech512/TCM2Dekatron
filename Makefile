CA_SENTINEL := tcm/deploy/ca/output/.generated
MAKEFLAGS += --warn-undefined-variables

.PHONY: dev prod logs ca clean-ca

dev:
	docker compose -f tcm/compose.dev.yaml up --build


$(CA_SENTINEL):
	@echo "==> Generowanie lokalnego CA"
	@bash tcm/scripts/gen-ca.sh

prod: $(CA_SENTINEL)
	docker compose -f tcm/compose.yaml up -d --build

logs:
	docker compose logs -f

ca:
	bash tcm/scripts/gen-ca.sh --force

clean-ca:
	rm -rf tcm/deploy/ca/output \
		tcm/deploy/ca/root-ca \
		tcm/deploy/ca/intermediate \
		tcm/deploy/ca/clients \
		tcm/deploy/reverse-proxy/certs
