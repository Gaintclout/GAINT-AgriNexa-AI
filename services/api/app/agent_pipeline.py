"""Internal read-only INTAKE/PROFILE pipeline.

No model invocation, persistence, or agent activation.
"""

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from .agent_data_access import load_parcel_context
from .agent_handlers import (
    IntakeInput,
    IntakeResult,
    ProfileResult,
    build_profile,
    process_intake,
)
from .security import Principal


class PipelineRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    parcel_id: str = Field(min_length=1, max_length=36)
    crop_name: str | None = Field(default=None, max_length=120)
    season: str | None = Field(default=None, max_length=80)


class PipelineResult(BaseModel):
    intake: IntakeResult
    profile: ProfileResult
    village_code: str
    area_hectares: str
    data_source: str = "parcel_registry"
    persisted: bool = False
    correlation_id: str | None = None


def prepare_parcel_profile(
    db: Session,
    principal: Principal,
    request: PipelineRequest,
) -> PipelineResult:
    """Resolve ownership before processing intake metadata."""

    context = load_parcel_context(
        db,
        principal,
        request.parcel_id,
    )

    intake = process_intake(
        IntakeInput(
            farmer_id=context.farmer_id,
            parcel_id=context.parcel_id,
            crop_name=request.crop_name,
            season=request.season,
        )
    )

    return PipelineResult(
        intake=intake,
        profile=build_profile(intake),
        village_code=context.village_code,
        area_hectares=str(context.area_hectares),
    )
