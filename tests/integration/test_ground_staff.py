from app.core.security import hash_password, create_access_token
from app.models.user import User
from app.models.airport import Airport
from app.models.terminal import Terminal
from app.utils.enums import UserRole


def create_ground_staff_test_data(db):
    user = User(
        full_name="Ground Staff Test Admin",
        email="ground_staff_admin_test@example.com",
        hashed_password=hash_password("TestPassword123"),
        role=UserRole.AIRPORT_OPERATIONS_MANAGER,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    airport = Airport(
        iata_code="GSA",
        name="Ground Staff Airport",
        city="Chennai",
        country="India",
        timezone="Asia/Kolkata",
    )
    db.add(airport)
    db.commit()
    db.refresh(airport)

    terminal = Terminal(
        airport_id=airport.id,
        code="GST",
        name="Ground Staff Terminal",
        capacity=100,
    )
    db.add(terminal)
    db.commit()
    db.refresh(terminal)

    token = create_access_token(str(user.id))
    return airport, terminal, token


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_ground_staff(client, db):
    airport, terminal, token = create_ground_staff_test_data(db)

    response = client.post(
        "/api/v1/ground-staff",
        json={
            "employee_code": "GS001",
            "full_name": "Arun Kumar",
            "email": "arun.groundstaff@example.com",
            "phone": "9876543210",
            "role": "baggage_handling_staff",
            "airport_id": airport.id,
            "terminal_id": terminal.id,
            "shift_start": "06:00",
            "shift_end": "14:00",
        },
        headers=auth_headers(token),
    )

    print('VALIDATION ERROR:', response.text)
    assert response.status_code == 201
    data = response.json()
    assert data["employee_code"] == "GS001"
    assert data["full_name"] == "Arun Kumar"
    assert data["airport_id"] == airport.id
    assert data["terminal_id"] == terminal.id
    assert data["availability"] == "available"




def test_list_ground_staff(client, db):
    airport, terminal, token = create_ground_staff_test_data(db)

    client.post(
        "/api/v1/ground-staff",
        json={
            "employee_code": "GS002",
            "full_name": "Kumar Raj",
            "email": "kumar.groundstaff@example.com",
            "phone": "9876543211",
            "role": "baggage_handling_staff",
            "airport_id": airport.id,
            "terminal_id": terminal.id,
        },
        headers=auth_headers(token),
    )

    response = client.get(
        "/api/v1/ground-staff",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["employee_code"] == "GS002"


def test_get_ground_staff_by_id(client, db):
    airport, terminal, token = create_ground_staff_test_data(db)

    create_response = client.post(
        "/api/v1/ground-staff",
        json={
            "employee_code": "GS003",
            "full_name": "Suresh Kumar",
            "email": "suresh.groundstaff@example.com",
            "phone": "9876543212",
            "role": "ground_staff_supervisor",
            "airport_id": airport.id,
            "terminal_id": terminal.id,
        },
        headers=auth_headers(token),
    )

    staff_id = create_response.json()["id"]

    response = client.get(
        f"/api/v1/ground-staff/{staff_id}",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["id"] == staff_id
    assert response.json()["full_name"] == "Suresh Kumar"

def test_update_ground_staff(client, db):
    airport, terminal, token = create_ground_staff_test_data(db)

    create_response = client.post(
        "/api/v1/ground-staff",
        json={
            "employee_code": "GS004",
            "full_name": "Old Name",
            "email": "update.groundstaff@example.com",
            "phone": "9876543213",
            "role": "baggage_handling_staff",
            "airport_id": airport.id,
            "terminal_id": terminal.id,
        },
        headers=auth_headers(token),
    )

    staff_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/ground-staff/{staff_id}",
        json={"full_name": "Updated Name"},
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Name"


def test_update_ground_staff_availability(client, db):
    airport, terminal, token = create_ground_staff_test_data(db)

    create_response = client.post(
        "/api/v1/ground-staff",
        json={
            "employee_code": "GS005",
            "full_name": "Availability Test",
            "email": "availability.groundstaff@example.com",
            "phone": "9876543214",
            "role": "baggage_handling_staff",
            "airport_id": airport.id,
            "terminal_id": terminal.id,
        },
        headers=auth_headers(token),
    )

    staff_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/ground-staff/{staff_id}",
        json={"availability": "busy"},
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["availability"] == "busy"

def test_reject_duplicate_ground_staff(client, db):
    airport, terminal, token = create_ground_staff_test_data(db)

    payload = {
        "employee_code": "GS006",
        "full_name": "Duplicate Test",
        "email": "duplicate.groundstaff@example.com",
        "phone": "9876543215",
        "role": "baggage_handling_staff",
        "airport_id": airport.id,
        "terminal_id": terminal.id,
    }

    first_response = client.post(
        "/api/v1/ground-staff",
        json=payload,
        headers=auth_headers(token),
    )
    assert first_response.status_code == 201

    second_response = client.post(
        "/api/v1/ground-staff",
        json=payload,
        headers=auth_headers(token),
    )
    assert second_response.status_code == 409


def test_reject_ground_staff_invalid_airport(client, db):
    airport, terminal, token = create_ground_staff_test_data(db)

    response = client.post(
        "/api/v1/ground-staff",
        json={
            "employee_code": "GS007",
            "full_name": "Invalid Airport Staff",
            "email": "invalid.airport@example.com",
            "phone": "9876543216",
            "role": "baggage_handling_staff",
            "airport_id": 99999,
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 404


def test_delete_ground_staff(client, db):
    airport, terminal, token = create_ground_staff_test_data(db)

    create_response = client.post(
        "/api/v1/ground-staff",
        json={
            "employee_code": "GS008",
            "full_name": "Delete Test",
            "email": "delete.groundstaff@example.com",
            "phone": "9876543217",
            "role": "baggage_handling_staff",
            "airport_id": airport.id,
            "terminal_id": terminal.id,
        },
        headers=auth_headers(token),
    )

    staff_id = create_response.json()["id"]

    response = client.delete(
        f"/api/v1/ground-staff/{staff_id}",
        headers=auth_headers(token),
    )

    assert response.status_code == 200

    get_response = client.get(
        f"/api/v1/ground-staff/{staff_id}",
        headers=auth_headers(token),
    )

    assert get_response.status_code == 404
