from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token
from app.database import get_db
from app.models.student import Student
from app.schemas.auth import LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate a student by student_number and return a JWT token."""
    result = await db.execute(
        select(Student).where(Student.student_number == request.student_number)
    )
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=401, detail="Invalid student number")

    token = create_access_token(student.id)
    return LoginResponse(
        access_token=token,
        student_id=student.id,
        student_name=student.name,
    )
