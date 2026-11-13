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


@pytest.fixture
def setup_equipment_data():
    db = SessionLocal()
    suffix = secrets.token_hex(5).upper()

    user = User(
        full_name="Equipment Test Manager",
        email=f"equipment-manager-{suffix}@example.com",
        hashed_password=hash_password("TestPassword123"),
        role=UserRole.AIRPORT_OPERATIONS_MANAGER,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    iata_code = "".join(
        secrets.choice(string.ascii_uppercase) for _ in range(3)
    )

    while db.query(Airport).filter(
        Airport.iata_code == iata_code
    ).first():
        iata_code = "".join(
            secrets.choice(string.ascii_uppercase) for _ in range(3)
        )

    airport = Airport(
        iata_code=iata_code,
        name=f"Equipment Test Airport {suffix}",
        city="Chennai",
        country="India",
        timezone="Asia/Kolkata",
    )
    db.add(airport)
    db.commit()
    db.refresh(airport)

    terminal = Terminal(
        airport_id=airport.id,
        code=f"ET{suffix[:6]}",
        name="Equipment Test Terminal",
        capacity=100,
    )
    db.add(terminal)
    db.commit()
    db.refresh(terminal)

    token = create_access_token(subject=str(user.id))

    yield {
        "airport_id": airport.id,
        "terminal_id": terminal.id,
        "token": token,
        "suffix": suffix,
    }

    db.close()


def equipment_headers(data):
    return {"Authorization": f"Bearer {data['token']}"}

def test_create_ground_equipment(setup_equipment_data):
    data = setup_equipment_data

    response = client.post(
        "/api/v1/ground-equipment",
        json={
            "equipment_code": f"TUG-{data['suffix']}",
            "name": "Airport Baggage Tug",
            "equipment_type": "tug",
            "registration_number": f"REG-{data['suffix']}",
            "airport_id": data["airport_id"],
            "terminal_id": data["terminal_id"],
            "status": "available",
            "remarks": "Test equipment",
        },
        headers=equipment_headers(data),
    )

    assert response.status_code == 201, response.text
    result = response.json()
    assert result["equipment_type"] == "tug"
    assert result["status"] == "available"
    assert result["airport_id"] == data["airport_id"]

def test_list_ground_equipment(setup_equipment_data):
    data = setup_equipment_data

    create_response = client.post(
        "/api/v1/ground-equipment",
        json={
            "equipment_code": f"LIST-{data['suffix']}",
            "name": "Baggage Belt Loader",
            "equipment_type": "belt_loader",
            "airport_id": data["airport_id"],
        },
        headers=equipment_headers(data),
    )
    assert create_response.status_code == 201, create_response.text

    response = client.get(
        f"/api/v1/ground-equipment?airport_id={data['airport_id']}",
        headers=equipment_headers(data),
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] >= 1
    assert any(
        item["equipment_code"] == f"LIST-{data['suffix']}"
        for item in response.json()["items"]
    )

def test_get_ground_equipment_by_id(setup_equipment_data):
    data = setup_equipment_data

    create_response = client.post(
        "/api/v1/ground-equipment",
        json={
            "equipment_code": f"GET-{data['suffix']}",
            "name": "Airport GPU",
            "equipment_type": "gpu",
            "airport_id": data["airport_id"],
        },
        headers=equipment_headers(data),
    )
    assert create_response.status_code == 201, create_response.text
    equipment_id = create_response.json()["id"]

    response = client.get(
        f"/api/v1/ground-equipment/{equipment_id}",
        headers=equipment_headers(data),
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == equipment_id
    assert response.json()["name"] == "Airport GPU"

def test_update_ground_equipment(setup_equipment_data):
    data = setup_equipment_data

    create_response = client.post(
        "/api/v1/ground-equipment",
        json={
            "equipment_code": f"UPDATE-{data['suffix']}",
            "name": "Old Equipment Name",
            "equipment_type": "tug",
            "airport_id": data["airport_id"],
        },
        headers=equipment_headers(data),
    )
    assert create_response.status_code == 201, create_response.text
    equipment_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/ground-equipment/{equipment_id}",
        json={
            "name": "Updated Equipment Name",
            "status": "under_maintenance",
            "remarks": "Scheduled maintenance",
        },
        headers=equipment_headers(data),
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Updated Equipment Name"
    assert response.json()["status"] == "under_maintenance"
    assert response.json()["remarks"] == "Scheduled maintenance"

def test_delete_ground_equipment(setup_equipment_data):
    data = setup_equipment_data

    create_response = client.post(
        "/api/v1/ground-equipment",
        json={
            "equipment_code": f"DELETE-{data['suffix']}",
            "name": "Equipment for Deletion",
            "equipment_type": "passenger_stairs",
            "airport_id": data["airport_id"],
        },
        headers=equipment_headers(data),
    )
    assert create_response.status_code == 201, create_response.text
    equipment_id = create_response.json()["id"]

    delete_response = client.delete(
        f"/api/v1/ground-equipment/{equipment_id}",
        headers=equipment_headers(data),
    )

    assert delete_response.status_code == 200, delete_response.text

    get_response = client.get(
        f"/api/v1/ground-equipment/{equipment_id}",
        headers=equipment_headers(data),
    )

    assert get_response.status_code == 404

def test_duplicate_equipment_code(setup_equipment_data):
    data = setup_equipment_data

    payload = {
        "equipment_code": f"DUP-{data['suffix']}",
        "name": "Duplicate Test Equipment",
        "equipment_type": "tug",
        "airport_id": data["airport_id"],
    }

    first_response = client.post(
        "/api/v1/ground-equipment",
        json=payload,
        headers=equipment_headers(data),
    )
    assert first_response.status_code == 201, first_response.text

    second_response = client.post(
        "/api/v1/ground-equipment",
        json=payload,
        headers=equipment_headers(data),
    )

    assert second_response.status_code == 409, second_response.text

def test_create_equipment_with_invalid_airport(setup_equipment_data):
    data = setup_equipment_data

    response = client.post(
        "/api/v1/ground-equipment",
        json={
            "equipment_code": f"INVALID-{data['suffix']}",
            "name": "Invalid Airport Equipment",
            "equipment_type": "tug",
            "airport_id": 999999,
        },
        headers=equipment_headers(data),
    )

    assert response.status_code == 404, response.text

