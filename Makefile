.PHONY: up down qa-up qa-down qa-seed qa-fault-scanner qa-fault-stash-empty qa-fault-api-unavailable qa-fault-service-action-failure qa-fault-clear qa-frontend qa-verify-product backtest-all

COMPOSE := docker compose
QA_COMPOSE := $(COMPOSE) -f docker-compose.yml -f docker-compose.qa.yml --env-file .env.qa
SERVICES := clickhouse schema_migrator market_harvester
PYTHON := .venv/bin/python
BACKTEST_LEAGUE ?= Mirage
BACKTEST_DAYS ?= 14
BACKTEST_FLAGS ?=

up:
	$(COMPOSE) up --build --detach $(SERVICES)

down:
	$(COMPOSE) down --remove-orphans

qa-up:
	@test -f .env.qa || cp .env.qa.example .env.qa
	$(QA_COMPOSE) up --build --detach

qa-down:
	$(QA_COMPOSE) down --remove-orphans --volumes

qa-seed:
	$(PYTHON) -m poe_trade.qa_contract seed --output .sisyphus/evidence/product/task-1-qa-environment/qa-seed.json

qa-fault-scanner:
	$(PYTHON) -m poe_trade.qa_contract fault --name scanner_degraded --output .sisyphus/evidence/product/task-1-qa-environment/qa-fault-scanner.json

qa-fault-stash-empty:
	$(PYTHON) -m poe_trade.qa_contract fault --name stash_empty --output .sisyphus/evidence/product/task-1-qa-environment/qa-fault-stash-empty.json

qa-fault-api-unavailable:
	$(PYTHON) -m poe_trade.qa_contract fault --name api_unavailable --output .sisyphus/evidence/product/task-1-qa-environment/qa-fault-api-unavailable.json

qa-fault-service-action-failure:
	$(PYTHON) -m poe_trade.qa_contract fault --name service_action_failure --output .sisyphus/evidence/product/task-1-qa-environment/qa-fault-service-action-failure.json

qa-fault-clear:
	$(PYTHON) -m poe_trade.qa_contract clear-faults --output .sisyphus/evidence/product/task-1-qa-environment/qa-fault-clear.json

qa-frontend:
	cd frontend && npm run qa:dev

qa-verify-product:
	.venv/bin/pytest tests/unit/test_api_*.py tests/unit/test_strategy_*.py tests/unit/test_ml_*.py
	cd frontend && npm run test && npm run build && npm run test:inventory && npx playwright test
	$(PYTHON) -m poe_trade.evidence_bundle

backtest-all:
	$(PYTHON) -m poe_trade.cli research backtest-all --league "$(BACKTEST_LEAGUE)" --days "$(BACKTEST_DAYS)" $(BACKTEST_FLAGS)

update:
	$(PYTHON) -m poe_trade.cli refresh gold --group refs
