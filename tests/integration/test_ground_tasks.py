from app.core.security import hash_password, create_access_token
from app.models.user import User
from app.models.airport import Airport
from app.models.terminal import Terminal
from app.utils.enums import UserRole


def create_ground_task_test_data(db):
    user = User(
        full_name="Ground Task Test Admin",
        email="ground_task_admin_test@example.com",
        hashed_password=hash_password("TestPassword123"),
        role=UserRole.AIRPORT_OPERATIONS_MANAGER,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    airport = Airport(
        iata_code="GTA",
        name="Ground Task Airport",
        city="Chennai",
        country="India",
        timezone="Asia/Kolkata",
    )
    db.add(airport)
    db.commit()
    db.refresh(airport)

    terminal = Terminal(
        airport_id=airport.id,
        code="GTT",
        name="Ground Task Terminal",
        capacity=100,
    )
    db.add(terminal)
    db.commit()
    db.refresh(terminal)

    token = create_access_token(str(user.id))
    return airport, terminal, token


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_ground_task(client, db):
    airport, terminal, token = create_ground_task_test_data(db)

    response = client.post(
        "/api/v1/ground-tasks",
        json={
            "task_code": "GT001",
            "title": "Aircraft Cabin Cleaning",
            "description": "Clean and prepare aircraft cabin",
            "airport_id": airport.id,
            "terminal_id": terminal.id,
            "priority": "high",
            "remarks": "Complete before departure",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["task_code"] == "GT001"
    assert data["title"] == "Aircraft Cabin Cleaning"
    assert data["priority"] == "high"
    assert data["status"] == "pending"
    assert data["airport_id"] == airport.id

def test_list_ground_tasks(client, db):
    airport, terminal, token = create_ground_task_test_data(db)

    client.post(
        "/api/v1/ground-tasks",
        json={
            "task_code": "GT002",
            "title": "Baggage Area Inspection",
            "airport_id": airport.id,
            "terminal_id": terminal.id,
        },
        headers=auth_headers(token),
    )

    response = client.get(
        "/api/v1/ground-tasks",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["task_code"] == "GT002"


def test_get_ground_task_by_id(client, db):
    airport, terminal, token = create_ground_task_test_data(db)

    create_response = client.post(
        "/api/v1/ground-tasks",
        json={
            "task_code": "GT003",
            "title": "Prepare Boarding Gate",
            "airport_id": airport.id,
            "terminal_id": terminal.id,
        },
        headers=auth_headers(token),
    )

    task_id = create_response.json()["id"]

    response = client.get(
        f"/api/v1/ground-tasks/{task_id}",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["id"] == task_id
    assert response.json()["task_code"] == "GT003"

def test_update_ground_task(client, db):
    airport, terminal, token = create_ground_task_test_data(db)

    create_response = client.post(
        "/api/v1/ground-tasks",
        json={
            "task_code": "GT004",
            "title": "Old Task Title",
            "airport_id": airport.id,
            "terminal_id": terminal.id,
        },
        headers=auth_headers(token),
    )

    task_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/ground-tasks/{task_id}",
        json={
            "title": "Updated Task Title",
            "priority": "urgent",
            "remarks": "Handle immediately",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated Task Title"
    assert response.json()["priority"] == "urgent"
    assert response.json()["remarks"] == "Handle immediately"

def test_delete_ground_task(client, db):
    airport, terminal, token = create_ground_task_test_data(db)

    create_response = client.post(
        "/api/v1/ground-tasks",
        json={
            "task_code": "GT005",
            "title": "Temporary Cleaning Task",
            "airport_id": airport.id,
            "terminal_id": terminal.id,
        },
        headers=auth_headers(token),
    )

    task_id = create_response.json()["id"]

    response = client.delete(
        f"/api/v1/ground-tasks/{task_id}",
        headers=auth_headers(token),
    )

    assert response.status_code == 200

    get_response = client.get(
        f"/api/v1/ground-tasks/{task_id}",
        headers=auth_headers(token),
    )

    assert get_response.status_code == 404

def test_duplicate_ground_task_code(client, db):
    airport, terminal, token = create_ground_task_test_data(db)

    task_data = {
        "task_code": "GT006",
        "title": "Baggage Preparation",
        "airport_id": airport.id,
        "terminal_id": terminal.id,
    }

    first_response = client.post(
        "/api/v1/ground-tasks",
        json=task_data,
        headers=auth_headers(token),
    )

    second_response = client.post(
        "/api/v1/ground-tasks",
        json=task_data,
        headers=auth_headers(token),
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409

def test_create_ground_task_invalid_airport(client, db):
    airport, terminal, token = create_ground_task_test_data(db)

    response = client.post(
        "/api/v1/ground-tasks",
        json={
            "task_code": "GT007",
            "title": "Invalid Airport Task",
            "airport_id": 99999,
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Airport not found"

def test_assign_ground_staff_to_task(client, db):
    airport, terminal, token = create_ground_task_test_data(db)
    headers = auth_headers(token)

    staff_response = client.post(
        "/api/v1/ground-staff",
        json={
            "employee_code": "GTS001",
            "full_name": "Task Assignment Staff",
            "email": "task_assignment_staff@example.com",
            "phone": "9876543210",
            "role": "baggage_handling_staff",
            "airport_id": airport.id,
            "terminal_id": terminal.id,
        },
        headers=headers,
    )

    assert staff_response.status_code == 201
    staff_id = staff_response.json()["id"]

    task_response = client.post(
        "/api/v1/ground-tasks",
        json={
            "task_code": "GT008",
            "title": "Load Passenger Baggage",
            "airport_id": airport.id,
            "terminal_id": terminal.id,
            "assigned_staff_id": staff_id,
        },
        headers=headers,
    )

    assert task_response.status_code == 201
    assert task_response.json()["assigned_staff_id"] == staff_id
    assert task_response.json()["status"] == "assigned"

    updated_staff = client.get(
        f"/api/v1/ground-staff/{staff_id}",
        headers=headers,
    )

    assert updated_staff.status_code == 200
    assert updated_staff.json()["availability"] == "busy"

def test_ground_task_lifecycle(client, db):
    airport, terminal, token = create_ground_task_test_data(db)
    headers = auth_headers(token)

    staff_response = client.post(
        "/api/v1/ground-staff",
        json={
            "employee_code": "GTS002",
            "full_name": "Lifecycle Test Staff",
            "email": "lifecycle_staff@example.com",
            "phone": "9876543211",
            "role": "baggage_handling_staff",
            "airport_id": airport.id,
            "terminal_id": terminal.id,
        },
        headers=headers,
    )

    assert staff_response.status_code == 201
    staff_id = staff_response.json()["id"]

    task_response = client.post(
        "/api/v1/ground-tasks",
        json={
            "task_code": "GT009",
            "title": "Aircraft Baggage Loading",
            "airport_id": airport.id,
            "terminal_id": terminal.id,
            "assigned_staff_id": staff_id,
        },
        headers=headers,
    )

    assert task_response.status_code == 201
    task_id = task_response.json()["id"]

    start_response = client.patch(
        f"/api/v1/ground-tasks/{task_id}",
        json={"status": "in_progress"},
        headers=headers,
    )

    assert start_response.status_code == 200
    assert start_response.json()["status"] == "in_progress"
    assert start_response.json()["started_at"] is not None

    complete_response = client.patch(
        f"/api/v1/ground-tasks/{task_id}",
        json={"status": "completed"},
        headers=headers,
    )

    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "completed"
    assert complete_response.json()["completed_at"] is not None

    updated_staff = client.get(
        f"/api/v1/ground-staff/{staff_id}",
        headers=headers,
    )

    assert updated_staff.status_code == 200
    assert updated_staff.json()["availability"] == "available"
