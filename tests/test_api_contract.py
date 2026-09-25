import importlib
from types import SimpleNamespace

import pytest


pytest.importorskip("fastapi")
pytest.importorskip("cv2")
pytest.importorskip("fpdf")
import cv2
import numpy as np
from fastapi.testclient import TestClient


SERVER = importlib.import_module("05_DEPLOYMENT.api.server")
CLIENT = TestClient(SERVER.app)


def test_healthcheck_is_research_only():
    response = CLIENT.get("/healthz")
    assert response.status_code == 200
    assert response.json()["mode"] == "research_only"
    assert response.json()["checkpoint_status"] == "verified"
    assert response.json()["model_ready"] is True


def test_mutations_disabled_without_configured_token(monkeypatch):
    monkeypatch.setattr(SERVER, "API_TOKEN", None)
    response = CLIENT.post("/api/v1/trigger_training")
    assert response.status_code == 503


def test_remote_training_separately_disabled(monkeypatch):
    monkeypatch.setattr(SERVER, "API_TOKEN", "test-token")
    monkeypatch.setattr(SERVER, "ALLOW_REMOTE_TRAINING", False)
    response = CLIENT.post(
        "/api/v1/trigger_training", headers={"X-API-Key": "test-token"}
    )
    assert response.status_code == 403


def test_research_pdf_is_generated_with_token(monkeypatch):
    monkeypatch.setattr(SERVER, "API_TOKEN", "test-token")
    response = CLIENT.post(
        "/api/v1/export_report",
        headers={"X-API-Key": "test-token"},
        json={
            "filename": "synthetic.png",
            "grade": "Not calculated",
            "hardware": "CPU",
            "reviewer_name": "Test",
            "count": 0,
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert response.headers["cache-control"] == "no-store"


def test_raster_inference_reports_candidates_without_clinical_grade(monkeypatch):
    class EmptyModel:
        def __call__(self, _image, **_kwargs):
            return [SimpleNamespace(boxes=None)]

    monkeypatch.setattr(SERVER, "API_TOKEN", None)
    monkeypatch.setattr(SERVER, "load_active_model", lambda device="cpu": EmptyModel())
    image = np.zeros((24, 24, 3), dtype=np.uint8)
    encoded_ok, encoded = cv2.imencode(".png", image)
    assert encoded_ok

    response = CLIENT.post(
        "/api/v1/analyze",
        files={"file": ("synthetic.png", encoded.tobytes(), "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["detections"] == []
    assert response.json()["grade"] == "Not calculated"
    assert response.headers["cache-control"] == "no-store"
