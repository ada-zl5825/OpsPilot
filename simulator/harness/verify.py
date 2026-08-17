from __future__ import annotations

import time
from dataclasses import dataclass, field

from benchmarks.datasets.check_integrity import check_integrity

from opspilot.domain.incidents import IncidentScenario
from opspilot.lab.scenarios import REQUIRED_SCENARIO_IDS, load_scenarios
from opspilot.verification.recovery import verify_recovery
from simulator.harness.client import LabClient, metric_value
from simulator.services.common.tokens import SCENARIO_TOKENS

HEALTHY_ORDER_BUDGET_SEC = 1.2
S02_SLOW_SEC = 1.5


@dataclass
class ScenarioCycleResult:
    scenario_id: str
    cycle: int
    injected: bool
    fault_visible: bool
    token_found: bool
    recovered: bool
    recovery_passed: bool
    details: list[str] = field(default_factory=list)


@dataclass
class LabVerifyResult:
    integrity_errors: list[str]
    observability: dict[str, bool]
    cycles: list[ScenarioCycleResult]

    @property
    def ok(self) -> bool:
        return (
            not self.integrity_errors
            and all(self.observability.values())
            and all(
                item.injected
                and item.fault_visible
                and item.token_found
                and item.recovered
                and item.recovery_passed
                for item in self.cycles
            )
        )


def _order_outcome(client: LabClient, timeout: float = 8.0) -> tuple[int, float, dict[str, object]]:
    started = time.perf_counter()
    response = client.place_order(timeout=timeout)
    duration = time.perf_counter() - started
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    return response.status_code, duration, payload


def _token_from_order(
    scenario: IncidentScenario, payload: dict[str, object], version: dict[str, object]
) -> bool:
    code = scenario.verification_code or ""
    blob = " ".join(str(value) for value in payload.values())
    if code and code in blob:
        return True
    build_id = str(version.get("build_id", ""))
    return scenario.scenario_id == "S03" and code in build_id


def _fault_visible(scenario_id: str, status_code: int, duration: float) -> bool:
    if scenario_id == "S01":
        return status_code == 503
    if scenario_id == "S02":
        return status_code == 200 and duration >= S02_SLOW_SEC
    if scenario_id == "S03":
        return status_code == 500
    if scenario_id == "S04":
        return status_code == 504
    return False


def _recovery_observations(client: LabClient, scenario: IncidentScenario) -> dict[str, str]:
    status_code, duration, _payload = _order_outcome(client)
    version = client.checkout_version()
    metrics = client.checkout_metrics()
    available = metric_value(metrics, "checkout_db_pool_available") or 0.0
    observations: dict[str, str] = {}
    for check in scenario.recovery_checks:
        if check.success_criteria.startswith("status=="):
            observations[check.check_id] = f"status=={status_code}"
        elif check.success_criteria.startswith("version=="):
            observations[check.check_id] = f"version=={version.get('version')}"
        elif check.success_criteria == ">0":
            observations[check.check_id] = ">0" if available > 0 else "0"
        elif check.success_criteria.endswith("s") and check.success_criteria.startswith("<"):
            budget = float(check.success_criteria[1:-1])
            observations[check.check_id] = (
                check.success_criteria if duration < budget else f"{duration:.3f}s"
            )
        else:
            observations[check.check_id] = ""
    return observations


