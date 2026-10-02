"""
FastAPI router for QueueLess API v1.

Aggregates sub-routers:
- auth: /api/v1/auth/*
- orgs: /api/v1/organizations/*
- services: /api/v1/services/*
- queues: /api/v1/services/{id}/queue, /api/v1/queues/*, /api/v1/tokens/*
- appointments: /api/v1/appointments/*
- analytics: /api/v1/analytics/*
- notifications: /api/v1/notifications/*
"""
from fastapi import APIRouter

from app.api.v1.routers.auth import auth
from app.api.v1.routers.orgs import orgs
from app.api.v1.routers.services import services
from app.api.v1.routers.queues import queues
from app.api.v1.routers.appointments import appointments
from app.api.v1.routers.analytics import analytics
from app.api.v1.routers.notifications import notifications
from app.api.v1.routers.shared import (
    _cache_get,
    _cache_set,
    _cache_delete,
    _ORG_LIST_KEY,
    _ORG_SVC_KEY,
)

router = APIRouter(prefix="/api/v1")

# Include direct router endpoints first (matching original router.py where services and notifications were on router)
router.include_router(services)
router.include_router(notifications)

# Include sub-routers
router.include_router(auth)
router.include_router(orgs)
router.include_router(queues)
router.include_router(appointments)
router.include_router(analytics)
