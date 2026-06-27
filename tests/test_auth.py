from app.core.security import get_password_hash
from app.models.user import User, Role


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_user_registration_forces_viewer(client, db_session):
    username = "test_viewer_user"
    password = "testpassword123"

    response = client.post(
        "/auth/register",
        json={"username": username, "password": password},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == username
    assert data["role"] == "viewer"
    assert "id" in data

    response_extra = client.post(
        "/auth/register",
        json={"username": "test_viewer_admin", "password": password, "role": "admin"},
    )
    assert response_extra.status_code == 201
    assert response_extra.json()["role"] == "viewer"


def test_login_and_rbac_flow(client, db_session):
    for role_name, username, pwd in [
        (Role.viewer, "viewer", "viewerpassword"),
        (Role.editor, "editor", "editorpassword"),
        (Role.admin, "admin", "adminpassword"),
    ]:
        existing = db_session.query(User).filter(User.username == username).first()
        if not existing:
            db_session.add(
                User(
                    username=username,
                    hashed_password=get_password_hash(pwd),
                    role=role_name,
                )
            )
    db_session.commit()

    response = client.post(
        "/auth/login",
        data={"username": "admin", "password": "wrongpassword"},
    )
    assert response.status_code == 401

    response = client.post(
        "/auth/login",
        data={"username": "viewer", "password": "viewerpassword"},
    )
    assert response.status_code == 200
    viewer_token = response.json()["access_token"]
    assert response.json()["token_type"] == "Bearer"

    response = client.post(
        "/auth/login",
        data={"username": "editor", "password": "editorpassword"},
    )
    assert response.status_code == 200
    editor_token = response.json()["access_token"]

    response = client.post(
        "/auth/login",
        data={"username": "admin", "password": "adminpassword"},
    )
    assert response.status_code == 200
    admin_token = response.json()["access_token"]

    asset_payload = {
        "type": "domain",
        "value": "example-rbac.com",
        "source": "manual_test",
        "tags": ["test"],
    }
    headers_viewer = {"Authorization": f"Bearer {viewer_token}"}
    response = client.post("/assets/", json=asset_payload, headers=headers_viewer)
    assert response.status_code == 403

    headers_editor = {"Authorization": f"Bearer {editor_token}"}
    response = client.post("/assets/", json=asset_payload, headers=headers_editor)
    assert response.status_code == 201
    asset_id = response.json()["id"]

    response = client.delete(f"/assets/{asset_id}", headers=headers_editor)
    assert response.status_code == 403

    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    response = client.delete(f"/assets/{asset_id}", headers=headers_admin)
    assert response.status_code == 200
