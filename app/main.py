import os
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://app_user:app_password@db:5432/sosmart_demo",
)
SECRET_KEY = os.getenv("SECRET_KEY", "demo-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))
AUTO_CREATE_SCHEMA = os.getenv("AUTO_CREATE_SCHEMA", "true").lower() == "true"
ENABLE_DEMO_SEED = os.getenv("ENABLE_DEMO_SEED", "false").lower() == "true"
CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "*")

DEMO_ADMIN_EMAIL = os.getenv("DEMO_ADMIN_EMAIL", "admin@example.com")
DEMO_ADMIN_PASSWORD = os.getenv("DEMO_ADMIN_PASSWORD", "admin123")
DEMO_USER_EMAIL = os.getenv("DEMO_USER_EMAIL", "user@example.com")
DEMO_USER_PASSWORD = os.getenv("DEMO_USER_PASSWORD", "user123")


class Base(DeclarativeBase):
    pass


class TransportMode(str, Enum):
    walking = "walking"
    bicycle = "bicycle"
    bus = "bus"
    car = "car"
    tram = "tram"
    train = "train"
    scooter = "scooter"
    e_bike = "e_bike"
    metro = "metro"
    motorcycle = "motorcycle"
    other = "other"


class ShisaRole(str, Enum):
    user = "user"
    shisa = "shisa"


CO2_EMISSION_FACTORS_KG_PER_KM: dict[TransportMode, float] = {
    TransportMode.walking: 0.0,
    TransportMode.bicycle: 0.0,
    TransportMode.bus: 0.082,
    TransportMode.car: 0.192,
    TransportMode.tram: 0.045,
    TransportMode.train: 0.041,
    TransportMode.scooter: 0.022,
    TransportMode.e_bike: 0.006,
    TransportMode.metro: 0.050,
    TransportMode.motorcycle: 0.103,
    TransportMode.other: 0.080,
}

POINTS_PER_KM: dict[TransportMode, float] = {
    TransportMode.walking: 9.0,
    TransportMode.bicycle: 9.0,
    TransportMode.bus: 6.0,
    TransportMode.car: 0.0,
    TransportMode.tram: 6.0,
    TransportMode.train: 6.0,
    TransportMode.scooter: 4.0,
    TransportMode.e_bike: 6.0,
    TransportMode.metro: 6.0,
    TransportMode.motorcycle: 0.0,
    TransportMode.other: 0.0,
}

