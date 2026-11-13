import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.models.user import User
from app.utils.enums import UserRole


def create_user_token(db, role=UserRole.AIRPORT_OPERATIONS_MANAGER):
    user = User(
        full_name="Airport Test Manager",
        email=f"{role.value}@example.com",
        hashed_password="hashed-password",
        role=role,
        is_active=True,
        is_verified=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # Pass the user ID directly as a string.
    # create_access_token() adds the JWT claims itself.
    token = create_access_token(str(user.id))

    return token

@pytest.fixture
def manager_headers(db):
    token = create_user_token(db)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def staff_headers(db):
    token = create_user_token(
        db,
        UserRole.BAGGAGE_HANDLING_STAFF,
    )
    return {"Authorization": f"Bearer {token}"}


def airport_payload(code="MAA"):
    return {
        "iata_code": code,
        "name": "Chennai International Airport",
        "city": "Chennai",
        "country": "India",
        "timezone": "Asia/Kolkata",
        "status": "operational",
    }


def test_create_airport(client: TestClient, manager_headers):
    response = client.post(
        "/api/v1/airports",
        json=airport_payload(),
        headers=manager_headers,
    )

    assert response.status_code == 201
    assert response.json()["iata_code"] == "MAA"
    assert response.json()["city"] == "Chennai"


def test_duplicate_airport_code(client, manager_headers):
    client.post(
        "/api/v1/airports",
        json=airport_payload(),
        headers=manager_headers,
    )

    response = client.post(
        "/api/v1/airports",
        json=airport_payload(),
        headers=manager_headers,
    )

    assert response.status_code == 409


def test_invalid_iata_code(client, manager_headers):
    payload = airport_payload("CHENNAI")

    response = client.post(
        "/api/v1/airports",
        json=payload,
        headers=manager_headers,
    )

    assert response.status_code == 422


def test_list_airports(client, manager_headers):
    client.post(
        "/api/v1/airports",
        json=airport_payload(),
        headers=manager_headers,
    )

    response = client.get(
        "/api/v1/airports",
        headers=manager_headers,
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_search_airports(client, manager_headers):
    client.post(
        "/api/v1/airports",
        json=airport_payload(),
        headers=manager_headers,
    )

    response = client.get(
        "/api/v1/airports?search=Chennai",
        headers=manager_headers,
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_get_airport(client, manager_headers):
    create_response = client.post(
        "/api/v1/airports",
        json=airport_payload(),
        headers=manager_headers,
    )

    airport_id = create_response.json()["id"]

    response = client.get(
        f"/api/v1/airports/{airport_id}",
        headers=manager_headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == airport_id


def test_update_airport(client, manager_headers):
    create_response = client.post(
        "/api/v1/airports",
        json=airport_payload(),
        headers=manager_headers,
    )

    airport_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/airports/{airport_id}",
        json={"city": "New Chennai"},
        headers=manager_headers,
    )

    assert response.status_code == 200
    assert response.json()["city"] == "New Chennai"


def test_delete_airport(client, db):
    token = create_user_token(db, UserRole.SUPER_ADMIN)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/api/v1/airports",
        json=airport_payload(),
        headers=headers,
    )

    airport_id = create_response.json()["id"]

    response = client.delete(
        f"/api/v1/airports/{airport_id}",
        headers=headers,
    )

    assert response.status_code == 204


def test_airport_creation_requires_permission(client, staff_headers):
    response = client.post(
        "/api/v1/airports",
        json=airport_payload(),
        headers=staff_headers,
    )

    assert response.status_code == 403