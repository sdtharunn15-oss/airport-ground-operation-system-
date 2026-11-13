import secrets

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import create_access_token, hash_password
from app.utils.enums import UserRole

client = TestClient(app)


@pytest.fixture
def reports_test_data():
    db = SessionLocal()
    suffix = secrets.token_hex(5)

    try:
        manager = User(
            full_name="Reports Test Manager",
            email=f"reports-manager-{suffix}@example.com",
            hashed_password=hash_password("TestPassword123"),
            role=UserRole.AIRPORT_OPERATIONS_MANAGER,
            is_active=True,
            is_verified=True,
        )

        agent = User(
            full_name="Reports Test Agent",
            email=f"reports-agent-{suffix}@example.com",
            hashed_password=hash_password("TestPassword123"),
            role=UserRole.GATE_AGENT,
            is_active=True,
            is_verified=True,
        )

        db.add_all([manager, agent])
        db.commit()
        db.refresh(manager)
        db.refresh(agent)

        yield {
            "manager_token": create_access_token(str(manager.id)),
            "agent_token": create_access_token(str(agent.id)),
        }

    finally:
        db.close()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_advanced_reports_success(reports_test_data):
    response = client.get(
        "/api/v1/reports/advanced",
        headers=auth(reports_test_data["manager_token"]),
    )

    assert response.status_code == 200, response.text

    result = response.json()

    expected_sections = [
        "report_period",
        "flights",
        "passengers",
        "baggage",
        "checkins",
        "ground_operations",
        "incidents",
    ]

    for section in expected_sections:
        assert section in result


def test_advanced_reports_requires_authentication():
    response = client.get("/api/v1/reports/advanced")

    assert response.status_code == 401


def test_advanced_reports_rejects_unauthorized_role(reports_test_data):
    response = client.get(
        "/api/v1/reports/advanced",
        headers=auth(reports_test_data["agent_token"]),
    )

    assert response.status_code == 403


def test_advanced_reports_date_filter(reports_test_data):
    response = client.get(
        "/api/v1/reports/advanced",
        params={
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        },
        headers=auth(reports_test_data["manager_token"]),
    )

    assert response.status_code == 200, response.text

    result = response.json()

    assert result["report_period"]["start_date"] == "2026-01-01"
    assert result["report_period"]["end_date"] == "2026-12-31"


def test_advanced_reports_invalid_date_range(reports_test_data):
    response = client.get(
        "/api/v1/reports/advanced",
        params={
            "start_date": "2026-12-31",
            "end_date": "2026-01-01",
        },
        headers=auth(reports_test_data["manager_token"]),
    )

    assert response.status_code == 422
