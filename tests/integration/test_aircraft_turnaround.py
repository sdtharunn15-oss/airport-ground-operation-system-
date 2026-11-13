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


def generate_unique_iata(db):
    while True:
        code = "".join(
            secrets.choice(string.ascii_uppercase)
            for _ in range(3)
        )
        if not db.query(Airport).filter(Airport.iata_code == code).first():
            return code


@pytest.fixture
def setup_turnaround_data():
    db = SessionLocal()
    suffix = secrets.token_hex(8)

    try:
        user = User(
            full_name="Turnaround Test Manager",
            email=f"turnaround-manager-{suffix}@example.com",
            hashed_password=hash_password("TestPassword123!"),
            role=UserRole.AIRPORT_OPERATIONS_MANAGER,
            is_active=True,
            is_verified=True,
        )

        airport_one = Airport(
            iata_code=generate_unique_iata(db),
            name="Turnaround Origin Airport",
            city="Chennai",
            country="India",
            timezone="Asia/Kolkata",
        )

        airport_two = Airport(
            iata_code=generate_unique_iata(db),
            name="Turnaround Destination Airport",
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
            name="Turnaround Test Terminal",
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
            "suffix": suffix,
        }

    finally:
        db.close()


def headers(data):
    return {"Authorization": f"Bearer {data['token']}"}


def create_test_flight(data):
    departure = datetime.now(timezone.utc) + timedelta(days=1)

    response = client.post(
        "/api/v1/flights",
        json={
            "flight_number": f"TA{data['suffix'][:6].upper()}",
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
        },
        headers=headers(data),
    )

    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_create_aircraft_turnaround(setup_turnaround_data):
    data = setup_turnaround_data
    flight_id = create_test_flight(data)

    start = datetime.now(timezone.utc) + timedelta(hours=3)
    end = start + timedelta(hours=2)

    response = client.post(
        "/api/v1/aircraft-turnarounds",
        json={
            "flight_id": flight_id,
            "service_type": "cleaning",
            "scheduled_start": start.isoformat(),
            "scheduled_end": end.isoformat(),
            "remarks": "Prepare aircraft cabin",
        },
        headers=headers(data),
    )

    assert response.status_code == 201, response.text
    result = response.json()
    assert result["flight_id"] == flight_id
    assert result["service_type"] == "cleaning"
    assert result["status"] == "scheduled"

def test_list_aircraft_turnarounds(setup_turnaround_data):
    data = setup_turnaround_data
    flight_id = create_test_flight(data)

    start = datetime.now(timezone.utc) + timedelta(hours=3)

    client.post(
        "/api/v1/aircraft-turnarounds",
        json={
            "flight_id": flight_id,
            "service_type": "refueling",
            "scheduled_start": start.isoformat(),
            "scheduled_end": (start + timedelta(hours=1)).isoformat(),
        },
        headers=headers(data),
    )

    response = client.get(
        f"/api/v1/aircraft-turnarounds?flight_id={flight_id}",
        headers=headers(data),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["service_type"] == "refueling"


def test_get_aircraft_turnaround_by_id(setup_turnaround_data):
    data = setup_turnaround_data
    flight_id = create_test_flight(data)

    start = datetime.now(timezone.utc) + timedelta(hours=3)

    create_response = client.post(
        "/api/v1/aircraft-turnarounds",
        json={
            "flight_id": flight_id,
            "service_type": "catering",
            "scheduled_start": start.isoformat(),
            "scheduled_end": (start + timedelta(hours=1)).isoformat(),
        },
        headers=headers(data),
    )

    assert create_response.status_code == 201, create_response.text
    turnaround_id = create_response.json()["id"]

    response = client.get(
        f"/api/v1/aircraft-turnarounds/{turnaround_id}",
        headers=headers(data),
    )

    assert response.status_code == 200
    assert response.json()["id"] == turnaround_id
    assert response.json()["service_type"] == "catering"


def test_update_aircraft_turnaround(setup_turnaround_data):
    data = setup_turnaround_data
    flight_id = create_test_flight(data)

    start = datetime.now(timezone.utc) + timedelta(hours=3)

    create_response = client.post(
        "/api/v1/aircraft-turnarounds",
        json={
            "flight_id": flight_id,
            "service_type": "cleaning",
            "scheduled_start": start.isoformat(),
            "scheduled_end": (start + timedelta(hours=2)).isoformat(),
        },
        headers=headers(data),
    )

    assert create_response.status_code == 201, create_response.text
    turnaround_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/aircraft-turnarounds/{turnaround_id}",
        json={
            "service_type": "catering",
            "remarks": "Updated catering service",
        },
        headers=headers(data),
    )

    assert response.status_code == 200, response.text
    assert response.json()["service_type"] == "catering"
    assert response.json()["remarks"] == "Updated catering service"


