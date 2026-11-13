from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import hash_password, create_access_token
from app.models.user import User
from app.models.airport import Airport
from app.models.terminal import Terminal
from app.models.flight import Flight
from app.utils.enums import UserRole


def create_passenger_test_data(db):
    user = User(
        full_name="Passenger Test Admin",
        email="passenger_admin_test@example.com",
        hashed_password=hash_password("TestPassword123"),
        role=UserRole.AIRPORT_OPERATIONS_MANAGER,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    origin = Airport(
        iata_code="PGA",
        name="Passenger Origin Airport",
        city="Chennai",
        country="India",
        timezone="Asia/Kolkata",
    )

    destination = Airport(
        iata_code="PGB",
        name="Passenger Destination Airport",
        city="Bengaluru",
        country="India",
        timezone="Asia/Kolkata",
    )

    db.add_all([origin, destination])
    db.commit()
    db.refresh(origin)
    db.refresh(destination)

    terminal = Terminal(
        airport_id=origin.id,
        code="PGT",
        name="Passenger Test Terminal",
        capacity=100,
    )
    db.add(terminal)
    db.commit()
    db.refresh(terminal)

    flight = Flight(
        flight_number="PG100",
        airline="Passenger Test Airlines",
        origin_airport_id=origin.id,
        destination_airport_id=destination.id,
        terminal_id=terminal.id,
        scheduled_departure=datetime.now(timezone.utc) + timedelta(days=1),
        scheduled_arrival=datetime.now(timezone.utc) + timedelta(days=1, hours=2),
    )
    db.add(flight)
    db.commit()
    db.refresh(flight)

    token = create_access_token(str(user.id))

    return flight, token


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def passenger_payload():
    return {
        "first_name": "Arun",
        "last_name": "Kumar",
        "email": "arun.passenger@example.com",
        "phone": "9876543210",
        "identification_type": "passport",
        "identification_reference": "PASSENGER-TEST-001",
    }


def test_create_passenger(client, db):
    flight, token = create_passenger_test_data(db)

    response = client.post(
        "/api/v1/passengers",
        json=passenger_payload(),
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    assert response.json()["first_name"] == "Arun"
    assert response.json()["status"] == "active"


def test_duplicate_passenger_email(client, db):
    flight, token = create_passenger_test_data(db)
    payload = passenger_payload()

    first = client.post(
        "/api/v1/passengers",
        json=payload,
        headers=auth_headers(token),
    )
    assert first.status_code == 201

    payload["identification_reference"] = "PASSENGER-TEST-002"

    duplicate = client.post(
        "/api/v1/passengers",
        json=payload,
        headers=auth_headers(token),
    )

    assert duplicate.status_code == 409


def test_list_passengers(client, db):
    flight, token = create_passenger_test_data(db)

    create = client.post(
        "/api/v1/passengers",
        json=passenger_payload(),
        headers=auth_headers(token),
    )
    assert create.status_code == 201

    response = client.get(
        "/api/v1/passengers",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_search_passengers(client, db):
    flight, token = create_passenger_test_data(db)

    client.post(
        "/api/v1/passengers",
        json=passenger_payload(),
        headers=auth_headers(token),
    )

    response = client.get(
        "/api/v1/passengers?search=Arun",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_update_passenger(client, db):
    flight, token = create_passenger_test_data(db)

    create = client.post(
        "/api/v1/passengers",
        json=passenger_payload(),
        headers=auth_headers(token),
    )
    passenger_id = create.json()["id"]

    response = client.patch(
        f"/api/v1/passengers/{passenger_id}",
        json={"first_name": "Updated"},
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["first_name"] == "Updated"


def test_assign_passenger_to_flight(client, db):
    flight, token = create_passenger_test_data(db)

    create = client.post(
        "/api/v1/passengers",
        json=passenger_payload(),
        headers=auth_headers(token),
    )
    passenger_id = create.json()["id"]

    response = client.post(
        "/api/v1/passengers/flights/assign",
        json={
            "passenger_id": passenger_id,
            "flight_id": flight.id,
            "booking_reference": "PG-BOOK-001",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    assert response.json()["status"] == "booked"


def test_passenger_flight_history(client, db):
    flight, token = create_passenger_test_data(db)

    create = client.post(
        "/api/v1/passengers",
        json=passenger_payload(),
        headers=auth_headers(token),
    )
    passenger_id = create.json()["id"]

    assignment = client.post(
        "/api/v1/passengers/flights/assign",
        json={
            "passenger_id": passenger_id,
            "flight_id": flight.id,
            "booking_reference": "PG-BOOK-002",
        },
        headers=auth_headers(token),
    )
    assert assignment.status_code == 201

    response = client.get(
        f"/api/v1/passengers/{passenger_id}/history",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_delete_passenger(client, db):
    flight, token = create_passenger_test_data(db)

    create = client.post(
        "/api/v1/passengers",
        json=passenger_payload(),
        headers=auth_headers(token),
    )
    passenger_id = create.json()["id"]

    response = client.delete(
        f"/api/v1/passengers/{passenger_id}",
        headers=auth_headers(token),
    )

    assert response.status_code == 204


def test_get_nonexistent_passenger(client, db):
    flight, token = create_passenger_test_data(db)

    response = client.get(
        "/api/v1/passengers/99999",
        headers=auth_headers(token),
    )

    assert response.status_code == 404