from pydantic import BaseModel


class StudentResponse(BaseModel):
    id: int
    name: str
    student_number: str
    year: int
    department_id: int
    department_name: str | None = None

    model_config = {"from_attributes": True}


class PaginatedStudentResponse(BaseModel):
    total: int
    page: int
    size: int
    items: list[StudentResponse]
