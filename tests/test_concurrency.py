"""
Concurrency test: 100 simultaneous registration requests for a course with capacity=1.
Exactly 1 must succeed, 99 must fail.

Uses direct service calls with separate DB sessions to simulate true concurrent
database transactions, bypassing the serial nature of ASGI test transport.
"""

import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.course import Course
from app.models.enrollment import Enrollment
from app.services import enrollment_service
from tests.conftest import TEST_DB_URL, _ensure_db_setup


async def test_concurrent_registration():
    """100 students register for a course with capacity=1 simultaneously.

    Directly calls the enrollment service with separate DB sessions
    to test the pessimistic locking mechanism under real concurrency.
    """
    await _ensure_db_setup()

    engine = create_async_engine(
        TEST_DB_URL, pool_size=50, max_overflow=60, isolation_level="READ_COMMITTED"
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        # Setup: set course 1 capacity to 1 and clear enrollments
        async with session_factory() as session:
            await session.execute(delete(Enrollment))
            await session.execute(update(Course).where(Course.id == 1).values(capacity=1))
            await session.commit()

        num_requests = 100
        success_count = 0
        failure_count = 0
        lock = asyncio.Lock()

        async def try_register(student_id: int):
            nonlocal success_count, failure_count
            async with session_factory() as session:
                try:
                    await enrollment_service.register(
                        student_id=student_id,
                        course_id=1,
                        db=session,
                    )
                    async with lock:
                        success_count += 1
                except HTTPException as e:
                    if e.status_code == 409:
                        async with lock:
                            failure_count += 1
                    else:
                        raise

        # Fire 100 concurrent registrations (students 1-100)
        tasks = [try_register(i) for i in range(1, num_requests + 1)]
        await asyncio.gather(*tasks)

        assert success_count == 1, (
            f"Expected exactly 1 success, got {success_count}"
        )
        assert failure_count == num_requests - 1

        # Verify in DB: exactly 1 enrollment for course 1
        async with session_factory() as session:
            result = await session.execute(
                select(Enrollment.id).where(Enrollment.course_id == 1)
            )
            enrollment_ids = result.scalars().all()
            assert len(enrollment_ids) == 1

    finally:
        # Cleanup
        async with session_factory() as session:
            await session.execute(delete(Enrollment))
            await session.execute(update(Course).where(Course.id == 1).values(capacity=40))
            await session.commit()
        await engine.dispose()
