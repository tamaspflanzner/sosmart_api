
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.main import (
    app,
    Base,
    Team,
    User,
    StudyTrip,
    get_db,
    get_current_user,
    get_total_user_points,
    delete_user_account,
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
        team = Team(name="Points Test Team")
        user = User(
            email="points-user@example.com",
            full_name="Points Test User",
            password_hash="test-only",
            is_admin=False,
        )

        db.add_all([team, user])
        db.flush()

        user.team_id = team.id
        db.commit()

        user_id = user.id
        team_id = team.id

    def override_db():
        with Session(engine) as db:
            yield db

    def override_current_user():
        with Session(engine) as db:
            yield db.get(User, user_id)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        client = TestClient(app)
        yield client, engine, user_id, team_id
    finally:
        client.close()
        app.dependency_overrides.clear()
        engine.dispose()

def test_trip_points_are_stored_not_calculated(test_environment):
    client, engine, user_id, team_id = test_environment

    trip_payload = {
        "trip_id": "points-test-trip-001",
        "origin": "Home",
        "destination": "University",
        "transport_mode": "walking",
        "distance_km": 5.0,
        "co2_emission_kg": 0.0,
        "co2_saved_kg": 1.0,
        "points": 120,
    }

    response = client.post("/api/v1/trips", json=trip_payload)

    assert response.status_code == 201, response.text

    trip_data = response.json()

    assert trip_data["total_points"] == 120
    assert trip_data["points"] == 120

    with Session(engine) as db:
        trip = db.scalar(
            select(StudyTrip).where(
                StudyTrip.client_trip_id == "points-test-trip-001"
            )
        )

        assert trip is not None
        assert trip.points == 120
        assert trip.total_points == 120

        assert get_total_user_points(db, user_id) == 120

    points_response = client.get(f"/api/v1/points/{user_id}")

    assert points_response.status_code == 200, points_response.text
    assert points_response.json()["points"] == 120

    team_response = client.get("/api/v1/leaderboard/teams")

    assert team_response.status_code == 200, team_response.text


    team_data = team_response.json()
    team_entries = team_data["entries"]

    assert isinstance(team_entries, list), team_data

    matching_teams = [
        entry for entry in team_entries
        if entry["team_id"] == team_id
    ]



    assert len(matching_teams) == 1, team_entries
    assert matching_teams[0]["points"] == 120


@pytest.mark.parametrize(
    "first_points, second_points",
    [
        (0, 0),
        (10, 25),
        (75, 150),
        (300, 20),
        (1000, 2500),
    ],
)
def test_previous_team_keeps_points_after_user_switches_team(
        test_environment,
        first_points,
        second_points,
):
    client, engine, user_id, team_a_id = test_environment

    with Session(engine) as db:
        team_b = Team(name="Points Test Team B")
        db.add(team_b)
        db.commit()
        team_b_id = team_b.id

    def create_trip(trip_id, points):
        payload = {
            "trip_id": trip_id,
            "origin": "Home",
            "destination": "University",
            "transport_mode": "walking",
            "distance_km": 5.0,
            "co2_emission_kg": 0.0,
            "co2_saved_kg": 1.0,
            "points": points,
        }

        response = client.post("/api/v1/trips", json=payload)
        assert response.status_code == 201, response.text

    # Earn points in Team A.
    create_trip("team-a-trip", first_points)

    # Move the user to Team B.
    with Session(engine) as db:
        user = db.get(User, user_id)
        user.team_id = team_b_id
        db.commit()

    # Earn points in Team B.
    create_trip("team-b-trip", second_points)

    expected_user_points = first_points + second_points

    with Session(engine) as db:
        trips = db.scalars(
            select(StudyTrip)
            .where(StudyTrip.user_id == user_id)
            .order_by(StudyTrip.id)
        ).all()

        assert len(trips) == 2

        assert trips[0].team_id == team_a_id
        assert trips[0].points == first_points

        assert trips[1].team_id == team_b_id
        assert trips[1].points == second_points

        assert get_total_user_points(db, user_id) == expected_user_points

    response = client.get("/api/v1/leaderboard/teams")
    assert response.status_code == 200, response.text

    teams = {
        entry["team_id"]: entry
        for entry in response.json()["entries"]
    }

    assert teams[team_a_id]["points"] == first_points
    assert teams[team_b_id]["points"] == second_points

    response = client.get(f"/api/v1/points/{user_id}")
    assert response.status_code == 200, response.text
    assert response.json()["points"] == expected_user_points

@pytest.mark.parametrize(
    "first_points, second_points",
    [
        (0, 0),
        (10, 25),
        (75, 150),
        (300, 20),
        (1000, 2500),
    ],
)
def test_deleting_user_preserves_team_points(
        test_environment,
        first_points,
        second_points,
):
    client, engine, user_id, team_a_id = test_environment

    # Create another team.
    with Session(engine) as db:
        team_b = Team(name="Deletion Test Team B")
        db.add(team_b)
        db.commit()
        team_b_id = team_b.id

    def create_trip(trip_id, points):
        response = client.post(
            "/api/v1/trips",
            json={
                "trip_id": trip_id,
                "origin": "Home",
                "destination": "University",
                "transport_mode": "walking",
                "distance_km": 5.0,
                "co2_emission_kg": 0.0,
                "co2_saved_kg": 1.0,
                "points": points,
            },
        )
        assert response.status_code == 201, response.text

    # Earn points in Team A.
    create_trip("deletion-team-a-trip", first_points)

    # Switch to Team B.
    with Session(engine) as db:
        user = db.get(User, user_id)
        user.team_id = team_b_id
        db.commit()

    # Earn points in Team B.
    create_trip("deletion-team-b-trip", second_points)

    expected_total = first_points + second_points

    # Delete the user.
    with Session(engine) as db:
        user = db.get(User, user_id)
        assert user is not None

        preserved = delete_user_account(db, user)
        db.commit()

        # All points should have been preserved.
        assert preserved == expected_total

        # User should be deleted.
        assert db.get(User, user_id) is None

        # Trips should be deleted.
        trips = db.scalars(
            select(StudyTrip).where(
                StudyTrip.user_id == user_id
            )
        ).all()

        assert trips == []

        # Each team keeps its own points.
        team_a = db.get(Team, team_a_id)
        team_b = db.get(Team, team_b_id)

        assert team_a.preserved_points == first_points
        assert team_b.preserved_points == second_points

    # Check the leaderboard after deletion.
    response = client.get("/api/v1/leaderboard/teams")
    assert response.status_code == 200, response.text

    teams = {
        entry["team_id"]: entry
        for entry in response.json()["entries"]
    }

    assert teams[team_a_id]["points"] == first_points
    assert teams[team_b_id]["points"] == second_points

@pytest.mark.parametrize(
    "first_points, second_points",
    [
        (0, 0),
        (10, 25),
        (75, 150),
        (300, 20),
        (1000, 2500),
    ],
)
def test_admin_api_preserves_team_points(
        test_environment,
        first_points,
        second_points,
):
    client, engine, user_id, team_a_id = test_environment

    # Create Team B and an admin.
    with Session(engine) as db:
        team_b = Team(name="Admin API Test Team B")

        admin = User(
            email="admin-points-test@example.com",
            full_name="Admin Points Test",
            password_hash="test-only",
            is_admin=True,
        )

        db.add_all([team_b, admin])
        db.commit()

        team_b_id = team_b.id
        admin_id = admin.id

    # The existing fixture authenticates the regular user.
    def regular_user_override():
        with Session(engine) as db:
            yield db.get(User, user_id)

    # Authenticate as admin for admin-only API requests.
    def admin_override():
        with Session(engine) as db:
            yield db.get(User, admin_id)

    def create_trip(trip_id, points):
        app.dependency_overrides[get_current_user] = regular_user_override

        response = client.post(
            "/api/v1/trips",
            json={
                "trip_id": trip_id,
                "origin": "Home",
                "destination": "University",
                "transport_mode": "walking",
                "distance_km": 5.0,
                "co2_emission_kg": 0.0,
                "co2_saved_kg": 1.0,
                "points": points,
            },
        )

        assert response.status_code == 201, response.text

    # User earns points in Team A.
    create_trip("admin-api-team-a-trip", first_points)

    # Admin moves the user to Team B through the real API.
    app.dependency_overrides[get_current_user] = admin_override

    response = client.patch(
        f"/api/v1/users/{user_id}",
        json={"team_id": team_b_id},
    )

    assert response.status_code == 200, response.text
    assert response.json()["team_id"] == team_b_id

    # User earns points in Team B.
    create_trip("admin-api-team-b-trip", second_points)

    expected_total = first_points + second_points

    # Verify the trips and personal points before deletion.
    with Session(engine) as db:
        trips = db.scalars(
            select(StudyTrip)
            .where(StudyTrip.user_id == user_id)
            .order_by(StudyTrip.id)
        ).all()

        assert len(trips) == 2

        assert trips[0].team_id == team_a_id
        assert trips[0].points == first_points

        assert trips[1].team_id == team_b_id
        assert trips[1].points == second_points

        assert get_total_user_points(db, user_id) == expected_total

    # Verify team points before deletion.
    response = client.get("/api/v1/leaderboard/teams")
    assert response.status_code == 200, response.text

    teams = {
        entry["team_id"]: entry
        for entry in response.json()["entries"]
    }

    assert teams[team_a_id]["points"] == first_points
    assert teams[team_b_id]["points"] == second_points

    # Admin deletes the user through the real API.
    app.dependency_overrides[get_current_user] = admin_override

    response = client.delete(
        f"/api/v1/admin/users/{user_id}"
    )

    assert response.status_code == 200, response.text

    # Verify the user and their trips were deleted.
    with Session(engine) as db:
        assert db.get(User, user_id) is None

        remaining_trips = db.scalars(
            select(StudyTrip).where(
                StudyTrip.user_id == user_id
            )
        ).all()

        assert remaining_trips == []

        team_a = db.get(Team, team_a_id)
        team_b = db.get(Team, team_b_id)

        assert team_a.preserved_points == first_points
        assert team_b.preserved_points == second_points

    # Verify the leaderboard still has the original team points.
    response = client.get("/api/v1/leaderboard/teams")
    assert response.status_code == 200, response.text

    teams = {
        entry["team_id"]: entry
        for entry in response.json()["entries"]
    }

    assert teams[team_a_id]["points"] == first_points
    assert teams[team_b_id]["points"] == second_points