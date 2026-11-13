import secrets
import string
import pytest

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.airport import Airport
from app.models.terminal import Terminal
from app.core.security import create_access_token, hash_password
from app.utils.enums import UserRole

client = TestClient(app)


@pytest.fixture
def setup_incident_data():
    db = SessionLocal()
    suffix = secrets.token_hex(5).upper()

    user = User(
        full_name="Incident Test Manager",
        email=f"incident-manager-{suffix}@example.com",
        hashed_password=hash_password("TestPassword123"),
        role=UserRole.AIRPORT_OPERATIONS_MANAGER,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    iata_code = "".join(secrets.choice(string.ascii_uppercase) for _ in range(3))
    while db.query(Airport).filter(Airport.iata_code == iata_code).first():
        iata_code = "".join(secrets.choice(string.ascii_uppercase) for _ in range(3))

    airport = Airport(
        iata_code=iata_code,
        name=f"Incident Test Airport {suffix}",
        city="Chennai",
        country="India",
        timezone="Asia/Kolkata",
    )
    db.add(airport)
    db.commit()
    db.refresh(airport)

    terminal = Terminal(
        airport_id=airport.id,
        code=f"IT{suffix[:6]}",
        name="Incident Test Terminal",
        capacity=100,
    )
    db.add(terminal)
    db.commit()
    db.refresh(terminal)

    token = create_access_token(subject=str(user.id))

    yield {
        "airport_id": airport.id,
        "terminal_id": terminal.id,
        "token": token,
        "suffix": suffix,
    }

    db.close()


def incident_headers(data):
    return {"Authorization": f"Bearer {data['token']}"}


def create_incident(data, code=None):
    return client.post(
        "/api/v1/operational-incidents",
        json={
            "incident_code": code or f"INC-{data['suffix']}",
            "title": "Baggage Tug Equipment Failure",
            "description": "Baggage tug stopped working near terminal.",
            "incident_type": "equipment_failure",
            "severity": "high",
            "airport_id": data["airport_id"],
            "terminal_id": data["terminal_id"],
        },
        headers=incident_headers(data),
    )


def test_create_operational_incident(setup_incident_data):
    data = setup_incident_data
    response = create_incident(data)

    assert response.status_code == 201, response.text
    result = response.json()
    assert result["incident_type"] == "equipment_failure"
    assert result["severity"] == "high"
    assert result["status"] == "reported"
    assert result["airport_id"] == data["airport_id"]


def test_list_operational_incidents(setup_incident_data):
    data = setup_incident_data
    create_response = create_incident(data)
    assert create_response.status_code == 201, create_response.text

    response = client.get(
        "/api/v1/operational-incidents",
        headers=incident_headers(data),
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] >= 1


def test_get_operational_incident(setup_incident_data):
    data = setup_incident_data
    create_response = create_incident(data)
    incident_id = create_response.json()["id"]

    response = client.get(
        f"/api/v1/operational-incidents/{incident_id}",
        headers=incident_headers(data),
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == incident_id


def test_update_operational_incident(setup_incident_data):
    data = setup_incident_data
    create_response = create_incident(data)
    incident_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/operational-incidents/{incident_id}",
        json={
            "title": "Updated Equipment Failure",
            "severity": "critical",
            "status": "under_investigation",
        },
        headers=incident_headers(data),
    )

    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Updated Equipment Failure"
    assert response.json()["severity"] == "critical"
    assert response.json()["status"] == "under_investigation"


def test_delete_operational_incident(setup_incident_data):
    data = setup_incident_data
    create_response = create_incident(data)
    incident_id = create_response.json()["id"]

    response = client.delete(
        f"/api/v1/operational-incidents/{incident_id}",
        headers=incident_headers(data),
    )

    assert response.status_code == 200, response.text

    get_response = client.get(
        f"/api/v1/operational-incidents/{incident_id}",
        headers=incident_headers(data),
    )
    assert get_response.status_code == 404


def test_operational_incident_full_lifecycle(setup_incident_data):
    data = setup_incident_data
    create_response = create_incident(data)
    assert create_response.status_code == 201, create_response.text

    incident_id = create_response.json()["id"]
    url = f"/api/v1/operational-incidents/{incident_id}"
    headers = incident_headers(data)

    investigation_response = client.patch(
        url,
        json={"status": "under_investigation"},
        headers=headers,
    )
    assert investigation_response.status_code == 200, investigation_response.text
    assert investigation_response.json()["status"] == "under_investigation"

    resolved_response = client.patch(
        url,
        json={
            "status": "resolved",
            "resolution_notes": "Equipment repaired and tested successfully.",
        },
        headers=headers,
    )
    assert resolved_response.status_code == 200, resolved_response.text
    assert resolved_response.json()["status"] == "resolved"
    assert resolved_response.json()["resolved_at"] is not None

    closed_response = client.patch(
        url,
        json={"status": "closed"},
        headers=headers,
    )
    assert closed_response.status_code == 200, closed_response.text
    assert closed_response.json()["status"] == "closed"


def test_duplicate_incident_code(setup_incident_data):
    data = setup_incident_data

    first_response = create_incident(data)
    assert first_response.status_code == 201, first_response.text

    duplicate_response = create_incident(data)
    assert duplicate_response.status_code == 409
    assert "Incident code already exists" in duplicate_response.text


def test_create_incident_with_invalid_airport(setup_incident_data):
    data = setup_incident_data

    response = client.post(
        "/api/v1/operational-incidents",
        json={
            "incident_code": f"INVALID-{data['suffix']}",
            "title": "Invalid Airport Incident",
            "description": "Testing invalid airport reference.",
            "incident_type": "other",
            "severity": "medium",
            "airport_id": 999999,
        },
        headers=incident_headers(data),
    )

    assert response.status_code == 404
    assert "Airport not found" in response.text

