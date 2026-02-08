from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models.course import Course
from app.models.course_schedule import CourseSchedule
from app.models.enrollment import Enrollment
from app.models.student import Student
from app.schemas.course import ScheduleResponse
from app.schemas.enrollment import TimetableEntry, TimetableResponse
from app.schemas.student import PaginatedStudentResponse, StudentResponse

router = APIRouter(prefix="/students", tags=["students"])


@router.get("", response_model=PaginatedStudentResponse)
async def get_students(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    department_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    # Count query
    count_stmt = select(func.count(Student.id))
    if department_id is not None:
        count_stmt = count_stmt.where(Student.department_id == department_id)
    total = (await db.execute(count_stmt)).scalar_one()

    # Data query
    stmt = select(Student).options(joinedload(Student.department))
    if department_id is not None:
        stmt = stmt.where(Student.department_id == department_id)
    stmt = stmt.order_by(Student.id).offset((page - 1) * size).limit(size)

    result = await db.execute(stmt)
    students = result.scalars().unique().all()

    return PaginatedStudentResponse(
        total=total,
        page=page,
        size=size,
        items=[
            StudentResponse(
                id=s.id,
                name=s.name,
                student_number=s.student_number,
                year=s.year,
                department_id=s.department_id,
                department_name=s.department.name,
            )
            for s in students
        ],
    )


@router.get("/{student_id}/timetable", response_model=TimetableResponse)
async def get_timetable(
    student_id: int,
    db: AsyncSession = Depends(get_db),
):
    # Verify student exists
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Get enrollments with course and professor info
    stmt = (
        select(Enrollment)
        .where(Enrollment.student_id == student_id)
        .options(
            joinedload(Enrollment.course).joinedload(Course.professor),
            joinedload(Enrollment.course).joinedload(Course.schedules),
        )
        .order_by(Enrollment.id)
    )
    result = await db.execute(stmt)
    enrollments = result.scalars().unique().all()

    total_credits = 0
    courses = []
    for enrollment in enrollments:
        course = enrollment.course
        total_credits += course.credits
        courses.append(
            TimetableEntry(
                enrollment_id=enrollment.id,
                course_id=course.id,
                course_name=course.name,
                course_code=course.code,
                credits=course.credits,
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
        )

    return TimetableResponse(
        student_id=student.id,
        student_name=student.name,
        total_credits=total_credits,
        courses=courses,
    )
