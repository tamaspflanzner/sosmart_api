
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.main import (
    app, Base, Team, User,
    get_db, get_current_user,
    MAX_TEAM_MEMBERS,
)


@pytest.fixture
def test_environment():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        team = Team(name="Capacity Test Team")
        admin = User(
            email="capacity-admin@example.com",
            full_name="Capacity Admin",
            password_hash="test-only",
            is_admin=True,
        )

        users = [
            User(
                email=f"capacity-user-{i}@example.com",
                full_name=f"Capacity User {i}",
                password_hash="test-only",
                is_admin=False,
            )
            for i in range(1, 42)
        ]

        db.add_all([team, admin, *users])
        db.commit()

        team_id = team.id
        user_ids = [user.id for user in users]
        admin_id = admin.id

    def override_db():
        with Session(engine) as db:
            yield db

    def override_current_user():
        with Session(engine) as db:
            yield db.get(User, admin_id)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        client = TestClient(app)
        yield client, engine, team_id, user_ids
    finally:
        client.close()
        app.dependency_overrides.clear()
        engine.dispose()


def test_exactly_40_members_allowed_and_41st_rejected(test_environment):
    client, engine, team_id, user_ids = test_environment

    assert MAX_TEAM_MEMBERS == 40

    for index, user_id in enumerate(user_ids[:40], start=1):
        response = client.patch(
            f"/api/v1/users/{user_id}",
            json={"team_id": team_id},
        )
        assert response.status_code == 200, (
            f"Member {index} failed: "
            f"{response.status_code} {response.text}"
        )

    with Session(engine) as db:
        count = db.scalar(
            select(func.count(User.id)).where(User.team_id == team_id)
        )
        assert count == 40

    print("\nPASS: Exactly 40 members accepted")

    response = client.patch(
        f"/api/v1/users/{user_ids[40]}",
        json={"team_id": team_id},
    )

    assert response.status_code == 400, response.text
    assert "full" in response.json()["detail"].lower()

    with Session(engine) as db:
        count = db.scalar(
            select(func.count(User.id)).where(User.team_id == team_id)
        )
        assert count == 40

    print("PASS: 41st member rejected")
    print("PASS: Team still has exactly 40 members")


def test_remove_and_replace_member(test_environment):
    client, engine, team_id, user_ids = test_environment

    for user_id in user_ids[:40]:
        response = client.patch(
            f"/api/v1/users/{user_id}",
            json={"team_id": team_id},
        )
        assert response.status_code == 200, response.text

    response = client.patch(
        f"/api/v1/users/{user_ids[0]}",
        json={"team_id": None},
    )
    assert response.status_code == 200, response.text

    with Session(engine) as db:
        count = db.scalar(
            select(func.count(User.id)).where(User.team_id == team_id)
        )
        assert count == 39

    response = client.patch(
        f"/api/v1/users/{user_ids[40]}",
        json={"team_id": team_id},
    )
    assert response.status_code == 200, response.text

    with Session(engine) as db:
        count = db.scalar(
            select(func.count(User.id)).where(User.team_id == team_id)
        )
        assert count == 40

    print("\nPASS: Member removed and replacement accepted")
