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
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, create_engine, func, select
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
    other = "other"


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


engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

app = FastAPI(
    title="SoSmart API",
    description="API service for shared SoSmart ecosystem data and statistics.",
    version="1.0.0",
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


class TripCreateRequest(BaseModel):
    origin: str = Field(min_length=1, max_length=255)
    destination: str = Field(min_length=1, max_length=255)
    transport_mode: TransportMode
    distance_km: float = Field(gt=0)
    co2_saved_kg: float = Field(ge=0)
    trip_time: datetime | None = None


class TripResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    trip_time: datetime
    origin: str
    destination: str
    transport_mode: str
    distance_km: float
    co2_saved_kg: float
    created_at: datetime


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


def parse_date_filters(from_date: date | None, to_date: date | None) -> tuple[datetime | None, datetime | None]:
    start = None
    end = None
    if from_date:
        start = datetime.combine(from_date, datetime.min.time(), tzinfo=timezone.utc)
    if to_date:
        end = datetime.combine(to_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    return start, end


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
    user_count = db.execute(select(func.count(User.id))).scalar_one()
    if user_count > 0:
        return

    admin = User(
        email=DEMO_ADMIN_EMAIL,
        full_name="Demo Admin",
        password_hash=get_password_hash(DEMO_ADMIN_PASSWORD),
        is_admin=True,
    )
    user = User(
        email=DEMO_USER_EMAIL,
        full_name="Demo User",
        password_hash=get_password_hash(DEMO_USER_PASSWORD),
        is_admin=False,
    )
    db.add_all([admin, user])
    db.flush()

    now = datetime.now(timezone.utc)
    demo_trips = [
        Trip(
            user_id=user.id,
            trip_time=now - timedelta(days=1),
            origin="District 5",
            destination="Central Station",
            transport_mode=TransportMode.bus.value,
            distance_km=12.5,
            co2_saved_kg=1.8,
        ),
        Trip(
            user_id=user.id,
            trip_time=now - timedelta(days=2),
            origin="Central Station",
            destination="Office Park",
            transport_mode=TransportMode.bicycle.value,
            distance_km=7.2,
            co2_saved_kg=1.1,
        ),
        Trip(
            user_id=admin.id,
            trip_time=now - timedelta(days=3),
            origin="Suburb A",
            destination="Downtown",
            transport_mode=TransportMode.train.value,
            distance_km=21.0,
            co2_saved_kg=3.2,
        ),
    ]
    db.add_all(demo_trips)
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


@app.post("/api/v1/trips", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
def create_trip(
    payload: TripCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Trip:
    trip_time = payload.trip_time.astimezone(timezone.utc) if payload.trip_time else datetime.now(timezone.utc)
    trip = Trip(
        user_id=current_user.id,
        trip_time=trip_time,
        origin=payload.origin,
        destination=payload.destination,
        transport_mode=payload.transport_mode.value,
        distance_km=payload.distance_km,
        co2_saved_kg=payload.co2_saved_kg,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


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
