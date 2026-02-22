from pydantic import BaseModel


class ProfessorResponse(BaseModel):
    id: int
    name: str
    employee_number: str
    department_id: int
    department_name: str

    model_config = {"from_attributes": True}


class PaginatedProfessorResponse(BaseModel):
    total: int
    page: int
    size: int
    items: list[ProfessorResponse]
