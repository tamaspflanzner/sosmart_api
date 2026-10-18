"""Point-accounting regression tests. Run: pytest -q tests/test_points_logic.py"""
from datetime import datetime, timedelta, timezone
from itertools import count
from uuid import uuid4
import random
from fastapi import Depends

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.main import (
    Base, StudyTrip, Team, User, app, assign_user_to_team,
    build_team_leaderboard_entries, delete_user_account, get_current_user,
    get_db, get_total_user_points,
)


def amount():
    return random.SystemRandom().randrange(1, 1_000_000)


@pytest.fixture
def env():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    serial = count()

    def make_user(admin=False):
        with Session(engine) as db:
            user = User(email=f'{uuid4()}@example.com', full_name='Test User', password_hash='unused', is_admin=admin)
            db.add(user)
            db.commit()
            return user.id

    def make_team():
        with Session(engine) as db:
            team = Team(name=f'Team-{uuid4()}')
            db.add(team)
            db.commit()
            return team.id

    user_id = make_user()
    admin_id = make_user(admin=True)
    active_user = [user_id]

    def override_db():
        with Session(engine) as db:
            yield db

    def override_user(db: Session = Depends(get_db)):
        return db.get(User, active_user[0])




    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    client = TestClient(app)

    def trip(points, mode='walking'):
        i = next(serial)
        start = datetime.now(timezone.utc) + timedelta(minutes=i)
        response = client.post('/api/v1/trips', json={
            'trip_id': str(uuid4()), 'points': points, 'purpose': 'Study',
            'legs': [{'origin': 'A', 'destination': 'B', 'transport_mode': mode,
                      'distance_km': 1.5, 'co2_emission_kg': 0.0, 'co2_saved_kg': 0.1,
                      'begin_time': start.isoformat(),
                      'end_time': (start + timedelta(minutes=1)).isoformat()}],
        })
        assert response.status_code == 201, response.text
        assert response.json()['points'] == points
        return response.json()['id']

    def switch(team_id, admin=False):
        active_user[0] = admin_id if admin else user_id
        try:
            endpoint = f'/api/v1/users/{user_id}' if admin else '/api/v1/users/me'
            response = client.patch(endpoint, json={'team_id': team_id})
            assert response.status_code == 200, response.text
        finally:
            active_user[0] = user_id

    def leaderboard():
        with Session(engine) as db:
            return {entry.team_id: entry.points for entry in build_team_leaderboard_entries(db)}

    yield {'engine': engine, 'client': client, 'user': user_id, 'admin': admin_id,
           'team': make_team, 'trip': trip, 'switch': switch, 'leaderboard': leaderboard}
    client.close()
    app.dependency_overrides.clear()
    engine.dispose()


def test_empty_account_has_no_points(env):
    with Session(env['engine']) as db:
        assert get_total_user_points(db, env['user']) == 0
    response = env['client'].get(f"/api/v1/points/{env['user']}")
    assert response.status_code == 200
    assert response.json()['points'] == 0


@pytest.mark.parametrize('mode', ['walking', 'bus', 'bicycle', 'train', 'car'])
def test_submitted_points_are_not_recalculated_from_transport(env, mode):
    points = amount()
    trip_id = env['trip'](points, mode)
    with Session(env['engine']) as db:
        trip = db.get(StudyTrip, trip_id)
        assert trip.points == points
        assert trip.total_points == points
        assert trip.team_id is None
        assert get_total_user_points(db, env['user']) == points


def test_first_team_gets_pre_join_points_and_personal_total_stays_same(env):
    values = [amount() for _ in range(3)]

    ids = [
        env["trip"](value, mode)
        for value, mode in zip(
            values,
            ["walking", "bus", "bicycle"]
        )
    ]

    team = env["team"]()

    with Session(env["engine"]) as db:
        points_before = get_total_user_points(
            db, env["user"]
        )

        assert points_before == sum(values)

        for trip_id in ids:
            assert db.get(StudyTrip, trip_id).team_id is None

    assert env["leaderboard"]()[team] == 0

    env["switch"](team)

    with Session(env["engine"]) as db:
        user = db.get(User, env["user"])

        assert user.has_joined_team is True
        assert user.team_id == team

        for trip_id in ids:
            assert db.get(StudyTrip, trip_id).team_id == team

        assert get_total_user_points(
            db, env["user"]
        ) == points_before

    assert env["leaderboard"]()[team] == sum(values)

