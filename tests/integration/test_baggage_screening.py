from datetime import datetime, timedelta, timezone

from app.core.security import hash_password, create_access_token
from app.models.user import User
from app.models.airport import Airport
from app.models.terminal import Terminal
from app.models.flight import Flight
from app.utils.enums import UserRole


def create_screening_test_data(db):
    user = User(
        full_name="Screening Test Admin",
        email="screening_admin_test@example.com",
        hashed_password=hash_password("TestPassword123"),
        role=UserRole.AIRPORT_OPERATIONS_MANAGER,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    origin = Airport(
        iata_code="SGA",
        name="Screening Origin Airport",
        city="Chennai",
        country="India",
        timezone="Asia/Kolkata",
    )

    destination = Airport(
        iata_code="SGB",
        name="Screening Destination Airport",
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
        code="SGT",
        name="Screening Test Terminal",
        capacity=100,
    )
    db.add(terminal)
    db.commit()
    db.refresh(terminal)

    flight = Flight(
        flight_number="SG100",
        airline="Screening Test Airlines",
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


def create_screening_baggage(client, token, flight_id):
    suffix = "SCREEN001"

    passenger_response = client.post(
        "/api/v1/passengers",
        json={
            "first_name": "Arun",
            "last_name": "Kumar",
            "email": f"screening_passenger_{suffix}@example.com",
            "phone": "9876543210",
            "identification_type": "passport",
            "identification_reference": f"SCREENING-PASS-{suffix}",
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
            "booking_reference": f"SCREENING-BOOK-{suffix}",
        },
        headers=auth_headers(token),
    )

    assert assignment_response.status_code == 201

    baggage_response = client.post(
        "/api/v1/baggage",
        json={
            "passenger_id": passenger_id,
            "flight_id": flight_id,
            "baggage_type": "checked",
            "weight_kg": 20.5,
            "description": "Screening test suitcase",
        },
        headers=auth_headers(token),
    )

    assert baggage_response.status_code == 201

    return baggage_response.json()["id"]


def add_screening(client, token, baggage_id, result="cleared"):
    return client.post(
        f"/api/v1/baggage-screening/{baggage_id}",
        json={
            "result": result,
            "screening_location": "Security Screening Area",
            "remarks": "Screening integration test",
        },
        headers=auth_headers(token),
    )


def test_create_baggage_screening(client, db):
    flight, token = create_screening_test_data(db)
    baggage_id = create_screening_baggage(client, token, flight.id)

    response = add_screening(client, token, baggage_id, "cleared")

    assert response.status_code == 201
    assert response.json()["baggage_id"] == baggage_id
    assert response.json()["result"] == "cleared"
    assert response.json()["screening_location"] == "Security Screening Area"


def test_create_flagged_baggage_screening(client, db):
    flight, token = create_screening_test_data(db)
    baggage_id = create_screening_baggage(client, token, flight.id)

    response = add_screening(client, token, baggage_id, "flagged")

    assert response.status_code == 201
    assert response.json()["result"] == "flagged"


def test_reject_duplicate_completed_screening(client, db):
    flight, token = create_screening_test_data(db)
    baggage_id = create_screening_baggage(client, token, flight.id)

    first = add_screening(client, token, baggage_id, "cleared")
    assert first.status_code == 201

    second = add_screening(client, token, baggage_id, "cleared")

    assert second.status_code == 409


def test_allow_rescreening_after_flagged_result(client, db):
    flight, token = create_screening_test_data(db)
    baggage_id = create_screening_baggage(client, token, flight.id)

    first = add_screening(client, token, baggage_id, "flagged")
    assert first.status_code == 201

    second = add_screening(client, token, baggage_id, "cleared")

    assert second.status_code == 201
    assert second.json()["result"] == "cleared"


def test_get_baggage_screening_history(client, db):
    flight, token = create_screening_test_data(db)
    baggage_id = create_screening_baggage(client, token, flight.id)

    add_screening(client, token, baggage_id, "flagged")
    add_screening(client, token, baggage_id, "cleared")

    response = client.get(
        f"/api/v1/baggage-screening/{baggage_id}/history",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert len(response.json()["items"]) == 2


def test_get_screening_record(client, db):
    flight, token = create_screening_test_data(db)
    baggage_id = create_screening_baggage(client, token, flight.id)

    create = add_screening(client, token, baggage_id, "cleared")
    assert create.status_code == 201

    screening_id = create.json()["id"]

    response = client.get(
        f"/api/v1/baggage-screening/records/{screening_id}",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["id"] == screening_id


def test_reject_screening_for_nonexistent_baggage(client, db):
    flight, token = create_screening_test_data(db)

    response = add_screening(client, token, 99999, "cleared")

    assert response.status_code == 404


def test_reject_screening_for_cancelled_baggage(client, db):
    flight, token = create_screening_test_data(db)
    baggage_id = create_screening_baggage(client, token, flight.id)

    cancel = client.patch(
        f"/api/v1/baggage/{baggage_id}/cancel",
        headers=auth_headers(token),
    )
    assert cancel.status_code == 200

    response = add_screening(client, token, baggage_id, "cleared")

    assert response.status_code == 400
