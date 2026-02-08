from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_student
from app.database import get_db
from app.models.student import Student
from app.rate_limiter import enrollment_rate_limiter
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

    Anti-macro protections applied:
    - Rate limit: max 5 requests per 10 seconds per student
    - Minimum interval: 1 second between consecutive requests
    - Failure penalty: 10 consecutive failures → 30 second block
    """
    if request.student_id != current_student.id:
        raise HTTPException(
            status_code=403,
            detail="Cannot register on behalf of another student",
        )

    # Anti-macro: check rate limit
    allowed, reason = await enrollment_rate_limiter.check(current_student.id)
    if not allowed:
        raise HTTPException(status_code=429, detail=reason)

    try:
        enrollment = await enrollment_service.register(
            student_id=current_student.id,
            course_id=request.course_id,
            db=db,
        )
    except HTTPException:
        await enrollment_rate_limiter.record_failure(current_student.id)
        raise

    await enrollment_rate_limiter.record_success(current_student.id)
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
