"""
INTELLI-CREDIT Backend — FastAPI Entry Point
Main application with CORS, router mounting, and startup events.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import settings
from middleware.auth import initialize_firebase
from ml.model_loader import load_all_models


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # --- Startup ---
    print("=" * 50)
    print("🚀 INTELLI-CREDIT Backend Starting...")
    print(f"   Environment: {settings.APP_ENV}")
    print("=" * 50)

    # Verify all dependencies are installed
    from check_dependencies import check_dependencies
    deps_ok = check_dependencies(auto_install=True)
    if not deps_ok:
        print("⚠ Some dependencies could not be installed — server may have issues")

    # Initialize Firebase Auth
    initialize_firebase()

    # Load ML models
    load_all_models()

    print("✅ Backend ready!")
    yield

    # --- Shutdown ---
    print("👋 INTELLI-CREDIT Backend shutting down...")


# --- Create FastAPI App ---
app = FastAPI(
    title="INTELLI-CREDIT API",
    description="AI-Powered Corporate Credit Decisioning Engine for Indian Banks",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Mount Routers ---
from api.pre_qual import router as pre_qual_router
from api.documents import router as documents_router
from api.field_visit import router as field_visit_router
from api.analysis import router as analysis_router
from api.cam import router as cam_router
from api.risk_score import router as risk_score_router
from api.decisions import router as decisions_router
from api.applications import router as applications_router

app.include_router(pre_qual_router)
app.include_router(documents_router)
app.include_router(field_visit_router)
app.include_router(analysis_router)
app.include_router(cam_router)
app.include_router(risk_score_router)
app.include_router(decisions_router)
app.include_router(applications_router)


# --- Health Check ---
@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "INTELLI-CREDIT API",
        "version": "3.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    from ml.model_loader import model_registry
    return {
        "status": "healthy",
        "environment": settings.APP_ENV,
        "models": model_registry.status(),
    }
