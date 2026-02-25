"""
Load test via httpx + ASGITransport: FastAPI 전체 스택(미들웨어·인증·Rate Limiter·라우터·서비스·DB)을
실제 TCP/IP 없이 측정한다.

Usage:
    pytest tests/test_load_http.py -v -s
"""

import asyncio
import statistics
import time

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth import create_access_token
from app.database import get_db
from app.main import app
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.rate_limiter import enrollment_rate_limiter
from tests.conftest import TEST_DB_URL, _ensure_db_setup

HTTP_LOAD_RESULTS: list[dict] = []


# ─── helpers ─────────────────────────────────────────────────────────────────

def _reset_rate_limiter() -> None:
    """테스트 간 rate limiter 상태 초기화."""
    enrollment_rate_limiter._requests.clear()
    enrollment_rate_limiter._failures.clear()
    enrollment_rate_limiter._blocked_until.clear()


def _auth_headers(student_id: int) -> dict[str, str]:
    token = create_access_token(student_id)
    return {"Authorization": f"Bearer {token}"}


def _make_override(session_factory):
    """get_db를 테스트 DB로 교체하는 override 함수 반환."""
    async def override_get_db():
        async with session_factory() as session:
            yield session
    return override_get_db


def _stats(latencies: list[float]) -> dict:
    if not latencies:
        return {"avg_latency_ms": 0, "p50_latency_ms": 0,
                "p95_latency_ms": 0, "p99_latency_ms": 0}
    s = sorted(latencies)
    return {
        "avg_latency_ms": round(statistics.mean(s) * 1000, 1),
        "p50_latency_ms": round(statistics.median(s) * 1000, 1),
        "p95_latency_ms": round(s[int(len(s) * 0.95)] * 1000, 1),
        "p99_latency_ms": round(s[int(len(s) * 0.99)] * 1000, 1),
    }


# ─── read scenario ────────────────────────────────────────────────────────────

async def _run_reads_http(session_factory, num_requests: int) -> dict:
    _reset_rate_limiter()
    app.dependency_overrides[get_db] = _make_override(session_factory)

    latencies: list[float] = []
    errors = 0

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        async def do_read():
            nonlocal errors
            t = time.perf_counter()
            try:
                resp = await client.get("/courses")
                if resp.status_code == 200:
                    latencies.append(time.perf_counter() - t)
                else:
                    errors += 1
            except Exception:
                errors += 1

        wall_start = time.perf_counter()
        await asyncio.gather(*[do_read() for _ in range(num_requests)])
        wall_time = time.perf_counter() - wall_start

    app.dependency_overrides.pop(get_db, None)

    return {
        "type": "READ",
        "concurrency": num_requests,
        "total_time_s": round(wall_time, 3),
        "throughput_rps": round(num_requests / wall_time, 1),
        **_stats(latencies),
        "errors": errors,
        "success_rate": round((num_requests - errors) / num_requests * 100, 1),
    }


# ─── write scenario ───────────────────────────────────────────────────────────

async def _run_enrollments_http(session_factory, num_requests: int, capacity: int) -> dict:
    _reset_rate_limiter()

    # 초기화: 수강신청 삭제 + capacity 설정
    async with session_factory() as session:
        await session.execute(delete(Enrollment))
        await session.execute(update(Course).where(Course.id == 1).values(capacity=capacity))
        await session.commit()

    app.dependency_overrides[get_db] = _make_override(session_factory)

    latencies: list[float] = []
    successes = 0
    expected_failures = 0  # 409: 정원초과·중복·학점초과
    unexpected_errors = 0  # 5xx, 연결 에러

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        async def do_enroll(student_id: int):
            nonlocal successes, expected_failures, unexpected_errors
            t = time.perf_counter()
            try:
                resp = await client.post(
                    "/enrollments",
                    json={"student_id": student_id, "course_id": 1},
                    headers=_auth_headers(student_id),
                )
                if resp.status_code == 201:
                    successes += 1
                elif resp.status_code in (400, 409, 422, 429):
                    expected_failures += 1
                else:
                    unexpected_errors += 1
            except Exception:
                unexpected_errors += 1
            latencies.append(time.perf_counter() - t)

        wall_start = time.perf_counter()
        await asyncio.gather(*[do_enroll(i) for i in range(1, num_requests + 1)])
        wall_time = time.perf_counter() - wall_start

    app.dependency_overrides.pop(get_db, None)

    return {
        "type": "WRITE (enrollment)",
        "concurrency": num_requests,
        "capacity": capacity,
        "total_time_s": round(wall_time, 3),
        "throughput_rps": round(num_requests / wall_time, 1),
        **_stats(latencies),
        "successes": successes,
        "expected_failures": expected_failures,
        "unexpected_errors": unexpected_errors,
        "correctness": successes <= capacity,
    }


