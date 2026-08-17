.PHONY: install lint format typecheck test test-unit test-contract up down smoke

UV ?= python -m uv

install:
	$(UV) sync --extra dev
	$(UV) run pre-commit install

lint:
	$(UV) run ruff check .

format:
	$(UV) run ruff format .

typecheck:
	$(UV) run mypy src

test: test-unit test-contract

test-unit:
	$(UV) run pytest tests/unit -q

test-contract:
	$(UV) run pytest tests/contract -q

up:
	docker compose up -d postgres

down:
	docker compose down

smoke:
	$(UV) run ruff check .
	$(UV) run mypy src
	$(UV) run pytest tests/unit tests/contract -q
