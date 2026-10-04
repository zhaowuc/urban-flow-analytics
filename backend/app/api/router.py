from fastapi import APIRouter

from backend.app.api import analysis, auth, catalog, dashboard, datasets, health, logs, predictions, realtime, reports, settings, users, warnings


api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(catalog.router)
api_router.include_router(datasets.router)
api_router.include_router(analysis.router)
api_router.include_router(predictions.router)
api_router.include_router(warnings.router)
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)
api_router.include_router(realtime.router)
api_router.include_router(users.router)
api_router.include_router(logs.router)
api_router.include_router(settings.router)
