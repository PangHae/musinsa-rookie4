from pydantic import BaseModel


class ScheduleResponse(BaseModel):
    day_of_week: str
    start_time: str
    end_time: str

    model_config = {"from_attributes": True}


class CourseResponse(BaseModel):
    id: int
    name: str
    code: str
    credits: int
    capacity: int
    enrolled: int
    department_id: int
    department_name: str | None = None
    professor_id: int
    professor_name: str | None = None
    schedules: list[ScheduleResponse] = []

    model_config = {"from_attributes": True}
