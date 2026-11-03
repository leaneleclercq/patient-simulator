"""Patient Simulator - Système physique pour la boucle fermée.

Service FastAPI simulant le metabolisme d'un patient diabetique de type 1.
"""

import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dynaconf import Dynaconf
from fastapi import FastAPI, Request
from google.cloud import firestore
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# ============================================================================
# CONFIGURATION (Dynaconf)
# ============================================================================

settings = Dynaconf(
    settings_files=["settings.toml"],
    envvar_prefix="PATIENT",  # Variables d'env: PATIENT_FIRESTORE_DATABASE, etc.
)

# ============================================================================
# LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ============================================================================
# FIRESTORE CLIENT
# ============================================================================

db = firestore.Client(database=settings.FIRESTORE_DATABASE)

# ============================================================================
# SCHEMAS PYDANTIC
# ============================================================================


class PatientState(BaseModel):
    """Etat physiologique du patient."""

    glucose_level: float = Field(
        ...,
        ge=settings.MIN_GLUCOSE_LEVEL_MG_DL,
        le=settings.MAX_GLUCOSE_LEVEL_MG_DL,
        description="Glycemie en mg/dL",
    )
    insulin_active: float = Field(..., ge=0, description="Insuline active en unites")
    carbs_active: float = Field(..., ge=0, description="Glucides actifs en grammes")
    last_update: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Horodatage de la derniere mise a jour",
    )


class InjectRequest(BaseModel):
    """Requete d'injection d'insuline."""

    dose: float = Field(
        ...,
        gt=0,
        le=settings.MAX_INSULIN_DOSE_U,
        description="Dose d'insuline en unites",
    )


class ConsumeRequest(BaseModel):
    """Requete de consommation de glucides."""

    carbs: float = Field(
        ...,
        gt=0,
        le=settings.MAX_CARBS_PER_MEAL_G,
        description="Quantite de glucides en grammes",
    )

# ============================================================================
# LOGIQUE MÉTIER
# ============================================================================


def update_patient_state(state: PatientState) -> PatientState:
    """Simule l'evolution de la glycemie selon le temps ecoule."""
    now = datetime.now(timezone.utc)
    elapsed_minutes = (now - state.last_update).total_seconds() / 60

    if elapsed_minutes < settings.MIN_UPDATE_INTERVAL_MINUTES:
        return state

    # 1) Absorption des glucides - augmente la glycemie
    glucose_from_carbs = (
        min(state.carbs_active, elapsed_minutes)
        * settings.GLUCOSE_ABSORPTION_RATE_MG_PER_G_PER_MIN
    )
    state.glucose_level += glucose_from_carbs
    state.carbs_active -= min(state.carbs_active, elapsed_minutes)

    # 2) Action de l'insuline - diminue la glycemie
    insulin_decay = elapsed_minutes * settings.INSULIN_DECAY_RATE_U_PER_MIN
    glucose_decrease = (
        min(state.insulin_active, insulin_decay)
        * settings.INSULIN_ACTION_RATE_MG_PER_U_PER_MIN
    )
    state.glucose_level -= glucose_decrease
    state.insulin_active -= min(state.insulin_active, insulin_decay)

    # 3) Production basale par le foie - augmente legerement
    state.glucose_level += elapsed_minutes * settings.LIVER_GLUCOSE_PRODUCTION_MG_PER_MIN

    # 4) Clamper la glycémie dans les limites physiologiques
    state.glucose_level = max(
        settings.MIN_GLUCOSE_LEVEL_MG_DL,
        min(settings.MAX_GLUCOSE_LEVEL_MG_DL, state.glucose_level),
    )

    # 5) Mettre a jour le timestamp
    state.last_update = now

    return state