# ─── tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_http_load_read():
    """READ 처리량: GET /courses, 동시성 10·50·100·200·500."""
    await _ensure_db_setup()
    engine = create_async_engine(
        TEST_DB_URL, pool_size=80, max_overflow=40, isolation_level="READ_COMMITTED"
    )
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        print("\n" + "=" * 70)
        print("HTTP READ LOAD TEST (GET /courses) — httpx + ASGI")
        print("=" * 70)

        for n in [10, 50, 100, 200, 500]:
            r = await _run_reads_http(sf, n)
            HTTP_LOAD_RESULTS.append(r)
            print(
                f"  N={n:>4} | {r['throughput_rps']:>7.1f} rps | "
                f"avg={r['avg_latency_ms']:>6.1f}ms | "
                f"p95={r['p95_latency_ms']:>6.1f}ms | "
                f"p99={r['p99_latency_ms']:>6.1f}ms | "
                f"errors={r['errors']}"
            )

        for r in HTTP_LOAD_RESULTS:
            if r["type"] == "READ":
                assert r["errors"] == 0, f"READ 에러 발생: concurrency={r['concurrency']}"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_http_load_write():
    """WRITE 처리량 + 동시성 정확성: POST /enrollments, capacity=1."""
    await _ensure_db_setup()
    engine = create_async_engine(
        TEST_DB_URL, pool_size=80, max_overflow=40, isolation_level="READ_COMMITTED"
    )
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        print("\n" + "=" * 70)
        print("HTTP WRITE LOAD TEST (POST /enrollments, capacity=1) — httpx + ASGI")
        print("=" * 70)

        for n in [10, 50, 100, 200, 500]:
            r = await _run_enrollments_http(sf, n, capacity=1)
            HTTP_LOAD_RESULTS.append(r)
            print(
                f"  N={n:>4} | {r['throughput_rps']:>7.1f} rps | "
                f"avg={r['avg_latency_ms']:>6.1f}ms | "
                f"p95={r['p95_latency_ms']:>6.1f}ms | "
                f"successes={r['successes']} | "
                f"correct={r['correctness']}"
            )

        for r in HTTP_LOAD_RESULTS:
            if r["type"].startswith("WRITE"):
                assert r["correctness"], (
                    f"정확성 위반: N={r['concurrency']}, successes={r['successes']}, capacity={r['capacity']}"
                )
                assert r["successes"] == 1, (
                    f"정확히 1명만 성공해야 함: successes={r['successes']}"
                )
    finally:
        # 정리
        async with sf() as session:
            await session.execute(delete(Enrollment))
            await session.execute(update(Course).where(Course.id == 1).values(capacity=40))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_http_load_mixed():
    """MIXED 워크로드: 80% READ + 20% WRITE, N=200."""
    await _ensure_db_setup()
    engine = create_async_engine(
        TEST_DB_URL, pool_size=80, max_overflow=40, isolation_level="READ_COMMITTED"
    )
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with sf() as session:
            await session.execute(delete(Enrollment))
            await session.execute(update(Course).where(Course.id == 1).values(capacity=50))
            await session.commit()

        _reset_rate_limiter()
        app.dependency_overrides[get_db] = _make_override(sf)

        print("\n" + "=" * 70)
        print("HTTP MIXED LOAD TEST (80% READ, 20% WRITE, N=200) — httpx + ASGI")
        print("=" * 70)

        num_reads, num_writes = 160, 40
        read_latencies: list[float] = []
        write_latencies: list[float] = []
        read_errors = write_errors = write_successes = write_rejections = 0

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async def do_read():
                nonlocal read_errors
                t = time.perf_counter()
                try:
                    resp = await client.get("/courses")
                    if resp.status_code == 200:
                        read_latencies.append(time.perf_counter() - t)
                    else:
                        read_errors += 1
                except Exception:
                    read_errors += 1

            async def do_write(sid: int):
                nonlocal write_successes, write_rejections, write_errors
                t = time.perf_counter()
                try:
                    resp = await client.post(
                        "/enrollments",
                        json={"student_id": sid, "course_id": 1},
                        headers=_auth_headers(sid),
                    )
                    if resp.status_code == 201:
                        write_successes += 1
                    elif resp.status_code in (400, 409, 422, 429):
                        write_rejections += 1
                    else:
                        write_errors += 1
                except Exception:
                    write_errors += 1
                write_latencies.append(time.perf_counter() - t)

            import random
            tasks = [do_read() for _ in range(num_reads)] + [do_write(i) for i in range(1, num_writes + 1)]
            random.shuffle(tasks)

            wall_start = time.perf_counter()
            await asyncio.gather(*tasks)
            wall_time = time.perf_counter() - wall_start

        app.dependency_overrides.pop(get_db, None)

        r = {
            "type": "MIXED",
            "total_time_s": round(wall_time, 3),
            "throughput_rps": round(200 / wall_time, 1),
            "read_avg_ms": round(statistics.mean(read_latencies) * 1000, 1) if read_latencies else 0,
            "write_avg_ms": round(statistics.mean(write_latencies) * 1000, 1) if write_latencies else 0,
            "read_errors": read_errors,
            "write_successes": write_successes,
            "write_rejections": write_rejections,
            "write_errors": write_errors,
        }
        HTTP_LOAD_RESULTS.append(r)

        print(f"  Total: 200 req in {wall_time:.3f}s ({200/wall_time:.1f} rps)")
        print(f"  Reads:  avg={r['read_avg_ms']:.1f}ms, errors={read_errors}")
        print(f"  Writes: avg={r['write_avg_ms']:.1f}ms, successes={write_successes}, "
              f"rejections={write_rejections}, errors={write_errors}")

        assert read_errors == 0
        assert write_errors == 0
        assert write_successes <= 50

    finally:
        async with sf() as session:
            await session.execute(delete(Enrollment))
            await session.execute(update(Course).where(Course.id == 1).values(capacity=40))
            await session.commit()
        await engine.dispose()
