from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.course import ScheduleResponse


class EnrollmentRequest(BaseModel):
    student_id: int = Field(..., gt=0)
    course_id: int = Field(..., gt=0)


class EnrollmentResponse(BaseModel):
    id: int
    student_id: int
    course_id: int
    course_name: str | None = None
    registered_at: datetime

    model_config = {"from_attributes": True}


class TimetableEntry(BaseModel):
    enrollment_id: int
    course_id: int
    course_name: str
    course_code: str
    credits: int
    professor_name: str
    schedules: list[ScheduleResponse] = []


class TimetableResponse(BaseModel):
    student_id: int
    student_name: str
    total_credits: int
    courses: list[TimetableEntry]