LEGACY_TRANSPORT_MODE_MAP: dict[TransportMode, str] = {
    TransportMode.walking: "walking",
    TransportMode.bicycle: "bicycle",
    TransportMode.bus: "bus",
    TransportMode.car: "car",
    TransportMode.tram: "tram",
    TransportMode.train: "train",
    TransportMode.scooter: "scooter",
    TransportMode.e_bike: "bicycle",
    TransportMode.metro: "train",
    TransportMode.motorcycle: "car",
    TransportMode.other: "other",
}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    trips: Mapped[list["Trip"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    study_trips: Mapped[list["StudyTrip"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    shisa_messages: Mapped[list["ShisaMessage"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    trip_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    origin: Mapped[str] = mapped_column(String(255), nullable=False)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    transport_mode: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    co2_saved_kg: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="trips")


class StudyTrip(Base):
    __tablename__ = "study_trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_trip_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    purpose: Mapped[str | None] = mapped_column(String(100), nullable=True)
    begin_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    travel_time_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    total_co2_emission_kg: Mapped[float] = mapped_column(Float, nullable=False)
    total_co2_saved_kg: Mapped[float] = mapped_column(Float, nullable=False)
    total_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="study_trips")
    legs: Mapped[list["StudyTripLeg"]] = relationship(
        back_populates="study_trip",
        cascade="all, delete-orphan",
        order_by="StudyTripLeg.sequence_no",
    )


class StudyTripLeg(Base):
    __tablename__ = "study_trip_legs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    study_trip_id: Mapped[int] = mapped_column(Integer, ForeignKey("study_trips.id"), nullable=False, index=True)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    transport_mode: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    origin: Mapped[str] = mapped_column(String(255), nullable=False)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    co2_emission_kg: Mapped[float] = mapped_column(Float, nullable=False)
    co2_saved_kg: Mapped[float] = mapped_column(Float, nullable=False)
    points_awarded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    begin_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    travel_time_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    study_trip: Mapped[StudyTrip] = relationship(back_populates="legs")


class ShisaMessage(Base):
    __tablename__ = "shisa_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    user: Mapped[User] = relationship(back_populates="shisa_messages")


engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

app = FastAPI(
    title="SoSmart API",
    description="API service for shared SoSmart ecosystem data and statistics.",
    version="1.1.0",
)

allow_origins = ["*"] if CORS_ALLOWED_ORIGINS == "*" else [origin.strip() for origin in CORS_ALLOWED_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    is_admin: bool
    created_at: datetime


class TripLegInput(BaseModel):
    origin: str = Field(min_length=1, max_length=255)
    destination: str = Field(min_length=1, max_length=255)
    transport_mode: TransportMode
    distance_km: float = Field(gt=0)
    co2_emission_kg: float = Field(ge=0)
    co2_saved_kg: float = Field(ge=0)
    begin_time: datetime | None = None
    end_time: datetime | None = None
    travel_time_seconds: int | None = Field(default=None, ge=0)


class TripCreateRequest(BaseModel):
    trip_id: str | None = Field(default=None, max_length=255)
    purpose: str | None = Field(default=None, max_length=100)
    begin_time: datetime | None = None
    end_time: datetime | None = None
    travel_time_seconds: int | None = Field(default=None, ge=0)
    legs: list[TripLegInput] | None = None

    origin: str | None = Field(default=None, min_length=1, max_length=255)
    destination: str | None = Field(default=None, min_length=1, max_length=255)
    transport_mode: TransportMode | None = None
    distance_km: float | None = Field(default=None, gt=0)
    co2_emission_kg: float | None = Field(default=None, ge=0)
    co2_saved_kg: float | None = Field(default=None, ge=0)
    trip_time: datetime | None = None


class TripLegResponse(BaseModel):
    sequence_no: int
    transport_mode: str
    origin: str
    destination: str
    distance_km: float
    co2_emission_kg: float
    co2_saved_kg: float
    points_awarded: int
    begin_time: datetime
    end_time: datetime
    travel_time_seconds: int


class TripHistoryItemResponse(BaseModel):
    id: int | str
    client_trip_id: str | None = None
    user_id: int
    purpose: str | None = None
    begin_time: datetime
    end_time: datetime
    travel_time_seconds: int
    total_distance_km: float
    total_co2_emission_kg: float
    total_co2_saved_kg: float
    total_points: int
    legs: list[TripLegResponse]


class ShisaChatRequest(BaseModel):
    user_id: int | None = None
    conversation_id: str = Field(min_length=1, max_length=255)
    role: ShisaRole
    content: str = Field(min_length=1)
    create_time: datetime | None = None


class ShisaChatResponse(BaseModel):
    id: int
    user_id: int
    conversation_id: str
    role: str
    content: str
    create_time: datetime


class ModeAggregation(BaseModel):
    transport_mode: str
    total_distance_km: float
    trip_count: int


class StatsResponse(BaseModel):
    total_trip_count: int
    total_distance_km: float
    total_co2_saved_kg: float
    by_transport_mode: list[ModeAggregation]


class DailyGlobalStatsItem(BaseModel):
    day: date
    total_trip_count: int
    total_distance_km: float
    total_co2_saved_kg: float


class DailyGlobalStatsResponse(BaseModel):
    days: list[DailyGlobalStatsItem]


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.get(User, int(user_id))
    if user is None:
        raise credentials_exception
    return user


def ensure_user_access(target_user_id: int, current_user: User) -> None:
    if current_user.is_admin or current_user.id == target_user_id:
        return
    raise HTTPException(status_code=403, detail="You are not allowed to access this user's data.")


def parse_date_filters(from_date: date | None, to_date: date | None) -> tuple[datetime | None, datetime | None]:
    start = None
    end = None
    if from_date:
        start = datetime.combine(from_date, datetime.min.time(), tzinfo=timezone.utc)
    if to_date:
        end = datetime.combine(to_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    return start, end


def to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def calculate_co2_saved_kg(mode: TransportMode, distance_km: float) -> float:
    car_factor = CO2_EMISSION_FACTORS_KG_PER_KM[TransportMode.car]
    mode_factor = CO2_EMISSION_FACTORS_KG_PER_KM[mode]
    return round(max(car_factor - mode_factor, 0.0) * distance_km, 3)


def calculate_points(mode: TransportMode, distance_km: float) -> int:
    return int(round(distance_km * POINTS_PER_KM[mode]))


def normalize_legacy_transport_mode(mode: TransportMode) -> str:
    return LEGACY_TRANSPORT_MODE_MAP[mode]


def build_leg_dicts(payload: TripCreateRequest) -> list[dict[str, Any]]:
    if payload.legs:
        leg_dicts: list[dict[str, Any]] = []
        for sequence_no, leg in enumerate(payload.legs, start=1):
            begin_time = to_utc(leg.begin_time)
            end_time = to_utc(leg.end_time)
            if begin_time and end_time:
                travel_time_seconds = int((end_time - begin_time).total_seconds())
            else:
                travel_time_seconds = leg.travel_time_seconds or 0
                if begin_time is None:
                    begin_time = to_utc(payload.begin_time) or datetime.now(timezone.utc)
                if end_time is None:
                    end_time = begin_time + timedelta(seconds=travel_time_seconds)

            leg_dicts.append(
                {
                    "sequence_no": sequence_no,
                    "origin": leg.origin,
                    "destination": leg.destination,
                    "transport_mode": leg.transport_mode,
                    "distance_km": float(leg.distance_km),
                    "co2_emission_kg": float(leg.co2_emission_kg),
                    "co2_saved_kg": float(leg.co2_saved_kg),
                    "begin_time": begin_time,
                    "end_time": end_time,
                    "travel_time_seconds": travel_time_seconds,
                }
            )
        return leg_dicts

    if not all(
        [
            payload.origin,
            payload.destination,
            payload.transport_mode,
            payload.distance_km,
            payload.co2_emission_kg is not None,
            payload.co2_saved_kg is not None,
        ]
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Provide either 'legs' or the legacy single-leg fields origin, destination, "
                "transport_mode, distance_km, co2_emission_kg, and co2_saved_kg."
            ),
        )

    begin_time = to_utc(payload.trip_time or payload.begin_time) or datetime.now(timezone.utc)
    if payload.end_time:
        end_time = to_utc(payload.end_time) or begin_time
    elif payload.travel_time_seconds is not None:
        end_time = begin_time + timedelta(seconds=payload.travel_time_seconds)
    else:
        end_time = begin_time

    travel_time_seconds = (
        payload.travel_time_seconds
        if payload.travel_time_seconds is not None
        else int((end_time - begin_time).total_seconds())
    )

    return [
        {
            "sequence_no": 1,
            "origin": payload.origin,
            "destination": payload.destination,
            "transport_mode": payload.transport_mode,
            "distance_km": float(payload.distance_km),
            "co2_emission_kg": float(payload.co2_emission_kg),
            "co2_saved_kg": float(payload.co2_saved_kg),
            "begin_time": begin_time,
            "end_time": end_time,
            "travel_time_seconds": max(travel_time_seconds, 0),
        }
    ]


def serialize_study_trip(study_trip: StudyTrip) -> TripHistoryItemResponse:
    return TripHistoryItemResponse(
        id=study_trip.id,
        client_trip_id=study_trip.client_trip_id,
        user_id=study_trip.user_id,
        purpose=study_trip.purpose,
        begin_time=study_trip.begin_time,
        end_time=study_trip.end_time,
        travel_time_seconds=study_trip.travel_time_seconds,
        total_distance_km=round(study_trip.total_distance_km, 3),
        total_co2_emission_kg=round(study_trip.total_co2_emission_kg, 3),
        total_co2_saved_kg=round(study_trip.total_co2_saved_kg, 3),
        total_points=study_trip.total_points,
        legs=[
            TripLegResponse(
                sequence_no=leg.sequence_no,
                transport_mode=leg.transport_mode,
                origin=leg.origin,
                destination=leg.destination,
                distance_km=round(leg.distance_km, 3),
                co2_emission_kg=round(leg.co2_emission_kg, 3),
                co2_saved_kg=round(leg.co2_saved_kg, 3),
                points_awarded=leg.points_awarded,
                begin_time=leg.begin_time,
                end_time=leg.end_time,
                travel_time_seconds=leg.travel_time_seconds,
            )
            for leg in study_trip.legs
        ],
    )


def serialize_legacy_trip(trip: Trip) -> TripHistoryItemResponse:
    emission_factor = CO2_EMISSION_FACTORS_KG_PER_KM.get(TransportMode(trip.transport_mode), 0.0)
    total_emission = round(trip.distance_km * emission_factor, 3)
    return TripHistoryItemResponse(
        id=f"legacy-{trip.id}",
        client_trip_id=None,
        user_id=trip.user_id,
        purpose=None,
        begin_time=trip.trip_time,
        end_time=trip.trip_time,
        travel_time_seconds=0,
        total_distance_km=round(trip.distance_km, 3),
        total_co2_emission_kg=total_emission,
        total_co2_saved_kg=round(trip.co2_saved_kg, 3),
        total_points=calculate_points(TransportMode(trip.transport_mode), trip.distance_km),
        legs=[
            TripLegResponse(
                sequence_no=1,
                transport_mode=trip.transport_mode,
                origin=trip.origin,
                destination=trip.destination,
                distance_km=round(trip.distance_km, 3),
                co2_emission_kg=total_emission,
                co2_saved_kg=round(trip.co2_saved_kg, 3),
                points_awarded=calculate_points(TransportMode(trip.transport_mode), trip.distance_km),
                begin_time=trip.trip_time,
                end_time=trip.trip_time,
                travel_time_seconds=0,
            )
        ],
    )


def query_study_trips(
    db: Session,
    user_id: int,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[StudyTrip]:
    stmt = select(StudyTrip).where(StudyTrip.user_id == user_id)
    if start is not None:
        stmt = stmt.where(StudyTrip.begin_time >= start)
    if end is not None:
        stmt = stmt.where(StudyTrip.begin_time < end)
    stmt = stmt.order_by(StudyTrip.begin_time.desc(), StudyTrip.id.desc())
    return list(db.scalars(stmt).all())


def query_legacy_trips(
    db: Session,
    user_id: int,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[Trip]:
    stmt = select(Trip).where(Trip.user_id == user_id)
    if start is not None:
        stmt = stmt.where(Trip.trip_time >= start)
    if end is not None:
        stmt = stmt.where(Trip.trip_time < end)
    stmt = stmt.order_by(Trip.trip_time.desc(), Trip.id.desc())
    return list(db.scalars(stmt).all())


def get_trip_history_items(
    db: Session,
    user_id: int,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[TripHistoryItemResponse]:
    study_trips = query_study_trips(db, user_id, start=start, end=end)
    if study_trips:
        return [serialize_study_trip(trip) for trip in study_trips]
    return [serialize_legacy_trip(trip) for trip in query_legacy_trips(db, user_id, start=start, end=end)]


def get_history_window_from_scope(scope: str) -> tuple[datetime | None, datetime | None]:
    now = datetime.now(timezone.utc)
    if scope == "all":
        return None, None
    if scope == "today":
        start = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)
        return start, None
    if scope.isdigit():
        days = int(scope)
        if days <= 0:
            raise HTTPException(status_code=400, detail="Days must be a positive integer.")
        return now - timedelta(days=days), None
    raise HTTPException(status_code=400, detail="Scope must be one of: all, today, or a positive integer day count.")


def serialize_shisa_message(message: ShisaMessage) -> ShisaChatResponse:
    return ShisaChatResponse(
        id=message.id,
        user_id=message.user_id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        create_time=message.created_at,
    )


def calculate_stats(
    db: Session,
    user_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> StatsResponse:
    start, end = parse_date_filters(from_date, to_date)

    filters = []
    if user_id is not None:
        filters.append(Trip.user_id == user_id)
    if start is not None:
        filters.append(Trip.trip_time >= start)
    if end is not None:
        filters.append(Trip.trip_time < end)

    totals_stmt = select(
        func.count(Trip.id),
        func.coalesce(func.sum(Trip.distance_km), 0.0),
        func.coalesce(func.sum(Trip.co2_saved_kg), 0.0),
    )
    if filters:
        totals_stmt = totals_stmt.where(*filters)
    total_trip_count, total_distance_km, total_co2_saved_kg = db.execute(totals_stmt).one()

    mode_stmt = select(
        Trip.transport_mode,
        func.coalesce(func.sum(Trip.distance_km), 0.0),
        func.count(Trip.id),
    ).group_by(Trip.transport_mode)
    if filters:
        mode_stmt = mode_stmt.where(*filters)
    mode_stmt = mode_stmt.order_by(Trip.transport_mode.asc())

    by_mode = [
        ModeAggregation(
            transport_mode=transport_mode,
            total_distance_km=float(distance),
            trip_count=count,
        )
        for transport_mode, distance, count in db.execute(mode_stmt).all()
    ]

    return StatsResponse(
        total_trip_count=total_trip_count,
        total_distance_km=float(total_distance_km),
        total_co2_saved_kg=float(total_co2_saved_kg),
        by_transport_mode=by_mode,
    )


def calculate_daily_global_stats(
    db: Session,
    from_date: date | None = None,
    to_date: date | None = None,
) -> DailyGlobalStatsResponse:
    start, end = parse_date_filters(from_date, to_date)

    day_expr = func.date(Trip.trip_time)
    stmt = select(
        day_expr,
        func.count(Trip.id),
        func.coalesce(func.sum(Trip.distance_km), 0.0),
        func.coalesce(func.sum(Trip.co2_saved_kg), 0.0),
    ).group_by(day_expr)

    if start is not None:
        stmt = stmt.where(Trip.trip_time >= start)
    if end is not None:
        stmt = stmt.where(Trip.trip_time < end)

    stmt = stmt.order_by(day_expr.desc())
    rows = db.execute(stmt).all()

    return DailyGlobalStatsResponse(
        days=[
            DailyGlobalStatsItem(
                day=day_value,
                total_trip_count=trip_count,
                total_distance_km=float(total_distance),
                total_co2_saved_kg=float(total_co2),
            )
            for day_value, trip_count, total_distance, total_co2 in rows
        ]
    )


def seed_demo_data(db: Session) -> None:
    admin = db.execute(select(User).where(User.email == DEMO_ADMIN_EMAIL)).scalar_one_or_none()
    if admin is None:
        admin = User(
            email=DEMO_ADMIN_EMAIL,
            full_name="Demo Admin",
            password_hash=get_password_hash(DEMO_ADMIN_PASSWORD),
            is_admin=True,
        )
        db.add(admin)
        db.flush()
    else:
        admin.full_name = "Demo Admin"
        admin.password_hash = get_password_hash(DEMO_ADMIN_PASSWORD)
        admin.is_admin = True

    user = db.execute(select(User).where(User.email == DEMO_USER_EMAIL)).scalar_one_or_none()
    if user is None:
        user = User(
            email=DEMO_USER_EMAIL,
            full_name="Demo User",
            password_hash=get_password_hash(DEMO_USER_PASSWORD),
            is_admin=False,
        )
        db.add(user)
        db.flush()
    else:
        user.full_name = "Demo User"
        user.password_hash = get_password_hash(DEMO_USER_PASSWORD)
        user.is_admin = False

    now = datetime.now(timezone.utc)
    demo_trips = [
        Trip(
            user_id=user.id,
            trip_time=now - timedelta(days=1),
            origin="District 5",
            destination="Central Station",
            transport_mode=LEGACY_TRANSPORT_MODE_MAP[TransportMode.bus],
            distance_km=12.5,
            co2_saved_kg=calculate_co2_saved_kg(TransportMode.bus, 12.5),
        ),
        Trip(
            user_id=user.id,
            trip_time=now - timedelta(days=2),
            origin="Central Station",
            destination="Office Park",
            transport_mode=LEGACY_TRANSPORT_MODE_MAP[TransportMode.bicycle],
            distance_km=7.2,
            co2_saved_kg=calculate_co2_saved_kg(TransportMode.bicycle, 7.2),
        ),
        Trip(
            user_id=admin.id,
            trip_time=now - timedelta(days=3),
            origin="Suburb A",
            destination="Downtown",
            transport_mode=LEGACY_TRANSPORT_MODE_MAP[TransportMode.train],
            distance_km=21.0,
            co2_saved_kg=calculate_co2_saved_kg(TransportMode.train, 21.0),
        ),
    ]
    for demo_trip in demo_trips:
        trip_exists = db.execute(
            select(Trip.id).where(
                Trip.user_id == demo_trip.user_id,
                Trip.origin == demo_trip.origin,
                Trip.destination == demo_trip.destination,
                Trip.transport_mode == demo_trip.transport_mode,
                Trip.distance_km == demo_trip.distance_km,
            )
        ).scalar_one_or_none()
        if trip_exists is None:
            db.add(demo_trip)

    db.commit()


@app.on_event("startup")
def on_startup() -> None:
    if AUTO_CREATE_SCHEMA:
        Base.metadata.create_all(bind=engine)
    if ENABLE_DEMO_SEED:
        with SessionLocal() as db:
            seed_demo_data(db)


@app.get("/api/v1/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered.")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=get_password_hash(payload.password),
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/api/v1/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_access_token({"sub": str(user.id), "email": user.email, "is_admin": user.is_admin})
    return TokenResponse(access_token=token)


@app.get("/api/v1/users/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@app.post("/api/v1/trips", response_model=TripHistoryItemResponse, status_code=status.HTTP_201_CREATED)
def create_trip(
    payload: TripCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TripHistoryItemResponse:
    leg_dicts = build_leg_dicts(payload)

    total_distance_km = 0.0
    total_co2_emission_kg = 0.0
    total_co2_saved_kg = 0.0
    total_points = 0

    for leg_dict in leg_dicts:
        mode = leg_dict["transport_mode"]
        distance_km = leg_dict["distance_km"]
        leg_dict["points_awarded"] = calculate_points(mode, distance_km)
        total_distance_km += distance_km
        total_co2_emission_kg += leg_dict["co2_emission_kg"]
        total_co2_saved_kg += leg_dict["co2_saved_kg"]
        total_points += leg_dict["points_awarded"]

    begin_time = min(leg["begin_time"] for leg in leg_dicts)
    end_time = max(leg["end_time"] for leg in leg_dicts)
    travel_time_seconds = max(int((end_time - begin_time).total_seconds()), 0)

    study_trip = StudyTrip(
        client_trip_id=payload.trip_id,
        user_id=current_user.id,
        purpose=payload.purpose,
        begin_time=begin_time,
        end_time=end_time,
        travel_time_seconds=travel_time_seconds,
        total_distance_km=round(total_distance_km, 3),
        total_co2_emission_kg=round(total_co2_emission_kg, 3),
        total_co2_saved_kg=round(total_co2_saved_kg, 3),
        total_points=total_points,
    )
    db.add(study_trip)
    db.flush()

    for leg_dict in leg_dicts:
        leg = StudyTripLeg(
            study_trip_id=study_trip.id,
            sequence_no=leg_dict["sequence_no"],
            transport_mode=leg_dict["transport_mode"].value,
            origin=leg_dict["origin"],
            destination=leg_dict["destination"],
            distance_km=leg_dict["distance_km"],
            co2_emission_kg=leg_dict["co2_emission_kg"],
            co2_saved_kg=leg_dict["co2_saved_kg"],
            points_awarded=leg_dict["points_awarded"],
            begin_time=leg_dict["begin_time"],
            end_time=leg_dict["end_time"],
            travel_time_seconds=leg_dict["travel_time_seconds"],
        )
        db.add(leg)

        legacy_trip = Trip(
            user_id=current_user.id,
            trip_time=leg_dict["begin_time"],
            origin=leg_dict["origin"],
            destination=leg_dict["destination"],
            transport_mode=normalize_legacy_transport_mode(leg_dict["transport_mode"]),
            distance_km=leg_dict["distance_km"],
            co2_saved_kg=leg_dict["co2_saved_kg"],
        )
        db.add(legacy_trip)

    db.commit()
    db.refresh(study_trip)
    _ = study_trip.legs
    return serialize_study_trip(study_trip)


@app.get("/api/v1/trip_history/{user_id}", response_model=list[TripHistoryItemResponse])
def get_trip_history(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TripHistoryItemResponse]:
    ensure_user_access(user_id, current_user)
    return get_trip_history_items(db, user_id)


@app.get("/api/v1/trip_history/{user_id}/{scope}")
def get_trip_history_by_scope(
    user_id: int,
    scope: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TripHistoryItemResponse | list[TripHistoryItemResponse]:
    ensure_user_access(user_id, current_user)

    if scope == "latest":
        items = get_trip_history_items(db, user_id)
        if not items:
            raise HTTPException(status_code=404, detail="No trips found for this user.")
        return items[0]

    if scope != "today":
        raise HTTPException(status_code=400, detail="Scope must be one of: today, latest.")

    start = datetime.combine(datetime.now(timezone.utc).date(), datetime.min.time(), tzinfo=timezone.utc)
    return get_trip_history_items(db, user_id, start=start)


@app.post("/api/v1/shisa_chat", response_model=ShisaChatResponse, status_code=status.HTTP_201_CREATED)
def create_shisa_chat_message(
    payload: ShisaChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShisaChatResponse:
    target_user_id = payload.user_id if payload.user_id is not None else current_user.id
    ensure_user_access(target_user_id, current_user)

    message = ShisaMessage(
        user_id=target_user_id,
        conversation_id=payload.conversation_id,
        role=payload.role.value,
        content=payload.content,
        created_at=to_utc(payload.create_time) or datetime.now(timezone.utc),
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return serialize_shisa_message(message)


@app.get("/api/v1/shisa_chat/{user_id}", response_model=list[ShisaChatResponse])
def get_shisa_chat_messages(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ShisaChatResponse]:
    ensure_user_access(user_id, current_user)
    stmt = select(ShisaMessage).where(ShisaMessage.user_id == user_id).order_by(ShisaMessage.created_at.asc())
    return [serialize_shisa_message(message) for message in db.scalars(stmt).all()]


@app.get("/api/v1/shisa_chat/{user_id}/{scope}", response_model=list[ShisaChatResponse])
def get_shisa_chat_messages_by_scope(
    user_id: int,
    scope: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ShisaChatResponse]:
    ensure_user_access(user_id, current_user)
    start, end = get_history_window_from_scope(scope)

    stmt = select(ShisaMessage).where(ShisaMessage.user_id == user_id)
    if start is not None:
        stmt = stmt.where(ShisaMessage.created_at >= start)
    if end is not None:
        stmt = stmt.where(ShisaMessage.created_at < end)
    stmt = stmt.order_by(ShisaMessage.created_at.asc())
    return [serialize_shisa_message(message) for message in db.scalars(stmt).all()]


@app.get("/api/v1/stats/global", response_model=StatsResponse)
def get_global_stats(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
) -> StatsResponse:
    return calculate_stats(db, user_id=None, from_date=from_date, to_date=to_date)


@app.get("/api/v1/stats/public/daily", response_model=DailyGlobalStatsResponse)
def get_public_daily_stats(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
) -> DailyGlobalStatsResponse:
    return calculate_daily_global_stats(db, from_date=from_date, to_date=to_date)


@app.get("/api/v1/stats/me", response_model=StatsResponse)
def get_my_stats(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StatsResponse:
    return calculate_stats(db, user_id=current_user.id, from_date=from_date, to_date=to_date)
