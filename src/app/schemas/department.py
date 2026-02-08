from pydantic import BaseModel


class DepartmentResponse(BaseModel):
    id: int
    name: str
    code: str

    model_config = {"from_attributes": True}
