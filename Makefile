.PHONY: up down logs rebuild seed-reset smoke test test-backend fe-typecheck ps psql

COMPOSE ?= docker compose

up:            ## build + start the whole stack
	$(COMPOSE) up -d --build
	@echo "frontend  -> http://localhost:$${FRONTEND_PORT:-8080}"
	@echo "API docs  -> http://localhost:$${BACKEND_PORT:-8000}/docs"

down:          ## stop the stack (keep data)
	$(COMPOSE) down

nuke:          ## stop the stack and delete the database volume
	$(COMPOSE) down -v

logs:
	$(COMPOSE) logs -f --tail=120

rebuild:
	$(COMPOSE) build --no-cache

ps:
	$(COMPOSE) ps

psql:          ## open a psql shell on the database
	$(COMPOSE) exec db psql -U $${POSTGRES_USER:-xeno} -d $${POSTGRES_DB:-xenopulse}

partition-demo: ## build campaign_events_part (enables the partition-pruning scenario)
	$(COMPOSE) exec -T db psql -U $${POSTGRES_USER:-xeno} -d $${POSTGRES_DB:-xenopulse} < db/partitioning.sql

reseed:        ## re-run the synthetic data generator
	$(COMPOSE) exec -T db psql -U $${POSTGRES_USER:-xeno} -d $${POSTGRES_DB:-xenopulse} < db/seed.sql

smoke:         ## run the end-to-end smoke test against the running stack
	./scripts/smoke.sh

test: test-backend fe-typecheck ## run all fast checks

test-backend:  ## backend unit tests (SQL guard + catalog; no DB needed)
	cd backend && python -m pytest -q tests/test_sql_guard.py tests/test_catalog.py

fe-typecheck:
	cd frontend && npm run typecheck
