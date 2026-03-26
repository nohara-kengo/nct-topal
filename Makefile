.PHONY: up down rebuild test upload-secrets-dev upload-secrets-prd

up:
	docker compose up -d

down:
	docker compose down

rebuild:
	docker compose build --no-cache && docker compose up -d

test:
	docker exec topal-dev python -m pytest tests/ -v

upload-secrets-dev:
	./scripts/upload-secrets.sh dev

upload-secrets-prd:
	./scripts/upload-secrets.sh prd
