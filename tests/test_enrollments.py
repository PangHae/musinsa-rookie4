import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enrollment import Enrollment
from app.rate_limiter import enrollment_rate_limiter
from tests.conftest import auth_headers


@pytest_asyncio.fixture(autouse=True)
async def clean_enrollments(db: AsyncSession):
    """Clean enrollments and disable rate limiter during tests."""
    await db.execute(delete(Enrollment))
    await db.commit()

    # Disable rate limiter for functional tests
    orig_min_interval = enrollment_rate_limiter.min_interval_seconds
    orig_max_requests = enrollment_rate_limiter.max_requests
    enrollment_rate_limiter.min_interval_seconds = 0
    enrollment_rate_limiter.max_requests = 1000
    enrollment_rate_limiter._requests.clear()
    enrollment_rate_limiter._failures.clear()
    enrollment_rate_limiter._blocked_until.clear()

    yield

    # Restore original settings
    enrollment_rate_limiter.min_interval_seconds = orig_min_interval
    enrollment_rate_limiter.max_requests = orig_max_requests
    await db.execute(delete(Enrollment))
    await db.commit()


@pytest.mark.asyncio
async def test_register_course(client: AsyncClient):
    response = await client.post(
        "/enrollments",
        json={"student_id": 1, "course_id": 1},
        headers=auth_headers(1),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["student_id"] == 1
    assert data["course_id"] == 1
    assert "id" in data
    assert "registered_at" in data


@pytest.mark.asyncio
async def test_register_without_auth(client: AsyncClient):
    """Registration without JWT should be rejected."""
    response = await client.post(
        "/enrollments", json={"student_id": 1, "course_id": 1}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_register_for_another_student(client: AsyncClient):
    """Cannot register on behalf of another student."""
    response = await client.post(
        "/enrollments",
        json={"student_id": 2, "course_id": 1},
        headers=auth_headers(1),  # logged in as student 1
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_register_duplicate(client: AsyncClient):
    # First registration should succeed
    resp1 = await client.post(
        "/enrollments",
        json={"student_id": 1, "course_id": 1},
        headers=auth_headers(1),
    )
    assert resp1.status_code == 201

    # Duplicate should fail
    resp2 = await client.post(
        "/enrollments",
        json={"student_id": 1, "course_id": 1},
        headers=auth_headers(1),
    )
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_register_student_not_found(client: AsyncClient):
    response = await client.post(
        "/enrollments",
        json={"student_id": 999999, "course_id": 1},
        headers=auth_headers(999999),
    )
    assert response.status_code == 401  # JWT valid but student doesn't exist


@pytest.mark.asyncio
async def test_register_course_not_found(client: AsyncClient):
    response = await client.post(
        "/enrollments",
        json={"student_id": 1, "course_id": 999999},
        headers=auth_headers(1),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_enrollment(client: AsyncClient):
    # Register first
    resp = await client.post(
        "/enrollments",
        json={"student_id": 1, "course_id": 1},
        headers=auth_headers(1),
    )
    assert resp.status_code == 201
    enrollment_id = resp.json()["id"]

    # Cancel
    resp2 = await client.delete(
        f"/enrollments/{enrollment_id}",
        headers=auth_headers(1),
    )
    assert resp2.status_code == 204


@pytest.mark.asyncio
async def test_cancel_not_found(client: AsyncClient):
    response = await client.delete(
        "/enrollments/999999",
        headers=auth_headers(1),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_another_students_enrollment(client: AsyncClient):
    """Cannot cancel another student's enrollment."""
    # Student 1 registers
    resp = await client.post(
        "/enrollments",
        json={"student_id": 1, "course_id": 1},
        headers=auth_headers(1),
    )
    assert resp.status_code == 201
    enrollment_id = resp.json()["id"]

    # Student 2 tries to cancel student 1's enrollment
    resp2 = await client.delete(
        f"/enrollments/{enrollment_id}",
        headers=auth_headers(2),
    )
    assert resp2.status_code == 403


@pytest.mark.asyncio
async def test_timetable(client: AsyncClient):
    # Register for a course
    resp = await client.post(
        "/enrollments",
        json={"student_id": 1, "course_id": 1},
        headers=auth_headers(1),
    )
    assert resp.status_code == 201

    # Get timetable
    resp2 = await client.get("/students/1/timetable")
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["student_id"] == 1
    assert data["total_credits"] > 0
    assert len(data["courses"]) == 1


@pytest.mark.asyncio
async def test_timetable_student_not_found(client: AsyncClient):
    response = await client.get("/students/999999/timetable")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_credit_limit_exceeded(client: AsyncClient, db: AsyncSession):
    """Registering for courses exceeding 18 credits should fail."""
    from sqlalchemy import select, update
    from app.models.course import Course

    # Find courses and temporarily set their credits to values that will exceed 18
    await db.execute(update(Course).where(Course.id == 1).values(credits=10))
    await db.execute(update(Course).where(Course.id == 2).values(credits=10))
    await db.commit()

    try:
        # First registration: 10 credits — should succeed
        resp1 = await client.post(
            "/enrollments",
            json={"student_id": 1, "course_id": 1},
            headers=auth_headers(1),
        )
        assert resp1.status_code == 201

        # Second registration: 10 + 10 = 20 > 18 — should fail
        resp2 = await client.post(
            "/enrollments",
            json={"student_id": 1, "course_id": 2},
            headers=auth_headers(1),
        )
        assert resp2.status_code == 409
        assert "Credit limit exceeded" in resp2.json()["detail"]
    finally:
        # Restore original credit values
        await db.execute(update(Course).where(Course.id == 1).values(credits=3))
        await db.execute(update(Course).where(Course.id == 2).values(credits=3))
        await db.commit()
