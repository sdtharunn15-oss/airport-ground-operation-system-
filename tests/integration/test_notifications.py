import secrets

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import create_access_token, hash_password
from app.utils.enums import UserRole, NotificationType
from app.models.notification import Notification

client = TestClient(app)


@pytest.fixture
def notification_test_data():
    db = SessionLocal()
    suffix = secrets.token_hex(5)

    try:
        manager = User(
            full_name="Notification Test Manager",
            email=f"notification-manager-{suffix}@example.com",
            hashed_password=hash_password("TestPassword123"),
            role=UserRole.AIRPORT_OPERATIONS_MANAGER,
            is_active=True,
            is_verified=True,
        )

        recipient = User(
            full_name="Notification Test Recipient",
            email=f"notification-user-{suffix}@example.com",
            hashed_password=hash_password("TestPassword123"),
            role=UserRole.GATE_AGENT,
            is_active=True,
            is_verified=True,
        )

        db.add_all([manager, recipient])
        db.commit()
        db.refresh(manager)
        db.refresh(recipient)

        yield {
            "manager_id": manager.id,
            "recipient_id": recipient.id,
            "manager_token": create_access_token(str(manager.id)),
            "recipient_token": create_access_token(str(recipient.id)),
        }

    finally:
        db.close()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def event_payload(data, notification_type="flight_delay"):
    return {
        "recipient_ids": [data["recipient_id"]],
        "notification_type": notification_type,
        "title": "Airport Operations Update",
        "message": "Test notification message",
        "related_entity_type": "flight",
        "related_entity_id": 1,
    }


@pytest.mark.parametrize(
    "notification_type",
    [item.value for item in NotificationType],
)
def test_generate_all_notification_event_types(
    notification_test_data,
    notification_type,
):
    data = notification_test_data

    response = client.post(
        "/api/v1/notifications/events",
        json=event_payload(data, notification_type),
        headers=auth(data["manager_token"]),
    )

    assert response.status_code == 201, response.text
    result = response.json()

    assert len(result) == 1
    assert result[0]["notification_type"] == notification_type
    assert result[0]["status"] == "unread"
    assert result[0]["recipient_id"] == data["recipient_id"]


def test_list_my_notifications(notification_test_data):
    data = notification_test_data

    created = client.post(
        "/api/v1/notifications/events",
        json=event_payload(data),
        headers=auth(data["manager_token"]),
    )
    assert created.status_code == 201, created.text

    response = client.get(
        "/api/v1/notifications/me",
        headers=auth(data["recipient_token"]),
    )

    assert response.status_code == 200, response.text
    result = response.json()

    assert result["total"] >= 1
    assert result["unread_count"] >= 1
    assert all(
        item["recipient_id"] == data["recipient_id"]
        for item in result["items"]
    )


def test_mark_notification_as_read(notification_test_data):
    data = notification_test_data

    created = client.post(
        "/api/v1/notifications/events",
        json=event_payload(data),
        headers=auth(data["manager_token"]),
    )
    notification_id = created.json()[0]["id"]

    response = client.patch(
        f"/api/v1/notifications/{notification_id}/read",
        headers=auth(data["recipient_token"]),
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "read"
    assert response.json()["read_at"] is not None


def test_mark_all_notifications_as_read(notification_test_data):
    data = notification_test_data

    created = client.post(
        "/api/v1/notifications/events",
        json=event_payload(data),
        headers=auth(data["manager_token"]),
    )
    assert created.status_code == 201, created.text

    response = client.patch(
        "/api/v1/notifications/read-all",
        headers=auth(data["recipient_token"]),
    )

    assert response.status_code == 200, response.text

    inbox = client.get(
        "/api/v1/notifications/me?status=unread",
        headers=auth(data["recipient_token"]),
    )

    assert inbox.status_code == 200, inbox.text
    assert inbox.json()["total"] == 0


def test_user_cannot_read_another_users_notification(notification_test_data):
    data = notification_test_data

    created = client.post(
        "/api/v1/notifications/events",
        json=event_payload(data),
        headers=auth(data["manager_token"]),
    )
    notification_id = created.json()[0]["id"]

    response = client.patch(
        f"/api/v1/notifications/{notification_id}/read",
        headers=auth(data["manager_token"]),
    )

    assert response.status_code == 404


def test_non_management_user_cannot_generate_event(notification_test_data):
    data = notification_test_data

    response = client.post(
        "/api/v1/notifications/events",
        json=event_payload(data),
        headers=auth(data["recipient_token"]),
    )

    assert response.status_code == 403


def test_notification_requires_authentication():
    response = client.get("/api/v1/notifications/me")
    assert response.status_code == 401
