from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.course_schedule import CourseSchedule
from app.models.enrollment import Enrollment
from app.models.student import Student


async def register(student_id: int, course_id: int, db: AsyncSession) -> Enrollment:
    """
    Register a student for a course using pessimistic locking.

    Transaction flow:
    1. Validate student exists
    2. SELECT ... FOR UPDATE on the course row (locks it)
    3. Check capacity (count enrollments vs capacity)
    4. Check duplicate enrollment
    5. Check credit limit (total enrolled credits + course credits <= 18)
    6. Check schedule conflicts
    7. INSERT enrollment
    8. COMMIT (releases lock)
    """
    # 1. Validate student
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # 2. Lock the course row with FOR UPDATE
    # This serializes concurrent registration attempts for the same course.
    # Once a transaction acquires this lock, all other transactions trying
    # to register for the same course must wait until the lock is released.
    stmt = select(Course).where(Course.id == course_id).with_for_update()
    result = await db.execute(stmt)
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # 3. Check capacity
    enrolled_count = (
        await db.execute(
            select(func.count(Enrollment.id)).where(
                Enrollment.course_id == course_id
            )
        )
    ).scalar_one()

    if enrolled_count >= course.capacity:
        raise HTTPException(status_code=409, detail="Course is full")

    # 4. Check duplicate enrollment
    existing = (
        await db.execute(
            select(Enrollment.id).where(
                Enrollment.student_id == student_id,
                Enrollment.course_id == course_id,
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        raise HTTPException(
            status_code=409, detail="Already enrolled in this course"
        )

    # 5. Check credit limit
    current_credits = (
        await db.execute(
            select(func.coalesce(func.sum(Course.credits), 0)).where(
                Course.id.in_(
                    select(Enrollment.course_id).where(
                        Enrollment.student_id == student_id
                    )
                )
            )
        )
    ).scalar_one()

    if current_credits + course.credits > 18:
        raise HTTPException(
            status_code=409,
            detail=f"Credit limit exceeded (current: {current_credits}, "
            f"attempting: {course.credits}, max: 18)",
        )

    # 6. Check schedule conflicts
    # Get schedules of the target course
    target_schedules = (
        await db.execute(
            select(CourseSchedule).where(CourseSchedule.course_id == course_id)
        )
    ).scalars().all()

    # Get schedules of currently enrolled courses
    enrolled_course_ids = select(Enrollment.course_id).where(
        Enrollment.student_id == student_id
    )
    enrolled_schedules = (
        await db.execute(
            select(CourseSchedule).where(
                CourseSchedule.course_id.in_(enrolled_course_ids)
            )
        )
    ).scalars().all()

    for target in target_schedules:
        for enrolled in enrolled_schedules:
            if target.day_of_week == enrolled.day_of_week:
                # Check time overlap
                if target.start_time < enrolled.end_time and target.end_time > enrolled.start_time:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Schedule conflict on {target.day_of_week} "
                        f"({target.start_time}-{target.end_time})",
                    )

    # 7. Insert enrollment
    enrollment = Enrollment(student_id=student_id, course_id=course_id)
    db.add(enrollment)
    await db.commit()
    await db.refresh(enrollment)

    # Attach course name for response
    enrollment.course_name = course.name

    return enrollment


async def cancel(enrollment_id: int, db: AsyncSession) -> None:
    """Cancel an enrollment by deleting it."""
    enrollment = await db.get(Enrollment, enrollment_id)
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    await db.delete(enrollment)
    await db.commit()
