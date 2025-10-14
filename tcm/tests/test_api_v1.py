"""Tests for API helpers and validation logic."""

from __future__ import annotations

import pytest
from fastapi import HTTPException, status
from starlette.applications import Starlette
from starlette.requests import Request

from tcm.app.api.models import OutputUpdateModel
from tcm.app.api import v1
from tcm.app.services.strike import StrikeTriggerOutcome


def _build_request() -> Request:
    scope = {
        "type": "http",
        "app": Starlette(),
        "path": "/dummy",
        "method": "GET",
        "headers": [],
        "client": ("test", 0),
    }
    return Request(scope)


def test_set_output_rejects_unknown_output_name() -> None:
    request = _build_request()
    payload = OutputUpdateModel(name="unknown", state=True)

    with pytest.raises(HTTPException) as excinfo:
        v1.set_output(request, payload, user=None)

    assert excinfo.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "unknown" in excinfo.value.detail


@pytest.mark.parametrize(
    "outcome,expected_status,expected_detail",
    [
        (
            StrikeTriggerOutcome(success=False, error="not_configured"),
            status.HTTP_404_NOT_FOUND,
            "Strike not configured",
        ),
        (
            StrikeTriggerOutcome(success=False, error="transistor_unavailable"),
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Strike transistor unavailable",
        ),
    ],
)
def test_trigger_strike_maps_service_errors_to_http(outcome, expected_status, expected_detail):
    request = _build_request()

    class DummyService:
        def trigger(self, strike_id: str):  # noqa: D401, ANN001 - simple stub
            return outcome

    with pytest.raises(HTTPException) as excinfo:
        v1.trigger_strike(request, "main", service=DummyService(), user=None)

    assert excinfo.value.status_code == expected_status
    assert excinfo.value.detail == expected_detail


def test_trigger_strike_raises_internal_error_for_unknown_failure() -> None:
    request = _build_request()

    class DummyService:
        def trigger(self, strike_id: str):  # noqa: D401, ANN001 - simple stub
            return StrikeTriggerOutcome(success=False, error="unexpected")

    with pytest.raises(HTTPException) as excinfo:
        v1.trigger_strike(request, "main", service=DummyService(), user=None)

    assert excinfo.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert excinfo.value.detail == "Strike trigger failed"
