"""Explicit CORS allowlist for the browser-based GIS portal."""
import os
from fastapi.middleware.cors import CORSMiddleware

def allowed_origins() -> list[str]:
    raw = os.getenv("AGRINEXA_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    origins = [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]
    if any(origin == "*" or not origin.startswith(("http://", "https://")) for origin in origins):
        raise RuntimeError("AGRINEXA_CORS_ORIGINS must contain explicit HTTP(S) origins")
    return origins

def configure_cors(app) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