def _run_cycle(
    client: LabClient,
    scenario: IncidentScenario,
    cycle: int,
) -> ScenarioCycleResult:
    details: list[str] = []
    inject_body = client.inject(scenario.scenario_id)
    injected = (
        bool(inject_body.get("injected"))
        and client.status(scenario.scenario_id).get("injected") is True
    )
    details.append(f"inject already={inject_body.get('already')}")

    def fault_pred() -> bool:
        status_code, duration, _payload = _order_outcome(client)
        return _fault_visible(scenario.scenario_id, status_code, duration)

    visible = client.wait_until(fault_pred, timeout_sec=20)
    status_code, duration, payload = _order_outcome(client)
    version = client.checkout_version()
    token_found = _token_from_order(scenario, payload, version)
    if not token_found:
        token_found = client.loki_has(scenario.verification_code or "")
    details.append(f"fault status={status_code} duration={duration:.3f}s token={token_found}")

    reset_body = client.reset(scenario.scenario_id)
    reset_done = client.status(scenario.scenario_id).get("injected") is False
    details.append(f"reset already={reset_body.get('already')}")

    def recovered_pred() -> bool:
        status_code, duration, _payload = _order_outcome(client)
        if scenario.scenario_id == "S03" and client.checkout_version().get("version") != "1.4.1":
            return False
        if scenario.scenario_id == "S02":
            return status_code == 200 and duration < HEALTHY_ORDER_BUDGET_SEC
        return status_code == 200

    recovered = reset_done and client.wait_until(recovered_pred, timeout_sec=20)
    observations = _recovery_observations(client, scenario)
    checks = verify_recovery(scenario.recovery_checks, observations)
    recovery_passed = recovered and all(item.passed for item in checks)
    if not recovery_passed:
        details.append(f"recovery observations={observations}")
    return ScenarioCycleResult(
        scenario_id=scenario.scenario_id,
        cycle=cycle,
        injected=bool(injected),
        fault_visible=visible,
        token_found=token_found,
        recovered=recovered,
        recovery_passed=recovery_passed,
        details=details,
    )


def verify_lab(cycles: int = 2, client: LabClient | None = None) -> LabVerifyResult:
    integrity_errors = check_integrity()
    owned = client is None
    client = client or LabClient()
    try:
        if not client.controller_healthy():
            return LabVerifyResult(
                integrity_errors=integrity_errors or ["controller is not healthy"],
                observability={},
                cycles=[],
            )
        client.reset_all()
        observability = {
            "prometheus": False,
            "loki": False,
            "tempo": False,
        }

        def prom_ready() -> bool:
            try:
                payload = client.prometheus_query("up")
                return payload.get("status") == "success"
            except Exception:
                return False

        observability["prometheus"] = client.wait_until(prom_ready, timeout_sec=30)
        time.sleep(3)
        observability["loki"] = client.ready("http://127.0.0.1:3100/ready")
        observability["tempo"] = (
            client.ready("http://127.0.0.1:3200/ready") or client.tempo_has_traces()
        )

        results: list[ScenarioCycleResult] = []
        scenarios = {item.scenario_id: item for item in load_scenarios()}
        for scenario_id in REQUIRED_SCENARIO_IDS:
            scenario = scenarios[scenario_id]
            assert SCENARIO_TOKENS[scenario_id] == scenario.verification_code
            client.reset_all()
            time.sleep(0.8)
            for cycle in range(1, cycles + 1):
                results.append(_run_cycle(client, scenario, cycle))
                client.reset(scenario_id)
                time.sleep(0.4)
        return LabVerifyResult(
            integrity_errors=integrity_errors,
            observability=observability,
            cycles=results,
        )
    finally:
        if owned:
            client.close()


def format_report(result: LabVerifyResult) -> str:
    lines = ["lab verify"]
    if result.integrity_errors:
        lines.append("integrity: FAIL")
        lines.extend(f"  - {error}" for error in result.integrity_errors)
    else:
        lines.append("integrity: ok")
    for name, ok in result.observability.items():
        lines.append(f"observability {name}: {'ok' if ok else 'FAIL'}")
    for item in result.cycles:
        flag = (
            "ok"
            if (
                item.injected
                and item.fault_visible
                and item.token_found
                and item.recovered
                and item.recovery_passed
            )
            else "FAIL"
        )
        lines.append(
            f"{item.scenario_id} cycle {item.cycle}: {flag} "
            f"inject={item.injected} fault={item.fault_visible} "
            f"token={item.token_found} recover={item.recovered} checks={item.recovery_passed}"
        )
        lines.extend(f"  {detail}" for detail in item.details)
    lines.append("result: ok" if result.ok else "result: FAIL")
    return "\n".join(lines)


def run_and_print(cycles: int = 2) -> int:
    result = verify_lab(cycles=cycles)
    print(format_report(result))
    return 0 if result.ok else 1
