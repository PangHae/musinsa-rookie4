import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.database import AsyncSessionLocal, engine
from app.models import Base
from app.routers import auth, courses, departments, enrollments, health, professors, students
from app.seed import seed_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables only
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Shutdown: dispose engine
    await engine.dispose()


class SeedMiddleware(BaseHTTPMiddleware):
    """Middleware that seeds initial data if the database is empty.

    On the first request, checks if data exists. If not, runs seed_database().
    Subsequent requests skip the check entirely. Idempotent and thread-safe.
    The seeding must complete within 1 minute (required by spec).
    """

    def __init__(self, app):
        super().__init__(app)
        self._seeded = False
        self._lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next):
        if not self._seeded:
            async with self._lock:
                if not self._seeded:
                    async with AsyncSessionLocal() as session:
                        await seed_database(session)
                    self._seeded = True
        return await call_next(request)


app = FastAPI(
    title="수강신청 시스템",
    description="대학교 수강신청 REST API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(SeedMiddleware)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(departments.router)
app.include_router(professors.router)
app.include_router(courses.router)
app.include_router(students.router)
app.include_router(enrollments.router)
