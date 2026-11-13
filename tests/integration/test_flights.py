
from datetime import datetime, timedelta, timezone
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


def generate_unique_iata(db, excluded=None):
    excluded = excluded or set()

    while True:
        code = "".join(
            secrets.choice(string.ascii_uppercase)
            for _ in range(3)
        )

        if code in excluded:
            continue

        exists = db.query(Airport).filter(
            Airport.iata_code == code
        ).first()

        if not exists:
            return code


@pytest.fixture
def setup_flight_data():
    db = SessionLocal()
    suffix = secrets.token_hex(8)

    try:
        airport_code_one = generate_unique_iata(db)
        airport_code_two = generate_unique_iata(
            db,
            excluded={airport_code_one},
        )

        user = User(
            full_name="Flight Test Manager",
            email=f"flight-manager-{suffix}@example.com",
            hashed_password=hash_password("TestPassword123!"),
            role=UserRole.FLIGHT_OPERATIONS_OFFICER,
            is_active=True,
            is_verified=True,
        )

        airport_one = Airport(
            iata_code=airport_code_one,
            name="Origin Test Airport",
            city="Chennai",
            country="India",
            timezone="Asia/Kolkata",
        )

        airport_two = Airport(
            iata_code=airport_code_two,
            name="Destination Test Airport",
            city="Mumbai",
            country="India",
            timezone="Asia/Kolkata",
        )

        db.add_all([user, airport_one, airport_two])
        db.commit()

        db.refresh(user)
        db.refresh(airport_one)
        db.refresh(airport_two)

        terminal = Terminal(
            airport_id=airport_one.id,
            code=f"T{suffix[:6].upper()}",
            name="Test Terminal",
            capacity=100,
        )

        db.add(terminal)
        db.commit()
        db.refresh(terminal)

        token = create_access_token(str(user.id))

        yield {
            "token": token,
            "airport_one": airport_one.id,
            "airport_two": airport_two.id,
            "terminal": terminal.id,
        }

    finally:
        db.close()


def flight_payload(data):
    departure = datetime.now(timezone.utc) + timedelta(days=1)

    return {
        "flight_number": "AI101",
        "airline": "Air India",
        "origin_airport_id": data["airport_one"],
        "destination_airport_id": data["airport_two"],
        "terminal_id": data["terminal"],
        "scheduled_departure": departure.isoformat(),
        "scheduled_arrival": (
            departure + timedelta(hours=2)
        ).isoformat(),
        "status": "scheduled",
        "aircraft_type": "Airbus A320",
    }


def headers(data):
    return {"Authorization": f"Bearer {data['token']}"}


def test_create_flight(setup_flight_data):
    data = setup_flight_data
    response = client.post(
        "/api/v1/flights",
        json=flight_payload(data),
        headers=headers(data),
    )
    assert response.status_code == 201
    assert response.json()["flight_number"] == "AI101"


def test_duplicate_flight(setup_flight_data):
    data = setup_flight_data
    payload = flight_payload(data)

    first = client.post(
        "/api/v1/flights",
        json=payload,
        headers=headers(data),
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/flights",
        json=payload,
        headers=headers(data),
    )
    assert second.status_code == 409


def test_invalid_same_airport(setup_flight_data):
    data = setup_flight_data
    payload = flight_payload(data)
    payload["destination_airport_id"] = data["airport_one"]

    response = client.post(
        "/api/v1/flights",
        json=payload,
        headers=headers(data),
    )
    assert response.status_code == 422


def test_invalid_arrival_time(setup_flight_data):
    data = setup_flight_data
    payload = flight_payload(data)
    payload["scheduled_arrival"] = payload["scheduled_departure"]

    response = client.post(
        "/api/v1/flights",
        json=payload,
        headers=headers(data),
    )
    assert response.status_code == 422


def test_create_flight_invalid_airport(setup_flight_data):
    data = setup_flight_data
    payload = flight_payload(data)
    payload["origin_airport_id"] = 999999

    response = client.post(
        "/api/v1/flights",
        json=payload,
        headers=headers(data),
    )
    assert response.status_code == 404


def test_create_flight_invalid_terminal(setup_flight_data):
    data = setup_flight_data
    payload = flight_payload(data)
    payload["terminal_id"] = 999999

    response = client.post(
        "/api/v1/flights",
        json=payload,
        headers=headers(data),
    )
    assert response.status_code == 404


def test_list_flights(setup_flight_data):
    data = setup_flight_data

    client.post(
        "/api/v1/flights",
        json=flight_payload(data),
        headers=headers(data),
    )

    response = client.get(
        "/api/v1/flights",
        headers=headers(data),
    )

    assert response.status_code == 200
    assert response.json()["total"] >= 1


def test_get_flight(setup_flight_data):
    data = setup_flight_data

    created = client.post(
        "/api/v1/flights",
        json=flight_payload(data),
        headers=headers(data),
    )
    flight_id = created.json()["id"]

    response = client.get(
        f"/api/v1/flights/{flight_id}",
        headers=headers(data),
    )

    assert response.status_code == 200
    assert response.json()["id"] == flight_id


def test_update_flight(setup_flight_data):
    data = setup_flight_data

    created = client.post(
        "/api/v1/flights",
        json=flight_payload(data),
        headers=headers(data),
    )
    flight_id = created.json()["id"]

    response = client.patch(
        f"/api/v1/flights/{flight_id}",
        json={"status": "boarding"},
        headers=headers(data),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "boarding"


def test_delete_flight_requires_admin(setup_flight_data):
    data = setup_flight_data

    created = client.post(
        "/api/v1/flights",
        json=flight_payload(data),
        headers=headers(data),
    )
    flight_id = created.json()["id"]

    response = client.delete(
        f"/api/v1/flights/{flight_id}",
        headers=headers(data),
    )

    assert response.status_code == 403


def test_unauthenticated_flight_list():
    response = client.get("/api/v1/flights")
    assert response.status_code == 401
