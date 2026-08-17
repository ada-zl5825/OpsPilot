# Incident simulator

Phase 1 lab: gateway, checkout, payment, inventory, notification, PostgreSQL, Redis, Prometheus, Loki, Tempo, and the OpenTelemetry Collector.

Ground truth and verification codes stay in `benchmarks/datasets/incidents/v1/`. They must not appear in prompts, runbooks, or controller API responses.

## Start

```powershell
docker compose --profile lab up -d --build
```

One command starts the shop, fault controller, traffic, and observability stack. The `holmes` profile is unchanged.

| Service | Port |
|---|---|
| gateway | 8080 |
| checkout | 8081 |
| payment | 8082 |
| inventory | 8083 |
| notification | 8084 |
| controller | 8090 |
| postgres | 5432 |
| redis | 6379 |
| prometheus | 9090 |
| loki | 3100 |
| tempo | 3200 |
| otel collector | 4317 / 4318 |

## Scenarios

| ID | Inject | Reset |
|---|---|---|
| S01 | `POST /v1/scenarios/S01/inject` | `POST /v1/scenarios/S01/reset` |
| S02 | `POST /v1/scenarios/S02/inject` | `POST /v1/scenarios/S02/reset` |
| S03 | `POST /v1/scenarios/S03/inject` | `POST /v1/scenarios/S03/reset` |
| S04 | `POST /v1/scenarios/S04/inject` | `POST /v1/scenarios/S04/reset` |

Inject and reset are idempotent. `POST /v1/reset` clears every flag. `GET /v1/active` returns the current inject onset only. Controller responses do not include ground truth or verification codes.

Place an order through the storefront:

```powershell
Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8080/api/orders -ContentType application/json -Body '{"sku":"sku-100","qty":1}'
```

## Verify without an LLM

```powershell
python -m uv run python -m benchmarks.datasets.check_integrity
python -m uv run python -m simulator.harness --cycles 2
```

The harness checks dataset integrity, two consecutive inject/reset cycles per scenario, live recovery against real HTTP/metrics, and that Prometheus, Loki, and Tempo are up.

## Design rules

- Service names do not encode the root cause
- Logs do not say `simulated error`
- Prompts do not contain answer keywords or verification codes
- Recovery checks use real APIs and metrics
