from datetime import datetime, timedelta, timezone

from app.core.security import hash_password, create_access_token
from app.db.base import Base
from app.models.user import User
from app.models.airport import Airport
from app.models.terminal import Terminal
from app.models.flight import Flight
from app.utils.enums import UserRole


def create_counter_test_data(db):
    user = User(
        full_name="Counter Test Admin",
        email="counter_admin_test@example.com",
        hashed_password=hash_password("TestPassword123"),
        role=UserRole.AIRPORT_OPERATIONS_MANAGER,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    airport = Airport(
        iata_code="CTA",
        name="Counter Test Airport",
        city="Chennai",
        country="India",
        timezone="Asia/Kolkata",
    )
    db.add(airport)
    db.commit()
    db.refresh(airport)

    terminal = Terminal(
        airport_id=airport.id,
        code="TCT",
        name="Counter Test Terminal",
        capacity=100,
    )
    db.add(terminal)
    db.commit()
    db.refresh(terminal)

    flight = Flight(
        flight_number="CT100",
        airline="Test Airlines",
        origin_airport_id=airport.id,
        destination_airport_id=airport.id + 1,
        terminal_id=terminal.id,
        scheduled_departure=datetime.now(timezone.utc) + timedelta(days=1),
        scheduled_arrival=datetime.now(timezone.utc) + timedelta(days=1, hours=2),
    )

    destination = Airport(
        iata_code="CTB",
        name="Destination Test Airport",
        city="Bengaluru",
        country="India",
        timezone="Asia/Kolkata",
    )
    db.add(destination)
    db.commit()
    db.refresh(destination)

    flight.destination_airport_id = destination.id
    db.add(flight)
    db.commit()
    db.refresh(flight)

    token = create_access_token(str(user.id))

    return terminal, flight, token


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def counter_payload(number="C01"):
    return {
        "counter_number": number,
        "counter_name": f"Check-in Counter {number}",
        "terminal_id": None,
    }


def test_create_counter(client, db):
    terminal, flight, token = create_counter_test_data(db)

    payload = counter_payload()
    payload["terminal_id"] = terminal.id

    response = client.post(
        "/api/v1/counters",
        json=payload,
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    assert response.json()["counter_number"] == "C01"


def test_list_counters(client, db):
    terminal, flight, token = create_counter_test_data(db)

    payload = counter_payload()
    payload["terminal_id"] = terminal.id

    create_response = client.post(
        "/api/v1/counters",
        json=payload,
        headers=auth_headers(token),
    )
    assert create_response.status_code == 201

    response = client.get(
        "/api/v1/counters",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert len(response.json()["items"]) >= 1


def test_create_duplicate_counter(client, db):
    terminal, flight, token = create_counter_test_data(db)

    payload = counter_payload()
    payload["terminal_id"] = terminal.id

    first_response = client.post(
        "/api/v1/counters",
        json=payload,
        headers=auth_headers(token),
    )
    assert first_response.status_code == 201

    duplicate_response = client.post(
        "/api/v1/counters",
        json=payload,
        headers=auth_headers(token),
    )

    assert duplicate_response.status_code == 409


def test_counter_assignment_and_release(client, db):
    terminal, flight, token = create_counter_test_data(db)

    payload = counter_payload()
    payload["terminal_id"] = terminal.id

    counter_response = client.post(
        "/api/v1/counters",
        json=payload,
        headers=auth_headers(token),
    )
    assert counter_response.status_code == 201

    counter_id = counter_response.json()["id"]

    assignment_response = client.post(
        "/api/v1/counters/assignments",
        json={
            "counter_id": counter_id,
            "flight_id": flight.id,
        },
        headers=auth_headers(token),
    )

    assert assignment_response.status_code == 201
    assignment_id = assignment_response.json()["id"]

    release_response = client.post(
        f"/api/v1/counters/assignments/{assignment_id}/release",
        headers=auth_headers(token),
    )

    assert release_response.status_code == 200


def test_counter_assignment_history(client, db):
    terminal, flight, token = create_counter_test_data(db)

    payload = counter_payload()
    payload["terminal_id"] = terminal.id

    counter_response = client.post(
        "/api/v1/counters",
        json=payload,
        headers=auth_headers(token),
    )
    assert counter_response.status_code == 201

    assignment_response = client.post(
        "/api/v1/counters/assignments",
        json={
            "counter_id": counter_response.json()["id"],
            "flight_id": flight.id,
        },
        headers=auth_headers(token),
    )
    assert assignment_response.status_code == 201

    response = client.get(
        "/api/v1/counters/assignments/history",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert str(assignment_response.json()["id"]) in response.text


def test_get_nonexistent_counter(client, db):
    terminal, flight, token = create_counter_test_data(db)

    response = client.get(
        "/api/v1/counters/99999",
        headers=auth_headers(token),
    )

    assert response.status_code == 404