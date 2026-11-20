"""Sprint 1 persistent schema. Database migration is intentionally not automatic."""
from datetime import datetime, timezone
from uuid import uuid4
from geoalchemy2 import Geometry
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

def uid() -> str:
    return str(uuid4())

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

class State(Base):
    __tablename__ = "states"
    code: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

class District(Base):
    __tablename__ = "districts"
    code: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    state_code: Mapped[str] = mapped_column(ForeignKey("states.code"), nullable=False, index=True)

class Mandal(Base):
    __tablename__ = "mandals"
    code: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    district_code: Mapped[str] = mapped_column(ForeignKey("districts.code"), nullable=False, index=True)

class Village(Base):
    __tablename__ = "villages"
    code: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    district_code: Mapped[str] = mapped_column(String(100), nullable=False)
    mandal_code: Mapped[str | None] = mapped_column(ForeignKey("mandals.code", name="fk_villages_mandal"), nullable=True, index=True)

class Parcel(Base):
    __tablename__ = "parcels"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    external_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    village_code: Mapped[str] = mapped_column(ForeignKey("villages.code"), nullable=False)
    farmer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    area_hectares: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    geom: Mapped[str | None] = mapped_column(Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    __table_args__ = (CheckConstraint("area_hectares > 0", name="ck_parcels_positive_area"),)