def test_team_switch_preserves_old_team_and_credits_new_trips_to_new_team(env):
    team_a = env["team"]()
    team_b = env["team"]()

    first, second, third = amount(), amount(), amount()

    pre_join_trip = env["trip"](first)

    env["switch"](team_a)

    team_a_trip = env["trip"](second, "bus")

    with Session(env["engine"]) as db:
        points_before_switch = get_total_user_points(
            db, env["user"]
        )

    assert points_before_switch == first + second
    assert env["leaderboard"]()[team_a] == first + second
    assert env["leaderboard"]()[team_b] == 0

    # Admin transfers user from Team A to Team B
    env["switch"](team_b, admin=True)

    with Session(env["engine"]) as db:
        assert db.get(StudyTrip, pre_join_trip).team_id == team_a
        assert db.get(StudyTrip, team_a_trip).team_id == team_a

        assert get_total_user_points(
            db, env["user"]
        ) == points_before_switch

    assert env["leaderboard"]()[team_a] == first + second
    assert env["leaderboard"]()[team_b] == 0

    # A new trip is credited to Team B
    team_b_trip = env["trip"](third, "bicycle")

    with Session(env["engine"]) as db:
        assert db.get(StudyTrip, team_b_trip).team_id == team_b

        assert get_total_user_points(
            db, env["user"]
        ) == first + second + third

    scores = env["leaderboard"]()

    assert scores[team_a] == first + second
    assert scores[team_b] == third


def test_reassigning_same_team_does_not_double_count(env):
    team = env['team']()
    points = amount()
    env['trip'](points)
    env['switch'](team)
    env['switch'](team, admin=True)
    assert env['leaderboard']()[team] == points


def test_null_points_falls_back_to_total_points(env):
    team = env['team']()
    env['switch'](team)
    expected = amount()
    trip_id = env['trip'](amount())
    with Session(env['engine']) as db:
        trip = db.get(StudyTrip, trip_id)
        trip.points = None
        trip.total_points = expected
        db.commit()
        assert get_total_user_points(db, env['user']) == expected
    assert env['leaderboard']()[team] == expected


def test_deletion_preserves_each_teams_points_without_double_count(env):
    team_a, team_b = env['team'](), env['team']()
    first, second = amount(), amount()
    env['switch'](team_a)
    env['trip'](first)
    env['switch'](team_b, admin=True)
    env['trip'](second)
    with Session(env['engine']) as db:
        user = db.get(User, env['user'])
        assert delete_user_account(db, user) == first + second
        db.commit()
        assert db.get(User, env['user']) is None
        assert db.scalars(select(StudyTrip).where(StudyTrip.user_id == env['user'])).all() == []
        assert db.get(Team, team_a).preserved_points == first
        assert db.get(Team, team_b).preserved_points == second
    scores = env['leaderboard']()
    assert scores[team_a] == first
    assert scores[team_b] == second


def test_previously_unassigned_points_must_not_transfer_on_second_team_join(env):
    """Regression: first-team-only rule, including trips made while between teams."""
    team_a, team_b = env['team'](), env['team']()
    initial = amount()
    between_teams = amount()
    env['trip'](initial)
    env['switch'](team_a)
    env['switch'](None, admin=True)
    later_trip = env['trip'](between_teams)
    env['switch'](team_b, admin=True)
    with Session(env['engine']) as db:
        assert db.get(StudyTrip, later_trip).team_id is None
        assert get_total_user_points(db, env['user']) == initial + between_teams
    scores = env['leaderboard']()
    assert scores[team_a] == initial
    assert scores[team_b] == 0


def test_regular_user_cannot_switch_directly_between_teams(env):
    team_a = env["team"]()
    team_b = env["team"]()

    env["switch"](team_a)

    response = env["client"].patch(
        "/api/v1/users/me",
        json={"team_id": team_b},
    )

    assert response.status_code == 403

    with Session(env["engine"]) as db:
        user = db.get(User, env["user"])
        assert user.team_id == team_a