def test_user_registration(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test User",
            "email": "test@example.com",
            "password": "TestPassword123"
        }
    )

    assert response.status_code == 201
    assert response.json()["email"] == "test@example.com"
    assert response.json()["role"] == "baggage_handling_staff"


def test_duplicate_registration(client):
    payload = {
        "full_name": "Test User",
        "email": "duplicate@example.com",
        "password": "TestPassword123"
    }

    first = client.post("/api/v1/auth/register", json=payload)
    second = client.post("/api/v1/auth/register", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409


def test_login_success(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Login User",
            "email": "login@example.com",
            "password": "TestPassword123"
        }
    )

    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "login@example.com",
            "password": "TestPassword123"
        }
    )

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()


def test_login_invalid_password(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Login User",
            "email": "wrong@example.com",
            "password": "TestPassword123"
        }
    )

    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "wrong@example.com",
            "password": "WrongPassword123"
        }
    )

    assert response.status_code == 401


def test_current_user_authenticated(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Current User",
            "email": "current@example.com",
            "password": "TestPassword123"
        }
    )

    login = client.post(
        "/api/v1/auth/login",
        data={
            "username": "current@example.com",
            "password": "TestPassword123"
        }
    )

    token = login.json()["access_token"]

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == "current@example.com"


def test_current_user_without_token(client):
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_refresh_token(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Refresh User",
            "email": "refresh@example.com",
            "password": "TestPassword123"
        }
    )

    login = client.post(
        "/api/v1/auth/login",
        data={
            "username": "refresh@example.com",
            "password": "TestPassword123"
        }
    )

    refresh_token = login.json()["refresh_token"]

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token}
    )

    assert response.status_code == 200
    assert "access_token" in response.json()


def test_refresh_rejects_access_token(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Token User",
            "email": "token@example.com",
            "password": "TestPassword123"
        }
    )

    login = client.post(
        "/api/v1/auth/login",
        data={
            "username": "token@example.com",
            "password": "TestPassword123"
        }
    )

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login.json()["access_token"]}
    )

    assert response.status_code == 401
