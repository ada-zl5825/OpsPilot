.PHONY: install lint format typecheck test test-unit test-contract test-security up down smoke holmes-up holmes-down holmes-smoke lab-up lab-down lab-verify investigate-prompt

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

test: test-unit test-contract test-security

test-unit:
	$(UV) run pytest tests/unit -q

test-contract:
	$(UV) run pytest tests/contract -q

test-security:
	$(UV) run pytest tests/security -q

up:
	docker compose up -d postgres

down:
	docker compose down

holmes-up:
	docker compose --profile holmes up -d --build

holmes-down:
	docker compose --profile holmes down

holmes-smoke:
	$(UV) run python -m opspilot.holmes.smoke

lab-up:
	docker compose --profile lab up -d --build

lab-down:
	docker compose --profile lab down

lab-verify:
	$(UV) run python -m benchmarks.datasets.check_integrity
	$(UV) run python -m simulator.harness --cycles 2

investigate-prompt:
	$(UV) run python -m opspilot.cli investigate --all --prompt-only

smoke:
	$(UV) run ruff check .
	$(UV) run mypy src
	$(UV) run pytest tests/unit tests/contract tests/security -q
