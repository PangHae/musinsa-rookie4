import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_departments(client: AsyncClient):
    response = await client.get("/departments")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 15


@pytest.mark.asyncio
async def test_get_professors(client: AsyncClient):
    response = await client.get("/professors")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 100


@pytest.mark.asyncio
async def test_get_professors_by_department(client: AsyncClient):
    response = await client.get("/professors?department_id=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(p["department_id"] == 1 for p in data)


@pytest.mark.asyncio
async def test_get_courses(client: AsyncClient):
    response = await client.get("/courses")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 500
    # Verify course structure
    course = data[0]
    assert "enrolled" in course
    assert "schedules" in course
    assert "capacity" in course


@pytest.mark.asyncio
async def test_get_courses_by_department(client: AsyncClient):
    response = await client.get("/courses?department_id=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert all(c["department_id"] == 1 for c in data)


@pytest.mark.asyncio
async def test_get_students_paginated(client: AsyncClient):
    response = await client.get("/students?page=1&size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 10000
    assert data["page"] == 1
    assert data["size"] == 10
    assert len(data["items"]) == 10


@pytest.mark.asyncio
async def test_get_students_by_department(client: AsyncClient):
    response = await client.get("/students?department_id=1&size=5")
    assert response.status_code == 200
    data = response.json()
    assert all(s["department_id"] == 1 for s in data["items"])