def get_patient_state(patient_id: str) -> PatientState:
    """Récupère l'état du patient depuis Firestore ou retourne un état initial."""
    doc_ref = db.collection("patients").document(patient_id)
    doc = doc_ref.get()

    if doc.exists:
        data = doc.to_dict()
        if "last_update" not in data or not isinstance(data["last_update"], datetime):
            data["last_update"] = datetime.now(timezone.utc)
        return PatientState(**data)

    # Aucun état existant - retourner un état initial sain
    logger.info("Nouveau patient %s, état initial créé", patient_id)
    return PatientState(
        glucose_level=settings.INITIAL_GLUCOSE_LEVEL_MG_DL,
        insulin_active=0.0,
        carbs_active=0.0,
        last_update=datetime.now(timezone.utc),
    )


def save_patient_state(patient_id: str, state: PatientState) -> None:
    """Sauvegarde l'etat du patient dans Firestore."""
    doc_ref = db.collection("patients").document(patient_id)
    doc_ref.set(state.model_dump())
    logger.info(
        "Etat du patient %s sauvegarde : glucose=%.1f mg/dL",
        patient_id,
        state.glucose_level,
    )


def reset_patient_state(patient_id: str) -> PatientState:
    """Réinitialise l'état du patient à l'état initial."""
    doc_ref = db.collection("patients").document(patient_id)
    doc_ref.delete()
    logger.info("Etat du patient %s réinitialisé", patient_id)
    return PatientState(
        glucose_level=settings.INITIAL_GLUCOSE_LEVEL_MG_DL,
        insulin_active=0.0,
        carbs_active=0.0,
        last_update=datetime.now(timezone.utc),
    )

# ============================================================================
# APPLICATION FASTAPI
# ============================================================================

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application."""
    # Startup
    logger.info("Demarrage du Patient Simulator")
    logger.info("Firestore database: %s", settings.FIRESTORE_DATABASE)
    yield
    # Shutdown
    logger.info("Arret du Patient Simulator")


app = FastAPI(
    title=settings.SERVICE_NAME,
    version=settings.SERVICE_VERSION,
    description="Simule le métabolisme d'un patient diabétique de type 1.",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ============================================================================
# ENDPOINTS
# ============================================================================


@app.get("/")
@limiter.limit(settings.RATE_LIMIT_ROOT)
def root(request: Request):
    """Health check du service."""
    return {
        "service": settings.SERVICE_NAME,
        "status": "running",
        "version": settings.SERVICE_VERSION,
        "message": "Le patient virtuel vous attend. Utilisez /docs pour voir l'API.",
    }


@app.get("/status", response_model=PatientState)
@limiter.limit(settings.RATE_LIMIT_STATUS)
def get_status(request: Request, patient_id: str = "demo-patient"):
    """Retourne l'etat actuel du patient."""
    state = get_patient_state(patient_id)
    updated_state = update_patient_state(state)
    save_patient_state(patient_id, updated_state)
    return updated_state


@app.post("/consume")
@limiter.limit(settings.RATE_LIMIT_ACTIONS)
def consume_carbs(
    request: Request, body: ConsumeRequest, patient_id: str = "demo-patient"
):
    """Ajoute des glucides au patient."""
    state = get_patient_state(patient_id)
    state = update_patient_state(state)
    state.carbs_active += body.carbs
    save_patient_state(patient_id, state)
    logger.info("Patient %s: ajout de %.1fg de glucides", patient_id, body.carbs)
    return {"message": f"Ajout de {body.carbs}g de glucides"}


@app.post("/inject")
@limiter.limit(settings.RATE_LIMIT_ACTIONS)
def inject_insulin(
    request: Request, body: InjectRequest, patient_id: str = "demo-patient"
):
    """Injecte de l'insuline au patient."""
    state = get_patient_state(patient_id)
    state = update_patient_state(state)
    state.insulin_active += body.dose
    save_patient_state(patient_id, state)
    logger.info("Patient %s: injection de %.1f unites", patient_id, body.dose)
    return {"message": f"Injection de {body.dose} unites"}


@app.post("/reset", response_model=PatientState)
@limiter.limit(settings.RATE_LIMIT_ACTIONS)
def reset_patient(request: Request, patient_id: str = "demo-patient"):
    """Réinitialise l'état du patient à l'état initial."""
    reset_state = reset_patient_state(patient_id)
    logger.info("Patient %s: réinitialisation effectuée", patient_id)
    return reset_state