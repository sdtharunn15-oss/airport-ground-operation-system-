from datetime import datetime, timedelta, timezone

from app.core.security import hash_password, create_access_token
from app.models.user import User
from app.models.airport import Airport
from app.models.terminal import Terminal
from app.models.flight import Flight
from app.models.passenger import Passenger
from app.models.counter import Counter
from app.models.counter_assignment import CounterAssignment
from app.utils.enums import (
    UserRole,
    CounterStatus,
    AssignmentStatus,
)


def create_checkin_test_data(db):
    user = User(
        full_name="Check-in Test Admin",
        email="checkin_admin_test@example.com",
        hashed_password=hash_password("TestPassword123"),
        role=UserRole.AIRPORT_OPERATIONS_MANAGER,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    origin = Airport(
        iata_code="CGA",
        name="Check-in Origin Airport",
        city="Chennai",
        country="India",
        timezone="Asia/Kolkata",
    )

    destination = Airport(
        iata_code="CGB",
        name="Check-in Destination Airport",
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
        code="CGT",
        name="Check-in Test Terminal",
        capacity=100,
    )
    db.add(terminal)
    db.commit()
    db.refresh(terminal)

    flight = Flight(
        flight_number="CG100",
        airline="Check-in Test Airlines",
        origin_airport_id=origin.id,
        destination_airport_id=destination.id,
        terminal_id=terminal.id,
        scheduled_departure=datetime.now(timezone.utc) + timedelta(days=1),
        scheduled_arrival=datetime.now(timezone.utc) + timedelta(days=1, hours=2),
    )
    db.add(flight)
    db.commit()
    db.refresh(flight)

    counter = Counter(
        terminal_id=terminal.id,
        counter_number="CG01",
        counter_name="Check-in Counter 1",
        status=CounterStatus.OCCUPIED,
    )
    db.add(counter)
    db.commit()
    db.refresh(counter)

    assignment = CounterAssignment(
        counter_id=counter.id,
        flight_id=flight.id,
        status=AssignmentStatus.ACTIVE,
    )
    db.add(assignment)
    db.commit()

    token = create_access_token(str(user.id))

    return flight, counter, token


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def create_test_passenger(client, token, flight_id, suffix="001"):
    passenger_response = client.post(
        "/api/v1/passengers",
        json={
            "first_name": "Arun",
            "last_name": "Kumar",
            "email": f"checkin_passenger_{suffix}@example.com",
            "phone": "9876543210",
            "identification_type": "passport",
            "identification_reference": f"CHECKIN-PASS-{suffix}",
        },
        headers=auth_headers(token),
    )

    assert passenger_response.status_code == 201

    passenger_id = passenger_response.json()["id"]

    assignment_response = client.post(
        "/api/v1/passengers/flights/assign",
        json={
            "passenger_id": passenger_id,
            "flight_id": flight_id,
            "booking_reference": f"CHECKIN-BOOK-{suffix}",
        },
        headers=auth_headers(token),
    )

    assert assignment_response.status_code == 201

    return passenger_id


def checkin_payload(passenger_id, flight_id, counter_id, seat="12A"):
    return {
        "passenger_id": passenger_id,
        "flight_id": flight_id,
        "counter_id": counter_id,
        "seat_number": seat,
    }


def test_create_checkin(client, db):
    flight, counter, token = create_checkin_test_data(db)

    passenger_id = create_test_passenger(
        client, token, flight.id
    )

    response = client.post(
        "/api/v1/checkins",
        json=checkin_payload(
            passenger_id,
            flight.id,
            counter.id,
        ),
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    assert response.json()["seat_number"] == "12A"
    assert response.json()["checkin_status"] == "checked_in"
    assert response.json()["boarding_pass_status"] == "active"
    assert response.json()["boarding_pass_reference"].startswith("BP-")
    assert response.json()["checked_in_at"] is not None


def test_duplicate_checkin(client, db):
    flight, counter, token = create_checkin_test_data(db)

    passenger_id = create_test_passenger(
        client, token, flight.id
    )

    payload = checkin_payload(
        passenger_id,
        flight.id,
        counter.id,
    )

    first = client.post(
        "/api/v1/checkins",
        json=payload,
        headers=auth_headers(token),
    )
    assert first.status_code == 201

    duplicate = client.post(
        "/api/v1/checkins",
        json=payload,
        headers=auth_headers(token),
    )

    assert duplicate.status_code == 409


def test_duplicate_seat_assignment(client, db):
    flight, counter, token = create_checkin_test_data(db)

    first_passenger = create_test_passenger(
        client, token, flight.id, "002"
    )

    second_passenger = create_test_passenger(
        client, token, flight.id, "003"
    )

    first = client.post(
        "/api/v1/checkins",
        json=checkin_payload(
            first_passenger,
            flight.id,
            counter.id,
            "15A",
        ),
        headers=auth_headers(token),
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/checkins",
        json=checkin_payload(
            second_passenger,
            flight.id,
            counter.id,
            "15A",
        ),
        headers=auth_headers(token),
    )

    assert second.status_code == 409


def test_list_checkins(client, db):
    flight, counter, token = create_checkin_test_data(db)

    passenger_id = create_test_passenger(
        client, token, flight.id, "004"
    )

    client.post(
        "/api/v1/checkins",
        json=checkin_payload(
            passenger_id,
            flight.id,
            counter.id,
        ),
        headers=auth_headers(token),
    )

    response = client.get(
        "/api/v1/checkins",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_get_checkin_by_id(client, db):
    flight, counter, token = create_checkin_test_data(db)

    passenger_id = create_test_passenger(
        client, token, flight.id, "005"
    )

    create = client.post(
        "/api/v1/checkins",
        json=checkin_payload(
            passenger_id,
            flight.id,
            counter.id,
        ),
        headers=auth_headers(token),
    )

    checkin_id = create.json()["id"]

    response = client.get(
        f"/api/v1/checkins/{checkin_id}",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["id"] == checkin_id


def test_cancel_checkin(client, db):
    flight, counter, token = create_checkin_test_data(db)

    passenger_id = create_test_passenger(
        client, token, flight.id, "006"
    )

    create = client.post(
        "/api/v1/checkins",
        json=checkin_payload(
            passenger_id,
            flight.id,
            counter.id,
        ),
        headers=auth_headers(token),
    )

    checkin_id = create.json()["id"]

    response = client.patch(
        f"/api/v1/checkins/{checkin_id}/cancel",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["checkin_status"] == "cancelled"
    assert response.json()["boarding_pass_status"] == "cancelled"


def test_get_nonexistent_checkin(client, db):
    flight, counter, token = create_checkin_test_data(db)

    response = client.get(
        "/api/v1/checkins/99999",
        headers=auth_headers(token),
    )

    assert response.status_code == 404