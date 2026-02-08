from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    student_number: str = Field(..., examples=["S00001"])


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    student_id: int
    student_name: str
