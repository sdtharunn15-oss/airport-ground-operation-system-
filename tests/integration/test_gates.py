from datetime import datetime, timedelta, timezone

from app.core.security import hash_password, create_access_token
from app.models.user import User
from app.models.airport import Airport
from app.models.terminal import Terminal
from app.models.flight import Flight
from app.models.gate import Gate
from app.utils.enums import UserRole


def create_gate_test_data(db):
    user = User(
        full_name="Gate Test Admin",
        email="gate_admin_test@example.com",
        hashed_password=hash_password("TestPassword123!"),
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    airport = Airport(
        iata_code="GTA",
        name="Gate Test Airport",
        city="Chennai",
        country="India",
        timezone="Asia/Kolkata",
    )
    db.add(airport)
    db.commit()
    db.refresh(airport)

    terminal = Terminal(
        airport_id=airport.id,
        code="TGT",
        name="Gate Test Terminal",
        capacity=100,
    )
    db.add(terminal)
    db.commit()
    db.refresh(terminal)

    flight = Flight(
        flight_number="GT100",
        airline="Test Airways",
        origin_airport_id=airport.id,
        destination_airport_id=airport.id,
        terminal_id=terminal.id,
        scheduled_departure=datetime.now(timezone.utc) + timedelta(hours=3),
        scheduled_arrival=datetime.now(timezone.utc) + timedelta(hours=5),
    )
    db.add(flight)
    db.commit()
    db.refresh(flight)

    token = create_access_token(str(user.id))

    return terminal, flight, token


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_gate(client, db):
    terminal, flight, token = create_gate_test_data(db)

    response = client.post(
        "/api/v1/gates",
        json={
            "terminal_id": terminal.id,
            "gate_number": "G01",
            "gate_name": "International Gate 1",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    assert response.json()["gate_number"] == "G01"


def test_list_gates(client, db):
    terminal, flight, token = create_gate_test_data(db)

    response = client.get(
        "/api/v1/gates",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["items"] == []


def test_create_duplicate_gate(client, db):
    terminal, flight, token = create_gate_test_data(db)

    payload = {
        "terminal_id": terminal.id,
        "gate_number": "G02",
        "gate_name": "Gate Two",
    }

    first = client.post(
        "/api/v1/gates",
        json=payload,
        headers=auth_headers(token),
    )

    second = client.post(
        "/api/v1/gates",
        json=payload,
        headers=auth_headers(token),
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_gate_assignment_and_release(client, db):
    terminal, flight, token = create_gate_test_data(db)

    gate = Gate(
        terminal_id=terminal.id,
        gate_number="G03",
        gate_name="Gate Three",
    )
    db.add(gate)
    db.commit()
    db.refresh(gate)

    assignment = client.post(
        "/api/v1/gates/assignments",
        json={
            "gate_id": gate.id,
            "flight_id": flight.id,
            "remarks": "Test assignment",
        },
        headers=auth_headers(token),
    )

    assert assignment.status_code == 201
    assignment_id = assignment.json()["id"]

    release = client.post(
        f"/api/v1/gates/assignments/{assignment_id}/release",
        headers=auth_headers(token),
    )

    assert release.status_code == 200
    assert release.json()["status"] == "released"


def test_gate_assignment_history(client, db):
    terminal, flight, token = create_gate_test_data(db)

    response = client.get(
        "/api/v1/gates/assignments/history",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_get_nonexistent_gate(client, db):
    terminal, flight, token = create_gate_test_data(db)

    response = client.get(
        "/api/v1/gates/999999",
        headers=auth_headers(token),
    )

    assert response.status_code == 404