def test_aircraft_turnaround_lifecycle(setup_turnaround_data):
    data = setup_turnaround_data
    flight_id = create_test_flight(data)

    staff_response = client.post(
        "/api/v1/ground-staff",
        json={
            "employee_code": f"TRL{data['suffix'][:6].upper()}",
            "full_name": "Turnaround Lifecycle Staff",
            "email": f"turnaround-lifecycle-{data['suffix']}@example.com",
            "phone": "9876543210",
            "role": "baggage_handling_staff",
            "airport_id": data["airport_one"],
            "terminal_id": data["terminal"],
        },
        headers=headers(data),
    )

    assert staff_response.status_code == 201, staff_response.text
    staff_id = staff_response.json()["id"]

    start = datetime.now(timezone.utc) + timedelta(hours=3)

    create_response = client.post(
        "/api/v1/aircraft-turnarounds",
        json={
            "flight_id": flight_id,
            "service_type": "cleaning",
            "assigned_staff_id": staff_id,
            "scheduled_start": start.isoformat(),
            "scheduled_end": (start + timedelta(hours=2)).isoformat(),
        },
        headers=headers(data),
    )

    assert create_response.status_code == 201, create_response.text
    turnaround_id = create_response.json()["id"]

    start_response = client.patch(
        f"/api/v1/aircraft-turnarounds/{turnaround_id}",
        json={"status": "in_progress"},
        headers=headers(data),
    )

    assert start_response.status_code == 200, start_response.text
    assert start_response.json()["status"] == "in_progress"
    assert start_response.json()["actual_start"] is not None

    complete_response = client.patch(
        f"/api/v1/aircraft-turnarounds/{turnaround_id}",
        json={"status": "completed"},
        headers=headers(data),
    )

    assert complete_response.status_code == 200, complete_response.text
    assert complete_response.json()["status"] == "completed"
    assert complete_response.json()["actual_end"] is not None

    updated_staff = client.get(
        f"/api/v1/ground-staff/{staff_id}",
        headers=headers(data),
    )

    assert updated_staff.status_code == 200
    assert updated_staff.json()["availability"] == "available"


def test_delete_aircraft_turnaround(setup_turnaround_data):
    data = setup_turnaround_data
    flight_id = create_test_flight(data)

    start = datetime.now(timezone.utc) + timedelta(hours=3)

    create_response = client.post(
        "/api/v1/aircraft-turnarounds",
        json={
            "flight_id": flight_id,
            "service_type": "waste_service",
            "scheduled_start": start.isoformat(),
            "scheduled_end": (start + timedelta(hours=1)).isoformat(),
        },
        headers=headers(data),
    )

    assert create_response.status_code == 201, create_response.text
    turnaround_id = create_response.json()["id"]

    delete_response = client.delete(
        f"/api/v1/aircraft-turnarounds/{turnaround_id}",
        headers=headers(data),
    )

    assert delete_response.status_code == 200

    get_response = client.get(
        f"/api/v1/aircraft-turnarounds/{turnaround_id}",
        headers=headers(data),
    )

    assert get_response.status_code == 404
