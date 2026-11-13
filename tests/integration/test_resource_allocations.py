from datetime import datetime, timedelta
import secrets
import string

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.airport import Airport
from app.models.terminal import Terminal
from app.models.ground_staff import GroundStaff
from app.models.ground_equipment import GroundEquipment
from app.core.security import create_access_token, hash_password
from app.utils.enums import (
    UserRole,
    GroundStaffAvailability,
    GroundEquipmentStatus,
    GroundEquipmentType,
)

client = TestClient(app)


def unique_iata(db):
    while True:
        code = "".join(secrets.choice(string.ascii_uppercase) for _ in range(3))
        if not db.query(Airport).filter(Airport.iata_code == code).first():
            return code


@pytest.fixture
def setup_resource_data():
    db = SessionLocal()
    suffix = secrets.token_hex(5).upper()

    try:
        user = User(
            full_name="Resource Test Manager",
            email=f"resource-manager-{suffix}@example.com",
            hashed_password=hash_password("TestPassword123"),
            role=UserRole.AIRPORT_OPERATIONS_MANAGER,
            is_active=True,
            is_verified=True,
        )

        airport = Airport(
            iata_code=unique_iata(db),
            name="Resource Test Airport",
            city="Chennai",
            country="India",
            timezone="Asia/Kolkata",
        )

        db.add_all([user, airport])
        db.commit()
        db.refresh(user)
        db.refresh(airport)

        terminal = Terminal(
            airport_id=airport.id,
            code=f"RT{suffix[:6]}",
            name="Resource Test Terminal",
            capacity=100,
        )
        db.add(terminal)
        db.commit()
        db.refresh(terminal)

        staff = GroundStaff(
            employee_code=f"EMP-{suffix}",
            full_name="Resource Test Staff",
            email=f"staff-{suffix}@example.com",
            phone="9876543210",
            role=UserRole.BAGGAGE_HANDLING_STAFF,
            airport_id=airport.id,
            terminal_id=terminal.id,
            availability=GroundStaffAvailability.AVAILABLE,
        )

        equipment = GroundEquipment(
            equipment_code=f"EQ-{suffix}",
            name="Resource Test Tug",
            equipment_type=GroundEquipmentType.TUG,
            airport_id=airport.id,
            terminal_id=terminal.id,
            status=GroundEquipmentStatus.AVAILABLE,
        )

        db.add_all([staff, equipment])
        db.commit()
        db.refresh(staff)
        db.refresh(equipment)

        yield {
            "token": create_access_token(str(user.id)),
            "airport_id": airport.id,
            "terminal_id": terminal.id,
            "staff_id": staff.id,
            "equipment_id": equipment.id,
            "suffix": suffix,
        }

    finally:
        db.close()


def headers(data):
    return {"Authorization": f"Bearer {data['token']}"}


def allocation_payload(data, resource_type="ground_staff"):
    start = datetime.utcnow() + timedelta(days=1)

    payload = {
        "resource_type": resource_type,
        "airport_id": data["airport_id"],
        "terminal_id": data["terminal_id"],
        "allocation_start": start.isoformat(),
        "allocation_end": (start + timedelta(hours=2)).isoformat(),
        "remarks": "Test resource allocation",
    }

    if resource_type == "ground_staff":
        payload["staff_id"] = data["staff_id"]
    else:
        payload["equipment_id"] = data["equipment_id"]

    return payload


def test_create_staff_allocation(setup_resource_data):
    data = setup_resource_data

    response = client.post(
        "/api/v1/resource-allocations/",
        json=allocation_payload(data),
        headers=headers(data),
    )

    assert response.status_code == 201, response.text
    result = response.json()
    assert result["resource_type"] == "ground_staff"
    assert result["staff_id"] == data["staff_id"]
    assert result["status"] == "active"


def test_create_equipment_allocation(setup_resource_data):
    data = setup_resource_data

    response = client.post(
        "/api/v1/resource-allocations/",
        json=allocation_payload(data, "ground_equipment"),
        headers=headers(data),
    )

    assert response.status_code == 201, response.text
    result = response.json()
    assert result["resource_type"] == "ground_equipment"
    assert result["equipment_id"] == data["equipment_id"]
    assert result["status"] == "active"


def test_list_resource_allocations(setup_resource_data):
    data = setup_resource_data

    created = client.post(
        "/api/v1/resource-allocations/",
        json=allocation_payload(data),
        headers=headers(data),
    )
    assert created.status_code == 201, created.text

    response = client.get(
        f"/api/v1/resource-allocations/?airport_id={data['airport_id']}",
        headers=headers(data),
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] >= 1


def test_release_resource_allocation(setup_resource_data):
    data = setup_resource_data

    created = client.post(
        "/api/v1/resource-allocations/",
        json=allocation_payload(data),
        headers=headers(data),
    )
    assert created.status_code == 201, created.text

    allocation_id = created.json()["id"]

    response = client.patch(
        f"/api/v1/resource-allocations/{allocation_id}",
        json={"status": "released"},
        headers=headers(data),
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "released"


def test_invalid_allocation_period(setup_resource_data):
    data = setup_resource_data
    payload = allocation_payload(data)

    payload["allocation_end"] = (
        datetime.utcnow() - timedelta(hours=1)
    ).isoformat()

    response = client.post(
        "/api/v1/resource-allocations/",
        json=payload,
        headers=headers(data),
    )

    assert response.status_code == 400, response.text
