"""Tests End-to-End pour le Patient Simulator déployé.

Ces tests s'executent contre un service reel déployé sur Google Cloud Run.
Ils necessitent la variable d'environnement SERVICE_URL.

Usage:
    SERVICE_URL=$(gcloud run services describe patient-simulator --region=europe-west1 --format='value(status.url)') uv run pytest tests/test_e2e.py -v
"""

import os

import httpx
import pytest

# URL du service déployé (requise)
SERVICE_URL = os.getenv("SERVICE_URL")


@pytest.fixture
def service_url():
    """Retourne l'URL du service déployé."""
    if not SERVICE_URL:
        pytest.skip("SERVICE_URL non définie - tests E2E ignores")
    return SERVICE_URL


class TestRootEndpointE2E:
    """Tests E2E pour l'endpoint / (health check)."""

    def test_health_check_returns_valid_response(self, service_url):
        """Test: L'endpoint / retourne une réponse valide."""
        response = httpx.get(f"{service_url}/", timeout=10.0)

        assert response.status_code == 200
        data = response.json()

        assert data["service"] == "Patient Simulator"
        assert data["status"] == "running"
        assert data["version"] == "1.0.0"


class TestStatusEndpointE2E:
    """Tests E2E pour l'endpoint /status."""

    def test_status_returns_valid_response(self, service_url):
        """Test: L'endpoint /status retourne une réponse valide."""
        response = httpx.get(f"{service_url}/status", timeout=10.0)

        assert response.status_code == 200
        data = response.json()

        assert "glucose_level" in data
        assert "insulin_active" in data
        assert "carbs_active" in data
        assert "last_update" in data

        # Vérifier les limites physiologiques
        assert 20.0 <= data["glucose_level"] <= 600.0
        assert data["insulin_active"] >= 0
        assert data["carbs_active"] >= 0

    def test_status_response_time(self, service_url):
        """Test: L'endpoint /status repond en moins de 10 secondes."""
        import time

        start = time.time()
        response = httpx.get(f"{service_url}/status", timeout=15.0)
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 10.0, f"Temps de réponse trop long: {elapsed:.2f}s"


class TestInjectEndpointE2E:
    """Tests E2E pour l'endpoint /inject."""

    def test_inject_returns_valid_response(self, service_url):
        """Test: L'endpoint /inject retourne une réponse valide."""
        response = httpx.post(
            f"{service_url}/inject",
            json={"dose": 5.0},
            timeout=10.0,
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "5.0" in data["message"]

    def test_inject_validates_dose(self, service_url):
        """Test: L'endpoint /inject valide la dose."""
        response = httpx.post(
            f"{service_url}/inject",
            json={"dose": 100.0},  # Trop élevée
            timeout=10.0,
        )

        assert response.status_code == 422


class TestConsumeEndpointE2E:
    """Tests E2E pour l'endpoint /consume."""

    def test_consume_returns_valid_response(self, service_url):
        """Test: L'endpoint /consume retourne une réponse valide."""
        response = httpx.post(
            f"{service_url}/consume",
            json={"carbs": 60.0},
            timeout=10.0,
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "60" in data["message"]

    def test_consume_validates_carbs(self, service_url):
        """Test: L'endpoint /consume valide les glucides."""
        response = httpx.post(
            f"{service_url}/consume",
            json={"carbs": 500.0},  # Trop élevés
            timeout=10.0,
        )

        assert response.status_code == 422


class TestOpenAPIE2E:
    """Tests E2E pour la documentation OpenAPI."""

    def test_openapi_docs_available(self, service_url):
        """Test: La documentation Swagger est accessible."""
        response = httpx.get(f"{service_url}/docs", timeout=10.0)
        assert response.status_code == 200

    def test_openapi_json_available(self, service_url):
        """Test: Le schema OpenAPI JSON est accessible."""
        response = httpx.get(f"{service_url}/openapi.json", timeout=10.0)
        assert response.status_code == 200
        data = response.json()
        assert "paths" in data
        assert "/status" in data["paths"]
        assert "/inject" in data["paths"]
        assert "/consume" in data["paths"]
        assert "/reset" in data["paths"]