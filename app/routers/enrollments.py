from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.enrollment import EnrollmentRequest, EnrollmentResponse
from app.services import enrollment_service

router = APIRouter(prefix="/enrollments", tags=["enrollments"])


@router.post("", response_model=EnrollmentResponse, status_code=201)
async def register_course(
    request: EnrollmentRequest,
    db: AsyncSession = Depends(get_db),
):
    enrollment = await enrollment_service.register(
        student_id=request.student_id,
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
    db: AsyncSession = Depends(get_db),
):
    await enrollment_service.cancel(enrollment_id=enrollment_id, db=db)
    return Response(status_code=204)
