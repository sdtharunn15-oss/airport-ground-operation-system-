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
from app.models.flight import Flight
from app.core.security import create_access_token, hash_password
from app.utils.enums import UserRole

client = TestClient(app)


def unique_iata(db):
    while True:
        code = "".join(secrets.choice(string.ascii_uppercase) for _ in range(3))
        if not db.query(Airport).filter(Airport.iata_code == code).first():
            return code


@pytest.fixture
def setup_delay_data():
    db = SessionLocal()
    suffix = secrets.token_hex(8)

    try:
        user = User(
            full_name="Delay Test Officer",
            email=f"delay-officer-{suffix}@example.com",
            hashed_password=hash_password("TestPassword123!"),
            role=UserRole.FLIGHT_OPERATIONS_OFFICER,
            is_active=True,
            is_verified=True,
        )

        airport_one = Airport(
            iata_code=unique_iata(db),
            name="Delay Origin Airport",
            city="Chennai",
            country="India",
            timezone="Asia/Kolkata",
        )
        airport_two = Airport(
            iata_code=unique_iata(db),
            name="Delay Destination Airport",
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
            code=f"D{suffix[:6].upper()}",
            name="Delay Test Terminal",
            capacity=100,
        )
        db.add(terminal)
        db.commit()
        db.refresh(terminal)

        departure = datetime.now(timezone.utc) + timedelta(days=1)

        flight = Flight(
            flight_number=f"DL{suffix[:6].upper()}",
            airline="Test Airways",
            origin_airport_id=airport_one.id,
            destination_airport_id=airport_two.id,
            terminal_id=terminal.id,
            scheduled_departure=departure,
            scheduled_arrival=departure + timedelta(hours=2),
            aircraft_type="Airbus A320",
        )
        db.add(flight)
        db.commit()
        db.refresh(flight)

        token = create_access_token(str(user.id))

        yield {
            "token": token,
            "flight_id": flight.id,
            "departure": departure,
        }

    finally:
        db.close()


def headers(data):
    return {"Authorization": f"Bearer {data['token']}"}


def delay_payload(data):
    expected = data["departure"]
    updated = expected + timedelta(minutes=90)

    return {
        "flight_id": data["flight_id"],
        "delay_category": "weather",
        "delay_reason": "Heavy rainfall affecting airport operations",
        "responsible_department": "Flight Operations",
        "expected_departure": expected.isoformat(),
        "updated_departure": updated.isoformat(),
        "remarks": "Weather-related delay",
    }


def test_create_flight_delay(setup_delay_data):
    data = setup_delay_data

    response = client.post(
        "/api/v1/flight-delays/",
        json=delay_payload(data),
        headers=headers(data),
    )

    assert response.status_code == 201, response.text
    assert response.json()["delay_duration_minutes"] == 90
    assert response.json()["delay_category"] == "weather"


def test_list_flight_delays(setup_delay_data):
    data = setup_delay_data

    created = client.post(
        "/api/v1/flight-delays/",
        json=delay_payload(data),
        headers=headers(data),
    )
    assert created.status_code == 201, created.text

    response = client.get(
        "/api/v1/flight-delays/",
        params={"flight_id": data["flight_id"]},
        headers=headers(data),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_flight_delay_history(setup_delay_data):
    data = setup_delay_data

    created = client.post(
        "/api/v1/flight-delays/",
        json=delay_payload(data),
        headers=headers(data),
    )
    assert created.status_code == 201, created.text

    response = client.get(
        f"/api/v1/flight-delays/flights/{data['flight_id']}/history",
        headers=headers(data),
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_invalid_flight_delay_duration(setup_delay_data):
    data = setup_delay_data
    payload = delay_payload(data)
    payload["updated_departure"] = (
        data["departure"] - timedelta(minutes=30)
    ).isoformat()

    response = client.post(
        "/api/v1/flight-delays/",
        json=payload,
        headers=headers(data),
    )

    assert response.status_code == 400
