
from datetime import datetime, timedelta, timezone

from app.core.security import hash_password, create_access_token
from app.models.user import User
from app.models.airport import Airport
from app.models.terminal import Terminal
from app.models.flight import Flight
from app.utils.enums import UserRole


def create_tracking_test_data(db):
    user = User(
        full_name="Tracking Test Admin",
        email="tracking_admin_test@example.com",
        hashed_password=hash_password("TestPassword123"),
        role=UserRole.AIRPORT_OPERATIONS_MANAGER,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    origin = Airport(
        iata_code="TGA",
        name="Tracking Origin Airport",
        city="Chennai",
        country="India",
        timezone="Asia/Kolkata",
    )

    destination = Airport(
        iata_code="TGB",
        name="Tracking Destination Airport",
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
        code="TGT",
        name="Tracking Test Terminal",
        capacity=100,
    )
    db.add(terminal)
    db.commit()
    db.refresh(terminal)

    flight = Flight(
        flight_number="TG100",
        airline="Tracking Test Airlines",
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


def create_tracking_baggage(client, token, flight_id):
    suffix = "TRACK001"

    passenger_response = client.post(
        "/api/v1/passengers",
        json={
            "first_name": "Arun",
            "last_name": "Kumar",
            "email": f"tracking_passenger_{suffix}@example.com",
            "phone": "9876543210",
            "identification_type": "passport",
            "identification_reference": f"TRACKING-PASS-{suffix}",
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
            "booking_reference": f"TRACKING-BOOK-{suffix}",
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
            "description": "Tracking test suitcase",
        },
        headers=auth_headers(token),
    )

    assert baggage_response.status_code == 201

    return baggage_response.json()["id"]


def add_tracking(client, token, baggage_id, tracking_status, location):
    return client.post(
        f"/api/v1/baggage-tracking/{baggage_id}",
        json={
            "status": tracking_status,
            "location": location,
            "remarks": "Tracking integration test",
        },
        headers=auth_headers(token),
    )


def test_create_initial_baggage_tracking(client, db):
    flight, token = create_tracking_test_data(db)
    baggage_id = create_tracking_baggage(client, token, flight.id)

    response = add_tracking(
        client, token, baggage_id,
        "registered", "Check-in Counter",
    )

    assert response.status_code == 201
    assert response.json()["baggage_id"] == baggage_id
    assert response.json()["status"] == "registered"
    assert response.json()["location"] == "Check-in Counter"


def test_update_baggage_tracking_status(client, db):
    flight, token = create_tracking_test_data(db)
    baggage_id = create_tracking_baggage(client, token, flight.id)

    initial = add_tracking(
        client, token, baggage_id,
        "registered", "Check-in Counter",
    )
    assert initial.status_code == 201

    response = add_tracking(
        client, token, baggage_id,
        "received", "Baggage Handling Area",
    )

    assert response.status_code == 201
    assert response.json()["status"] == "received"


def test_reject_invalid_tracking_transition(client, db):
    flight, token = create_tracking_test_data(db)
    baggage_id = create_tracking_baggage(client, token, flight.id)

    add_tracking(
        client, token, baggage_id,
        "registered", "Check-in Counter",
    )

    response = add_tracking(
        client, token, baggage_id,
        "loaded", "Aircraft",
    )

    assert response.status_code == 400


def test_get_baggage_tracking_history(client, db):
    flight, token = create_tracking_test_data(db)
    baggage_id = create_tracking_baggage(client, token, flight.id)

    add_tracking(
        client, token, baggage_id,
        "registered", "Check-in Counter",
    )

    add_tracking(
        client, token, baggage_id,
        "received", "Baggage Handling Area",
    )

    response = client.get(
        f"/api/v1/baggage-tracking/{baggage_id}/history",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["items"][0]["status"] == "registered"
    assert response.json()["items"][1]["status"] == "received"


def test_get_current_baggage_tracking(client, db):
    flight, token = create_tracking_test_data(db)
    baggage_id = create_tracking_baggage(client, token, flight.id)

    add_tracking(
        client, token, baggage_id,
        "registered", "Check-in Counter",
    )

    add_tracking(
        client, token, baggage_id,
        "received", "Baggage Handling Area",
    )

    response = client.get(
        f"/api/v1/baggage-tracking/{baggage_id}/current",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["baggage_id"] == baggage_id
    assert response.json()["current_status"] == "received"
    assert response.json()["current_location"] == "Baggage Handling Area"


def test_get_tracking_record(client, db):
    flight, token = create_tracking_test_data(db)
    baggage_id = create_tracking_baggage(client, token, flight.id)

    create = add_tracking(
        client, token, baggage_id,
        "registered", "Check-in Counter",
    )

    assert create.status_code == 201
    tracking_id = create.json()["id"]

    response = client.get(
        f"/api/v1/baggage-tracking/records/{tracking_id}",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["id"] == tracking_id


def test_reject_tracking_for_nonexistent_baggage(client, db):
    flight, token = create_tracking_test_data(db)

    response = add_tracking(
        client, token, 99999,
        "registered", "Check-in Counter",
    )

    assert response.status_code == 404


def test_reject_tracking_for_cancelled_baggage(client, db):
    flight, token = create_tracking_test_data(db)
    baggage_id = create_tracking_baggage(client, token, flight.id)

    cancel = client.patch(
        f"/api/v1/baggage/{baggage_id}/cancel",
        headers=auth_headers(token),
    )
    assert cancel.status_code == 200

    response = add_tracking(
        client, token, baggage_id,
        "registered", "Check-in Counter",
    )

    assert response.status_code == 400
