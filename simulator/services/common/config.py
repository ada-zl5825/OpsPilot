from __future__ import annotations

import os


def env(name: str, default: str) -> str:
    return os.environ.get(name, default)


SERVICE_NAME = env("SERVICE_NAME", "lab")
SERVICE_VERSION = env("SERVICE_VERSION", "1.0.0")
REDIS_URL = env("REDIS_URL", "redis://redis:6379/0")
DATABASE_URL = env("DATABASE_URL", "postgresql://opspilot:opspilot@postgres:5432/opspilot")
OTEL_ENDPOINT = env("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
GATEWAY_URL = env("GATEWAY_URL", "http://gateway:8080")
CHECKOUT_URL = env("CHECKOUT_URL", "http://checkout:8081")
PAYMENT_URL = env("PAYMENT_URL", "http://payment:8082")
INVENTORY_URL = env("INVENTORY_URL", "http://inventory:8083")
NOTIFICATION_URL = env("NOTIFICATION_URL", "http://notification:8084")
DB_POOL_MAX = int(env("DB_POOL_MAX", "3"))
PAYMENT_TIMEOUT_SEC = float(env("PAYMENT_TIMEOUT_SEC", "2.0"))
CACHE_DELAY_SEC = float(env("CACHE_DELAY_SEC", "2.0"))
PAYMENT_HOLD_SEC = float(env("PAYMENT_HOLD_SEC", "6.0"))
FLAG_KEY = "lab:flags"
VERSION_KEY = "lab:checkout:version"
RELEASED_AT_KEY = "lab:checkout:released_at"
ACTIVE_SCENARIO_KEY = "lab:active_scenario"
INJECTED_AT_KEY = "lab:injected_at"
