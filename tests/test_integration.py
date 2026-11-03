"""Tests d'integration pour les endpoints API avec Firestore mocke."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from fastapi.testclient import TestClient


class MockFirestoreDocument:
    """Mock pour un document Firestore."""
    def __init__(self, data=None, exists=True):
        self._data = data
        self.exists = exists

    def to_dict(self):
        return self._data


class MockFirestoreDocRef:
    """Mock pour une reference de document Firestore."""
    def __init__(self, data=None, exists=True):
        self._data = data
        self._exists = exists

    def get(self):
        return MockFirestoreDocument(self._data, self._exists)

    def set(self, data):
        self._data = data


class MockFirestoreCollection:
    """Mock pour une collection Firestore."""
    def __init__(self):
        self._docs = {}

    def document(self, doc_id):
        if doc_id not in self._docs:
            self._docs[doc_id] = MockFirestoreDocRef(exists=False)
        return self._docs[doc_id]


class MockFirestoreClient:
    """Mock pour le client Firestore."""
    def __init__(self, *args, **kwargs):
        self._collections = {}

    def collection(self, name):
        if name not in self._collections:
            self._collections[name] = MockFirestoreCollection()
        return self._collections[name]


# Appliquer le mock AVANT d'importer main
with patch('google.cloud.firestore.Client', MockFirestoreClient):
    from main import app


@pytest.fixture
def client():
    """Client de test FastAPI avec Firestore mocke."""
    # Remplace aussi le client deja cree si main a ete importe par un autre fichier de tests
    with patch('main.db', MockFirestoreClient()):
        yield TestClient(app)


class TestRootEndpoint:
    """Tests d'integration pour l'endpoint / (health check)."""

    def test_health_check_returns_200(self, client):
        """Test: L'endpoint / retourne 200."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Patient Simulator"
        assert data["status"] == "running"
        assert data["version"] == "1.0.0"


class TestStatusEndpoint:
    """Tests d'integration pour l'endpoint /status."""

    def test_status_returns_initial_state(self, client):
        """Test: L'endpoint /status retourne un etat initial valide."""
        response = client.get("/status")

        assert response.status_code == 200
        data = response.json()

        # Vérifier les champs obligatoires
        assert "glucose_level" in data
        assert "insulin_active" in data
        assert "carbs_active" in data
        assert "last_update" in data

        # Vérifier les limites physiologiques
        assert 20 <= data["glucose_level"] <= 600
        assert data["insulin_active"] >= 0
        assert data["carbs_active"] >= 0


class TestInjectEndpoint:
    """Tests d'integration pour l'endpoint /inject."""

    def test_inject_valid_dose(self, client):
        """Test: Injection d'une dose valide."""
        response = client.post("/inject", json={"dose": 5.0})

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "5.0" in data["message"]

    def test_inject_invalid_dose_too_high(self, client):
        """Test: Injection d'une dose trop elevee retourne 422."""
        response = client.post("/inject", json={"dose": 100.0})

        assert response.status_code == 422

    def test_inject_invalid_dose_negative(self, client):
        """Test: Injection d'une dose negative retourne 422."""
        response = client.post("/inject", json={"dose": -5.0})

        assert response.status_code == 422


class TestConsumeEndpoint:
    """Tests d'integration pour l'endpoint /consume."""

    def test_consume_valid_carbs(self, client):
        """Test: Consommation de glucides valide."""
        response = client.post("/consume", json={"carbs": 60.0})

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "60" in data["message"]

    def test_consume_invalid_carbs_too_high(self, client):
        """Test: Consommation de glucides trop elevee retourne 422."""
        response = client.post("/consume", json={"carbs": 500.0})

        assert response.status_code == 422

    def test_consume_invalid_carbs_negative(self, client):
        """Test: Consommation de glucides negative retourne 422."""
        response = client.post("/consume", json={"carbs": -30.0})

        assert response.status_code == 422