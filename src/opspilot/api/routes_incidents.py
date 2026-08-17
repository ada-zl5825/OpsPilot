from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from opspilot.api.dependencies import investigation_store, settings
from opspilot.domain.incidents import IncidentRun
from opspilot.investigation.replay import replay_store
from opspilot.investigation.runner import cancel_incident_run, create_incident_run
from opspilot.investigation.store import InvestigationStore
from opspilot.settings import Settings

router = APIRouter(tags=["incidents"])
StoreDep = Annotated[InvestigationStore, Depends(investigation_store)]
SettingsDep = Annotated[Settings, Depends(settings)]


class CreateIncidentRequest(BaseModel):
    scenario_id: str | None = None
    source: Literal["benchmark", "manual", "alert"] = "manual"


class IncidentResponse(BaseModel):
    run_id: UUID
    scenario_id: str | None
    source: str
    status: str
    model: str
    prompt_version: str
    tool_catalog_version: str
    final_diagnosis: dict[str, Any] | None = None
    recovery_verified: bool = False


def _to_response(run: IncidentRun) -> IncidentResponse:
    diagnosis = run.final_diagnosis.model_dump(mode="json") if run.final_diagnosis else None
    return IncidentResponse(
        run_id=run.run_id,
        scenario_id=run.scenario_id,
        source=run.source,
        status=run.status.value,
        model=run.model,
        prompt_version=run.prompt_version,
        tool_catalog_version=run.tool_catalog_version,
        final_diagnosis=diagnosis,
        recovery_verified=run.recovery_verified,
    )


@router.post("/incidents", status_code=201)
def create_incident(
    payload: CreateIncidentRequest,
    store: StoreDep,
    app_settings: SettingsDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> IncidentResponse:
    _ = idempotency_key
    run = create_incident_run(
        store,
        scenario_id=payload.scenario_id,
        source=payload.source,
        model=app_settings.holmes_model,
    )
    return _to_response(run)


@router.get("/incidents/{run_id}")
def get_incident(
    run_id: UUID,
    store: StoreDep,
) -> IncidentResponse:
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="incident run not found")
    return _to_response(run)


@router.get("/incidents/{run_id}/events")
def list_events(
    run_id: UUID,
    store: StoreDep,
) -> dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="incident run not found")
    replayed = replay_store(store, run_id)
    return {
        "run_id": str(run_id),
        "status": replayed.status.value,
        "stop_reason": replayed.stop_reason.value,
        "successful": replayed.successful,
        "events": [event.model_dump(mode="json") for event in replayed.events],
        "evidence": [item.model_dump(mode="json") for item in replayed.evidence],
    }


@router.post("/incidents/{run_id}/cancel")
def cancel_incident(
    run_id: UUID,
    store: StoreDep,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> IncidentResponse:
    _ = idempotency_key
    try:
        run = cancel_incident_run(store, run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="incident run not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _to_response(run)
