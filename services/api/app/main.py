
"""GAINT AgriNexa AI - FastAPI application entry point."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

# Authentication
from .auth_router import router as auth_router

# AI agents
from .agent_router import router as agent_router
from .agent_preview_router import router as agent_preview_router
from .weather_agent_router import router as weather_agent_router
from .crop_advisory_router import router as crop_advisory_router
from .market_agent_router import router as market_agent_router
from .scheme_agent_router import router as scheme_agent_router
from .escalation_agent_router import router as escalation_agent_router
from .learning_agent_router import router as learning_agent_router
from .health import router as health_router
from .observability import configure_logging, request_context_middleware
from .production_config import validate_production_configuration

# Agricultural services
from .registry_router import router as registry_router
from .geography import router as geography_router
from .gis_router import router as gis_router
from .spatial import router as spatial_router

# SCIM and field verification
from .scim_router import router as scim_router
from .field_verification_router import (
    router as field_verification_router,
)

# Configuration and security
from .cors import configure_cors
from .database import (
    DatabaseConfigurationError,
    DatabaseConnectionError,
)
from .security import (
    Role,
    AuthenticationConfigurationError,
)

LOG = logging.getLogger(__name__)
validate_production_configuration()
configure_logging()

# --------------------------------------------------
# Application initialization
# --------------------------------------------------

app = FastAPI(
    title="GAINT AgriNexa AI",
    description=(
        "Integrated Agricultural Intelligence Platform "
        "with GIS, field verification, SCIM and governed AI agents."
    ),
    version="0.1.0",
)

configure_cors(app)
app.middleware("http")(request_context_middleware)


# --------------------------------------------------
# Database exception handling
# --------------------------------------------------

async def database_unavailable(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    LOG.error(
        "Database request failed (error type: %s)",
        type(exc).__name__,
    )

    return JSONResponse(
        status_code=503,
        content={
            "detail": "Database temporarily unavailable",
        },
    )


app.add_exception_handler(
    DatabaseConfigurationError,
    database_unavailable,
)

app.add_exception_handler(
    DatabaseConnectionError,
    database_unavailable,
)

app.add_exception_handler(
    SQLAlchemyError,
    database_unavailable,
)


# --------------------------------------------------
# Authentication exception handling
# --------------------------------------------------

async def authentication_unavailable(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    LOG.error(
        "Authentication request failed (error type: %s)",
        type(exc).__name__,
    )

    return JSONResponse(
        status_code=503,
        content={
            "detail": "Authentication service temporarily unavailable",
        },
    )


app.add_exception_handler(
    AuthenticationConfigurationError,
    authentication_unavailable,
)


# --------------------------------------------------
# Authentication routes
# --------------------------------------------------

app.include_router(auth_router)


# --------------------------------------------------
# Governed AI agent routes
# --------------------------------------------------

app.include_router(agent_router)
app.include_router(agent_preview_router)

app.include_router(weather_agent_router)
app.include_router(crop_advisory_router)
app.include_router(market_agent_router)
app.include_router(scheme_agent_router)
app.include_router(escalation_agent_router)
app.include_router(learning_agent_router)


# --------------------------------------------------
# Agricultural and GIS routes
# --------------------------------------------------

app.include_router(registry_router)
app.include_router(geography_router)
app.include_router(gis_router)
app.include_router(spatial_router)


# --------------------------------------------------
# SCIM routes
# --------------------------------------------------

app.include_router(scim_router)


# --------------------------------------------------
# Field verification routes
# --------------------------------------------------

app.include_router(field_verification_router)
app.include_router(health_router)


# --------------------------------------------------
# Health endpoint
# --------------------------------------------------

@app.get("/health", tags=["System"])
def health():
    return {
        "status": "ok",
        "service": "agrinexa-api",
    }


# --------------------------------------------------
# Application metadata
# --------------------------------------------------

@app.get("/api/v1/metadata", tags=["System"])
def metadata():
    return {
        "product": "GAINT AgriNexa AI",
        "version": app.version,
        "roles": [role.value for role in Role],
        "scim_is_agent": False,
        "agents": [
            "INTAKE",
            "PROFILE",
            "WEATHER",
            "CROP_ADVISORY",
            "MARKET",
            "SCHEME",
            "ESCALATION",
            "LEARNING",
        ],
    }
