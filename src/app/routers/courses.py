from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models.course import Course
from app.models.course_schedule import CourseSchedule
from app.models.enrollment import Enrollment
from app.schemas.course import CourseResponse, ScheduleResponse

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("", response_model=list[CourseResponse])
async def get_courses(
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

    stmt = (
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
        stmt = stmt.where(Course.department_id == department_id)

    stmt = stmt.order_by(Course.id)
    result = await db.execute(stmt)
    rows = result.unique().all()

    return [
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
    ]
