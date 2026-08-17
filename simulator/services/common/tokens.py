"""Correlation tokens emitted into telemetry when a scenario is active.

These values must match `verification_code` in the scorer dataset. They are
never returned by controller APIs and must not appear in prompts or runbooks.
"""

SCENARIO_TOKENS = {
    "S01": "OP-S01-M4QX7C",
    "S02": "OP-S02-R8NW2H",
    "S03": "OP-S03-K2PL9D",
    "S04": "OP-S04-T9VC4E",
}

CHECKOUT_VERSION_HEALTHY = "1.4.1"
CHECKOUT_VERSION_CURRENT = "1.4.2"
CHECKOUT_SHA = {
    CHECKOUT_VERSION_HEALTHY: "9e2b110c",
    CHECKOUT_VERSION_CURRENT: "c3f91aa8",
}
