from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_student
from app.database import get_db
from app.models.student import Student
from app.schemas.enrollment import EnrollmentRequest, EnrollmentResponse
from app.services import enrollment_service

router = APIRouter(prefix="/enrollments", tags=["enrollments"])


@router.post("", response_model=EnrollmentResponse, status_code=201)
async def register_course(
    request: EnrollmentRequest,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Register for a course. Requires JWT authentication.

    The student_id is extracted from the JWT token, so a student can only
    register for themselves — not on behalf of another student.
    """
    if request.student_id != current_student.id:
        raise HTTPException(
            status_code=403,
            detail="Cannot register on behalf of another student",
        )

    enrollment = await enrollment_service.register(
        student_id=current_student.id,
        course_id=request.course_id,
        db=db,
    )
    return EnrollmentResponse(
        id=enrollment.id,
        student_id=enrollment.student_id,
        course_id=enrollment.course_id,
        course_name=getattr(enrollment, "course_name", None),
        registered_at=enrollment.registered_at,
    )


@router.delete("/{enrollment_id}", status_code=204)
async def cancel_enrollment(
    enrollment_id: int,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an enrollment. Only the owning student can cancel."""
    await enrollment_service.cancel(
        enrollment_id=enrollment_id,
        student_id=current_student.id,
        db=db,
    )
    return Response(status_code=204)
