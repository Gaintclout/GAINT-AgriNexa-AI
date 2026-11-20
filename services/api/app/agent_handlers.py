"""Deterministic intake and profile processing.

These functions do not query databases, invoke AI models,
write records, or enable agent execution.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IntakeInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    farmer_id: str = Field(min_length=1, max_length=128)
    parcel_id: str = Field(min_length=1, max_length=128)
    crop_name: str | None = Field(default=None, max_length=120)
    season: str | None = Field(default=None, max_length=80)

    @field_validator("farmer_id", "parcel_id")
    @classmethod
    def require_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Identifier cannot be blank")
        return value

    @field_validator("crop_name", "season")
    @classmethod
    def normalize_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class IntakeResult(BaseModel):
    farmer_id: str
    parcel_id: str
    crop_name: str | None
    season: str | None
    status: str = "validated"


class ProfileResult(BaseModel):
    farmer_id: str
    parcel_id: str
    completed_fields: int
    total_fields: int
    completeness_percent: int
    missing_fields: list[str]
    status: str = "incomplete"


def process_intake(data: IntakeInput) -> IntakeResult:
    """Normalize and validate input without persisting it."""
    return IntakeResult(**data.model_dump())


def build_profile(intake: IntakeResult) -> ProfileResult:
    """Calculate completeness; do not infer missing information."""
    fields = {
        "farmer_id": intake.farmer_id,
        "parcel_id": intake.parcel_id,
        "crop_name": intake.crop_name,
        "season": intake.season,
    }

    missing = [
        name for name, value in fields.items()
        if value is None or not str(value).strip()
    ]

    total = len(fields)
    completed = total - len(missing)

    return ProfileResult(
        farmer_id=intake.farmer_id,
        parcel_id=intake.parcel_id,
        completed_fields=completed,
        total_fields=total,
        completeness_percent=round(completed * 100 / total),
        missing_fields=missing,
        status="complete" if not missing else "incomplete",
    )
