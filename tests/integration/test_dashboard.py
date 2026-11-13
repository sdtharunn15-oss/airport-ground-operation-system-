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
def dashboard_test_data():
    db = SessionLocal()
    suffix = secrets.token_hex(5)

    try:
        manager = User(
            full_name="Dashboard Test Manager",
            email=f"dashboard-manager-{suffix}@example.com",
            hashed_password=hash_password("TestPassword123"),
            role=UserRole.AIRPORT_OPERATIONS_MANAGER,
            is_active=True,
            is_verified=True,
        )

        agent = User(
            full_name="Dashboard Test Agent",
            email=f"dashboard-agent-{suffix}@example.com",
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


def test_dashboard_summary_success(dashboard_test_data):
    response = client.get(
        "/api/v1/dashboard/summary",
        headers=auth(dashboard_test_data["manager_token"]),
    )

    assert response.status_code == 200, response.text

    result = response.json()

    expected_sections = [
        "flights",
        "passengers",
        "baggage",
        "gates",
        "counters",
        "ground_staff",
        "ground_tasks",
        "aircraft_turnarounds",
        "ground_equipment",
        "incidents",
        "flight_delays",
        "resource_allocations",
    ]

    for section in expected_sections:
        assert section in result
        assert "total" in result[section]


def test_dashboard_requires_authentication():
    response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == 401


def test_dashboard_rejects_unauthorized_role(dashboard_test_data):
    response = client.get(
        "/api/v1/dashboard/summary",
        headers=auth(dashboard_test_data["agent_token"]),
    )

    assert response.status_code == 403


def test_dashboard_summary_contains_valid_counts(dashboard_test_data):
    response = client.get(
        "/api/v1/dashboard/summary",
        headers=auth(dashboard_test_data["manager_token"]),
    )

    assert response.status_code == 200, response.text

    result = response.json()

    for section in result.values():
        assert isinstance(section["total"], int)
        assert section["total"] >= 0

    assert isinstance(
        result["flight_delays"]["average_delay_minutes"],
        (int, float),
    )
    assert result["flight_delays"]["average_delay_minutes"] >= 0
