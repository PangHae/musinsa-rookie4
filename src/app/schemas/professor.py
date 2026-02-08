from pydantic import BaseModel


class ProfessorResponse(BaseModel):
    id: int
    name: str
    employee_number: str
    department_id: int
    department_name: str | None = None

    model_config = {"from_attributes": True}
