from fastapi import FastAPI

from opspilot import __version__
from opspilot.api.routes_approvals import router as approvals_router
from opspilot.api.routes_benchmarks import router as benchmarks_router
from opspilot.api.routes_incidents import router as incidents_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="OpsPilot Incident Lab",
        version=__version__,
        description="Auditable incident investigation and controlled remediation control plane.",
    )
    app.include_router(incidents_router, prefix="/api")
    app.include_router(approvals_router, prefix="/api")
    app.include_router(benchmarks_router, prefix="/api")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__, "phase": "4"}

    return app


app = create_app()
