from datetime import datetime, timedelta, timezone

from app.core.security import hash_password, create_access_token
from app.models.user import User
from app.models.airport import Airport
from app.models.terminal import Terminal
from app.models.flight import Flight
from app.utils.enums import UserRole


def create_baggage_test_data(db):
    user = User(
        full_name="Baggage Test Admin",
        email="baggage_admin_test@example.com",
        hashed_password=hash_password("TestPassword123"),
        role=UserRole.AIRPORT_OPERATIONS_MANAGER,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    origin = Airport(
        iata_code="BGA",
        name="Baggage Origin Airport",
        city="Chennai",
        country="India",
        timezone="Asia/Kolkata",
    )

    destination = Airport(
        iata_code="BGB",
        name="Baggage Destination Airport",
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
        code="BGT",
        name="Baggage Test Terminal",
        capacity=100,
    )
    db.add(terminal)
    db.commit()
    db.refresh(terminal)

    flight = Flight(
        flight_number="BG100",
        airline="Baggage Test Airlines",
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


def create_test_passenger(client, token, flight_id, suffix="001"):
    passenger_response = client.post(
        "/api/v1/passengers",
        json={
            "first_name": "Arun",
            "last_name": "Kumar",
            "email": f"baggage_passenger_{suffix}@example.com",
            "phone": "9876543210",
            "identification_type": "passport",
            "identification_reference": f"BAGGAGE-PASS-{suffix}",
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
            "booking_reference": f"BAGGAGE-BOOK-{suffix}",
        },
        headers=auth_headers(token),
    )

    assert assignment_response.status_code == 201

    return passenger_id


def baggage_payload(passenger_id, flight_id):
    return {
        "passenger_id": passenger_id,
        "flight_id": flight_id,
        "baggage_type": "checked",
        "weight_kg": 20.5,
        "description": "One standard travel suitcase",
    }


def test_register_baggage(client, db):
    flight, token = create_baggage_test_data(db)

    passenger_id = create_test_passenger(
        client, token, flight.id
    )

    response = client.post(
        "/api/v1/baggage",
        json=baggage_payload(passenger_id, flight.id),
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    assert response.json()["passenger_id"] == passenger_id
    assert response.json()["flight_id"] == flight.id
    assert response.json()["baggage_type"] == "checked"
    assert response.json()["weight_kg"] == 20.5
    assert response.json()["status"] == "registered"
    assert response.json()["baggage_tag_number"].startswith("BAG-")


def test_list_baggage(client, db):
    flight, token = create_baggage_test_data(db)

    passenger_id = create_test_passenger(
        client, token, flight.id, "002"
    )

    client.post(
        "/api/v1/baggage",
        json=baggage_payload(passenger_id, flight.id),
        headers=auth_headers(token),
    )

    response = client.get(
        "/api/v1/baggage",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_filter_baggage_by_passenger(client, db):
    flight, token = create_baggage_test_data(db)

    passenger_id = create_test_passenger(
        client, token, flight.id, "003"
    )

    client.post(
        "/api/v1/baggage",
        json=baggage_payload(passenger_id, flight.id),
        headers=auth_headers(token),
    )

    response = client.get(
        f"/api/v1/baggage?passenger_id={passenger_id}",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_filter_baggage_by_flight(client, db):
    flight, token = create_baggage_test_data(db)

    passenger_id = create_test_passenger(
        client, token, flight.id, "004"
    )

    client.post(
        "/api/v1/baggage",
        json=baggage_payload(passenger_id, flight.id),
        headers=auth_headers(token),
    )

    response = client.get(
        f"/api/v1/baggage?flight_id={flight.id}",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_update_baggage(client, db):
    flight, token = create_baggage_test_data(db)

    passenger_id = create_test_passenger(
        client, token, flight.id, "005"
    )

    create = client.post(
        "/api/v1/baggage",
        json=baggage_payload(passenger_id, flight.id),
        headers=auth_headers(token),
    )

    baggage_id = create.json()["id"]

    response = client.patch(
        f"/api/v1/baggage/{baggage_id}",
        json={
            "weight_kg": 25.0,
            "description": "Updated suitcase weight",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["weight_kg"] == 25.0
    assert response.json()["description"] == "Updated suitcase weight"


def test_cancel_baggage(client, db):
    flight, token = create_baggage_test_data(db)

    passenger_id = create_test_passenger(
        client, token, flight.id, "006"
    )

    create = client.post(
        "/api/v1/baggage",
        json=baggage_payload(passenger_id, flight.id),
        headers=auth_headers(token),
    )

    baggage_id = create.json()["id"]

    response = client.patch(
        f"/api/v1/baggage/{baggage_id}/cancel",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_get_nonexistent_baggage(client, db):
    flight, token = create_baggage_test_data(db)

    response = client.get(
        "/api/v1/baggage/99999",
        headers=auth_headers(token),
    )

    assert response.status_code == 404


def test_reject_invalid_baggage_weight(client, db):
    flight, token = create_baggage_test_data(db)

    passenger_id = create_test_passenger(
        client, token, flight.id, "007"
    )

    payload = baggage_payload(passenger_id, flight.id)
    payload["weight_kg"] = 0

    response = client.post(
        "/api/v1/baggage",
        json=payload,
        headers=auth_headers(token),
    )

    assert response.status_code == 422
def test_reject_baggage_status_change_through_general_update(client, db):
    flight, token = create_baggage_test_data(db)

    passenger_id = create_test_passenger(
        client, token, flight.id, "008"
    )

    create = client.post(
        "/api/v1/baggage",
        json=baggage_payload(passenger_id, flight.id),
        headers=auth_headers(token),
    )

    baggage_id = create.json()["id"]

    response = client.patch(
        f"/api/v1/baggage/{baggage_id}",
        json={"status": "cancelled"},
        headers=auth_headers(token),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Use the cancellation endpoint to cancel baggage"
    )


def test_reject_modification_of_cancelled_baggage(client, db):
    flight, token = create_baggage_test_data(db)

    passenger_id = create_test_passenger(
        client, token, flight.id, "009"
    )

    create = client.post(
        "/api/v1/baggage",
        json=baggage_payload(passenger_id, flight.id),
        headers=auth_headers(token),
    )

    baggage_id = create.json()["id"]

    cancel = client.patch(
        f"/api/v1/baggage/{baggage_id}/cancel",
        headers=auth_headers(token),
    )

    assert cancel.status_code == 200

    response = client.patch(
        f"/api/v1/baggage/{baggage_id}",
        json={"weight_kg": 25.0},
        headers=auth_headers(token),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Cancelled baggage cannot be modified"
    )
