import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.geography_validation import validate_village_hierarchy
from app.models import State, District, Mandal

@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    State.__table__.create(engine)
    District.__table__.create(engine)
    Mandal.__table__.create(engine)
    with Session(engine) as session:
        session.add(State(code="TG", name="Telangana"))
        session.add_all([
            District(code="D1", name="District One", state_code="TG"),
            District(code="D2", name="District Two", state_code="TG")
        ])
        session.add(Mandal(code="M1", name="Mandal One", district_code="D1"))
        session.commit()
        yield session
    engine.dispose()

def test_valid_village_hierarchy(db):
    validate_village_hierarchy(db, "D1", "M1")
    validate_village_hierarchy(db, "D2", None)

@pytest.mark.parametrize("district,mandal", [
    ("D2", "M1"),
    ("D1", "MISSING"),
    ("MISSING", None)
])
def test_invalid_village_hierarchy(db, district, mandal):
    with pytest.raises(HTTPException) as exc:
        validate_village_hierarchy(db, district, mandal)
    assert exc.value.status_code == 422
