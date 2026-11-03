# patient-simulator
Patient Simulator - Système physique pour la boucle fermée de gestion d'insuline

# Patient Simulator

Système physique pour la boucle fermée de gestion d'insuline. Simule le métabolisme d'un patient diabétique de type 1.

## Description

Le Patient Simulator expose une API REST qui simule le metabolisme glycemique. Les autres services (CGM, Pump, Bolus Controller) interagissent avec lui pour lire la glycemie et modifier l'etat physiologique.

## Endpoints

| Endpoint | Methode | Description |
|----------|---------|-------------|
| `/` | GET | Health check du service |
| `/status` | GET | Retourne l'etat actuel du patient (glycemie, insuline active, glucides actifs) |
| `/inject` | POST | Injecte de l'insuline (dose en unites) |
| `/consume` | POST | Simule la consommation de glucides (carbs en grammes) |
| `/reset` | POST | Réinitialise l'état du patient à l'état initial |
| `/docs` | GET | Documentation Swagger |

## Configuration

Le service utilise Dynaconf pour la configuration. Les paramètres peuvent être surchargés via variables d'environnement préfixées par `PATIENT_`.

| Variable | Description | Defaut |
|----------|-------------|--------|
| `PATIENT_FIRESTORE_DATABASE` | Nom de la base Firestore | patient-simulator-db |
| `PATIENT_MAX_INSULIN_DOSE_U` | Dose max d'insuline | 10.0 |
| `PATIENT_MAX_CARBS_PER_MEAL_G` | Glucides max par repas | 300.0 |

## Developpement

### Installation

    git clone https://github.com/VOTRE_USERNAME/patient-simulator.git
    cd patient-simulator
    uv sync

### Configuration GCP

    gcloud auth application-default login

### Lancer le service

    uv run uvicorn main:app --reload

### Tests

    # Tests unitaires et integration
    uv run pytest tests/test_unit.py tests/test_integration.py -v

    # Tests E2E (service deploye)
    SERVICE_URL=$(gcloud run services describe patient-simulator --region=europe-west1 --format='value(status.url)') uv run pytest tests/test_e2e.py -v

## Deploiement

    gcloud run deploy patient-simulator \
      --source . \
      --region europe-west1 \
      --allow-unauthenticated

## Architecture

Le Patient Simulator est le système physique de la boucle fermée :

    ┌─────────────┐                          ┌───────────────────┐
    │ CGM Service │ ──── GET /status ──────> │ Patient Simulator │
    └─────────────┘                          └───────────────────┘

    ┌──────────────┐                         ┌───────────────────┐
    │ Pump Service │ ──── POST /inject ────> │ Patient Simulator │
    └──────────────┘                         └───────────────────┘

## Technologies

- **Framework** : FastAPI (Python 3.11)
- **Persistance** : Google Cloud Firestore
- **Configuration** : Dynaconf
- **Deploiement** : Google Cloud Run (europe-west1)
- **Observabilite** : Cloud Logging

## Tests

| Type | Fichier | Nombre |
|------|---------|--------|
| Unitaires | test_unit.py | 19 |
| Integration | test_integration.py | 8 |
| E2E | test_e2e.py | 9 |
| **Total** | | **36** |