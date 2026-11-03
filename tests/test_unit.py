"""Tests unitaires pour les modeles Pydantic et la logique metabolique."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

# Les tests unitaires n'utilisent pas Firestore : on remplace le client AVANT d'importer main
with patch('google.cloud.firestore.Client', MagicMock()):
    from main import (
        PatientState,
        InjectRequest,
        ConsumeRequest,
        update_patient_state,
        settings,
    )


class TestPatientStateModel:
    """Tests unitaires pour le modele PatientState."""

    def test_valid_patient_state(self):
        """Test: Création d'un état patient valide."""
        state = PatientState(
            glucose_level=100.0,
            insulin_active=2.0,
            carbs_active=30.0,
        )
        assert state.glucose_level == 100.0
        assert state.insulin_active == 2.0
        assert state.carbs_active == 30.0
        assert state.last_update is not None

    def test_glucose_minimum_valid(self):
        """Test: Glycemie minimum valide (20 mg/dL)."""
        state = PatientState(
            glucose_level=settings.MIN_GLUCOSE_LEVEL_MG_DL,
            insulin_active=0.0,
            carbs_active=0.0,
        )
        assert state.glucose_level == settings.MIN_GLUCOSE_LEVEL_MG_DL

    def test_glucose_maximum_valid(self):
        """Test: Glycemie maximum valide (600 mg/dL)."""
        state = PatientState(
            glucose_level=settings.MAX_GLUCOSE_LEVEL_MG_DL,
            insulin_active=0.0,
            carbs_active=0.0,
        )
        assert state.glucose_level == settings.MAX_GLUCOSE_LEVEL_MG_DL

    def test_glucose_below_minimum(self):
        """Test: Glycemie en dessous du minimum leve une erreur."""
        with pytest.raises(ValueError):
            PatientState(
                glucose_level=settings.MIN_GLUCOSE_LEVEL_MG_DL - 0.1,
                insulin_active=0.0,
                carbs_active=0.0,
            )

    def test_glucose_above_maximum(self):
        """Test: Glycemie au dessus du maximum leve une erreur."""
        with pytest.raises(ValueError):
            PatientState(
                glucose_level=settings.MAX_GLUCOSE_LEVEL_MG_DL + 0.1,
                insulin_active=0.0,
                carbs_active=0.0,
            )

    def test_insulin_active_negative(self):
        """Test: Insuline active negative leve une erreur."""
        with pytest.raises(ValueError):
            PatientState(
                glucose_level=100.0,
                insulin_active=-1.0,
                carbs_active=0.0,
            )


class TestInjectRequestModel:
    """Tests unitaires pour le modele InjectRequest."""

    def test_valid_dose(self):
        """Test: Dose d'insuline valide."""
        request = InjectRequest(dose=5.0)
        assert request.dose == 5.0

    def test_dose_at_maximum(self):
        """Test: Dose au maximum autorise."""
        request = InjectRequest(dose=settings.MAX_INSULIN_DOSE_U)
        assert request.dose == settings.MAX_INSULIN_DOSE_U

    def test_dose_above_maximum(self):
        """Test: Dose au dessus du maximum leve une erreur."""
        with pytest.raises(ValueError):
            InjectRequest(dose=settings.MAX_INSULIN_DOSE_U + 0.1)

    def test_dose_zero_or_negative(self):
        """Test: Dose zero ou negative leve une erreur."""
        with pytest.raises(ValueError):
            InjectRequest(dose=0.0)
        with pytest.raises(ValueError):
            InjectRequest(dose=-1.0)


class TestConsumeRequestModel:
    """Tests unitaires pour le modele ConsumeRequest."""

    def test_valid_carbs(self):
        """Test: Quantite de glucides valide."""
        request = ConsumeRequest(carbs=60.0)
        assert request.carbs == 60.0

    def test_carbs_at_maximum(self):
        """Test: Glucides au maximum autorise."""
        request = ConsumeRequest(carbs=settings.MAX_CARBS_PER_MEAL_G)
        assert request.carbs == settings.MAX_CARBS_PER_MEAL_G

    def test_carbs_above_maximum(self):
        """Test: Glucides au dessus du maximum leve une erreur."""
        with pytest.raises(ValueError):
            ConsumeRequest(carbs=settings.MAX_CARBS_PER_MEAL_G + 0.1)

    def test_carbs_zero_or_negative(self):
        """Test: Glucides zero ou negatifs leve une erreur."""
        with pytest.raises(ValueError):
            ConsumeRequest(carbs=0.0)
        with pytest.raises(ValueError):
            ConsumeRequest(carbs=-10.0)


class TestUpdatePatientState:
    """Tests unitaires pour la fonction update_patient_state (logique metabolique)."""

    def test_no_update_if_time_too_short(self):
        """Test: Pas de mise a jour si le temps ecoule est trop court."""
        state = PatientState(
            glucose_level=100.0,
            insulin_active=5.0,
            carbs_active=30.0,
            last_update=datetime.now(timezone.utc),
        )
        original_glucose = state.glucose_level

        updated = update_patient_state(state)

        # La glycemie ne doit pas changer si le temps est trop court
        assert updated.glucose_level == original_glucose

    def test_carbs_increase_glucose(self):
        """Test: Les glucides actifs augmentent la glycemie."""
        past_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        state = PatientState(
            glucose_level=100.0,
            insulin_active=0.0,
            carbs_active=30.0,
            last_update=past_time,
        )

        updated = update_patient_state(state)

        # La glycemie doit augmenter grace aux glucides
        assert updated.glucose_level > 100.0
        # Les glucides actifs doivent diminuer
        assert updated.carbs_active < 30.0

    def test_insulin_decreases_glucose(self):
        """Test: L'insuline active diminue la glycemie."""
        past_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        state = PatientState(
            glucose_level=200.0,
            insulin_active=10.0,
            carbs_active=0.0,
            last_update=past_time
        )

        updated = update_patient_state(state)

        # La glycemie doit diminuer grace a l'insuline
        assert updated.glucose_level < 200.0
        # L'insuline active doit diminuer
        assert updated.insulin_active < 10.0

    def test_glucose_clamped_to_minimum(self):
        """Test: La glycemie ne descend pas en dessous du minimum."""
        past_time = datetime.now(timezone.utc) - timedelta(minutes=60)
        state = PatientState(
            glucose_level=settings.MIN_GLUCOSE_LEVEL_MG_DL + 10,
            insulin_active=100.0,  # Beaucoup d'insuline
            carbs_active=0.0,
            last_update=past_time,
        )

        updated = update_patient_state(state)

        # La glycémie doit être clampée au minimum
        assert updated.glucose_level >= settings.MIN_GLUCOSE_LEVEL_MG_DL

    def test_glucose_clamped_to_maximum(self):
        """Test: La glycemie ne depasse pas le maximum."""
        past_time = datetime.now(timezone.utc) - timedelta(minutes=60)
        state = PatientState(
            glucose_level=settings.MAX_GLUCOSE_LEVEL_MG_DL - 10,
            insulin_active=0.0,
            carbs_active=1000.0,  # Beaucoup de glucides
            last_update=past_time,
        )

        updated = update_patient_state(state)

        # La glycémie doit être clampée au maximum
        assert updated.glucose_level <= settings.MAX_GLUCOSE_LEVEL_MG_DL


