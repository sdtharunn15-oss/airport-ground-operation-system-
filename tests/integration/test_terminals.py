from fastapi.testclient import TestClient

from app.utils.enums import UserRole

from tests.integration.test_airports import (
    create_user_token,
    airport_payload,
)


def create_airport(client, headers):
    response = client.post(
        "/api/v1/airports",
        json=airport_payload(),
        headers=headers,
    )

    assert response.status_code == 201
    return response.json()["id"]


def terminal_payload(code="T1"):
    return {
        "code": code,
        "name": "Terminal 1",
        "capacity": 5000,
        "status": "operational",
    }


def test_create_terminal(client: TestClient, db):
    token = create_user_token(db)
    headers = {"Authorization": f"Bearer {token}"}

    airport_id = create_airport(client, headers)

    response = client.post(
        f"/api/v1/airports/{airport_id}/terminals",
        json=terminal_payload(),
        headers=headers,
    )

    assert response.status_code == 201
    assert response.json()["code"] == "T1"
    assert response.json()["capacity"] == 5000


def test_terminal_requires_existing_airport(client, db):
    token = create_user_token(db)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/v1/airports/9999/terminals",
        json=terminal_payload(),
        headers=headers,
    )

    assert response.status_code == 404


def test_duplicate_terminal_code(client, db):
    token = create_user_token(db)
    headers = {"Authorization": f"Bearer {token}"}

    airport_id = create_airport(client, headers)
    url = f"/api/v1/airports/{airport_id}/terminals"

    client.post(url, json=terminal_payload(), headers=headers)

    response = client.post(
        url,
        json=terminal_payload(),
        headers=headers,
    )

    assert response.status_code == 409


def test_terminal_capacity_must_be_positive(client, db):
    token = create_user_token(db)
    headers = {"Authorization": f"Bearer {token}"}

    airport_id = create_airport(client, headers)

    payload = terminal_payload()
    payload["capacity"] = 0

    response = client.post(
        f"/api/v1/airports/{airport_id}/terminals",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 422


def test_list_terminals(client, db):
    token = create_user_token(db)
    headers = {"Authorization": f"Bearer {token}"}

    airport_id = create_airport(client, headers)

    client.post(
        f"/api/v1/airports/{airport_id}/terminals",
        json=terminal_payload(),
        headers=headers,
    )

    response = client.get(
        f"/api/v1/airports/{airport_id}/terminals",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_get_terminal(client, db):
    token = create_user_token(db)
    headers = {"Authorization": f"Bearer {token}"}

    airport_id = create_airport(client, headers)

    create_response = client.post(
        f"/api/v1/airports/{airport_id}/terminals",
        json=terminal_payload(),
        headers=headers,
    )

    terminal_id = create_response.json()["id"]

    response = client.get(
        f"/api/v1/terminals/{terminal_id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == terminal_id


def test_update_terminal(client, db):
    token = create_user_token(db)
    headers = {"Authorization": f"Bearer {token}"}

    airport_id = create_airport(client, headers)

    create_response = client.post(
        f"/api/v1/airports/{airport_id}/terminals",
        json=terminal_payload(),
        headers=headers,
    )

    terminal_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/terminals/{terminal_id}",
        json={"capacity": 7000},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["capacity"] == 7000


def test_delete_terminal(client, db):
    token = create_user_token(db, UserRole.SUPER_ADMIN)
    headers = {"Authorization": f"Bearer {token}"}

    airport_id = create_airport(client, headers)

    create_response = client.post(
        f"/api/v1/airports/{airport_id}/terminals",
        json=terminal_payload(),
        headers=headers,
    )

    terminal_id = create_response.json()["id"]

    response = client.delete(
        f"/api/v1/terminals/{terminal_id}",
        headers=headers,
    )

    assert response.status_code == 204