from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models.course import Course
from app.models.course_schedule import CourseSchedule
from app.models.enrollment import Enrollment
from app.schemas.course import CourseResponse, PaginatedCourseResponse, ScheduleResponse

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("", response_model=PaginatedCourseResponse)
async def get_courses(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    department_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    # Subquery for enrolled count
    enrolled_subq = (
        select(
            Enrollment.course_id,
            func.count(Enrollment.id).label("enrolled"),
        )
        .group_by(Enrollment.course_id)
        .subquery()
    )

    base_stmt = (
        select(
            Course,
            func.coalesce(enrolled_subq.c.enrolled, 0).label("enrolled"),
        )
        .outerjoin(enrolled_subq, Course.id == enrolled_subq.c.course_id)
        .options(
            joinedload(Course.department),
            joinedload(Course.professor),
            joinedload(Course.schedules),
        )
    )

    if department_id is not None:
        base_stmt = base_stmt.where(Course.department_id == department_id)

    count_stmt = select(func.count(Course.id))
    if department_id is not None:
        count_stmt = count_stmt.where(Course.department_id == department_id)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = base_stmt.order_by(Course.id).offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    rows = result.unique().all()

    return PaginatedCourseResponse(
        total=total,
        page=page,
        size=size,
        items=[
            CourseResponse(
                id=course.id,
                name=course.name,
                code=course.code,
                credits=course.credits,
                capacity=course.capacity,
                enrolled=enrolled,
                department_id=course.department_id,
                department_name=course.department.name,
                professor_id=course.professor_id,
                professor_name=course.professor.name,
                schedules=[
                    ScheduleResponse(
                        day_of_week=s.day_of_week,
                        start_time=s.start_time,
                        end_time=s.end_time,
                    )
                    for s in course.schedules
                ],
            )
            for course, enrolled in rows
        ],
    )
