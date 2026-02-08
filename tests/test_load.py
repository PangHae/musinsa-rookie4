"""
Load test: measures server throughput and latency under concurrent load.

Tests both read (GET /courses) and write (POST /enrollments) endpoints
at various concurrency levels to find the server's breaking point.

Usage:
    pytest tests/test_load.py -v -s

This test runs against the test database using ASGI transport (no real HTTP),
so it measures application-level performance without network overhead.
"""

import asyncio
import statistics
import time

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth import create_access_token
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.services import enrollment_service
from tests.conftest import TEST_DB_URL, _ensure_db_setup

# Results accumulator for report generation
LOAD_TEST_RESULTS: list[dict] = []


async def _run_concurrent_reads(session_factory, num_requests: int) -> dict:
    """Fire N concurrent course list queries and measure latency."""
    latencies = []
    errors = 0

    async def do_read():
        nonlocal errors
        start = time.perf_counter()
        try:
            async with session_factory() as session:
                result = await session.execute(
                    select(Course).order_by(Course.id).limit(50)
                )
                _ = result.scalars().all()
            latencies.append(time.perf_counter() - start)
        except Exception:
            errors += 1

    tasks = [do_read() for _ in range(num_requests)]
    wall_start = time.perf_counter()
    await asyncio.gather(*tasks)
    wall_time = time.perf_counter() - wall_start

    return {
        "type": "READ",
        "concurrency": num_requests,
        "total_time_s": round(wall_time, 3),
        "throughput_rps": round(num_requests / wall_time, 1),
        "avg_latency_ms": round(statistics.mean(latencies) * 1000, 1) if latencies else 0,
        "p50_latency_ms": round(statistics.median(latencies) * 1000, 1) if latencies else 0,
        "p95_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.95)] * 1000, 1) if latencies else 0,
        "p99_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.99)] * 1000, 1) if latencies else 0,
        "errors": errors,
        "success_rate": round((num_requests - errors) / num_requests * 100, 1),
    }


async def _run_concurrent_enrollments(session_factory, num_requests: int, capacity: int) -> dict:
    """Fire N concurrent enrollment requests for a course with given capacity."""
    latencies = []
    successes = 0
    expected_failures = 0
    unexpected_errors = 0

    async def do_enroll(student_id: int):
        nonlocal successes, expected_failures, unexpected_errors
        start = time.perf_counter()
        try:
            async with session_factory() as session:
                await enrollment_service.register(
                    student_id=student_id,
                    course_id=1,
                    db=session,
                )
                successes += 1
        except HTTPException:
            expected_failures += 1
        except Exception:
            unexpected_errors += 1
        latencies.append(time.perf_counter() - start)

    tasks = [do_enroll(i) for i in range(1, num_requests + 1)]
    wall_start = time.perf_counter()
    await asyncio.gather(*tasks)
    wall_time = time.perf_counter() - wall_start

    return {
        "type": "WRITE (enrollment)",
        "concurrency": num_requests,
        "capacity": capacity,
        "total_time_s": round(wall_time, 3),
        "throughput_rps": round(num_requests / wall_time, 1),
        "avg_latency_ms": round(statistics.mean(latencies) * 1000, 1) if latencies else 0,
        "p50_latency_ms": round(statistics.median(latencies) * 1000, 1) if latencies else 0,
        "p95_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.95)] * 1000, 1) if latencies else 0,
        "p99_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.99)] * 1000, 1) if latencies else 0,
        "successes": successes,
        "expected_failures": expected_failures,
        "unexpected_errors": unexpected_errors,
        "correctness": successes <= capacity,
    }


@pytest.mark.asyncio
async def test_load_read_endpoints():
    """Test read throughput at increasing concurrency levels."""
    await _ensure_db_setup()
    engine = create_async_engine(
        TEST_DB_URL, pool_size=80, max_overflow=40, isolation_level="READ_COMMITTED"
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        concurrency_levels = [10, 50, 100, 200, 500]
        print("\n" + "=" * 70)
        print("READ LOAD TEST (GET courses)")
        print("=" * 70)

        for n in concurrency_levels:
            result = await _run_concurrent_reads(session_factory, n)
            LOAD_TEST_RESULTS.append(result)
            print(
                f"  N={n:>4} | {result['throughput_rps']:>7.1f} rps | "
                f"avg={result['avg_latency_ms']:>6.1f}ms | "
                f"p95={result['p95_latency_ms']:>6.1f}ms | "
                f"p99={result['p99_latency_ms']:>6.1f}ms | "
                f"errors={result['errors']}"
            )

        # Should complete all without errors
        for r in LOAD_TEST_RESULTS:
            if r["type"] == "READ":
                assert r["errors"] == 0, f"Read errors at concurrency {r['concurrency']}"

    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_load_write_endpoints():
    """Test write throughput with pessimistic locking under contention."""
    await _ensure_db_setup()
    engine = create_async_engine(
        TEST_DB_URL, pool_size=80, max_overflow=40, isolation_level="READ_COMMITTED"
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        concurrency_levels = [10, 50, 100, 200, 500]
        print("\n" + "=" * 70)
        print("WRITE LOAD TEST (POST enrollment, capacity=1)")
        print("=" * 70)

        for n in concurrency_levels:
            # Reset: clear enrollments, set capacity=1
            async with session_factory() as session:
                await session.execute(delete(Enrollment))
                await session.execute(
                    update(Course).where(Course.id == 1).values(capacity=1)
                )
                await session.commit()

            result = await _run_concurrent_enrollments(session_factory, n, capacity=1)
            LOAD_TEST_RESULTS.append(result)
            print(
                f"  N={n:>4} | {result['throughput_rps']:>7.1f} rps | "
                f"avg={result['avg_latency_ms']:>6.1f}ms | "
                f"p95={result['p95_latency_ms']:>6.1f}ms | "
                f"successes={result['successes']} | "
                f"correct={result['correctness']}"
            )

        # All must be correct (exactly 1 success per run)
        for r in LOAD_TEST_RESULTS:
            if r["type"].startswith("WRITE"):
                assert r["correctness"], (
                    f"Correctness violation at N={r['concurrency']}: "
                    f"{r['successes']} successes for capacity {r['capacity']}"
                )
                assert r["successes"] == 1

    finally:
        # Cleanup
        async with session_factory() as session:
            await session.execute(delete(Enrollment))
            await session.execute(
                update(Course).where(Course.id == 1).values(capacity=40)
            )
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_load_mixed_workload():
    """Simulate realistic mixed read/write workload."""
    await _ensure_db_setup()
    engine = create_async_engine(
        TEST_DB_URL, pool_size=80, max_overflow=40, isolation_level="READ_COMMITTED"
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        # Reset
        async with session_factory() as session:
            await session.execute(delete(Enrollment))
            await session.execute(
                update(Course).where(Course.id == 1).values(capacity=50)
            )
            await session.commit()

        print("\n" + "=" * 70)
        print("MIXED WORKLOAD TEST (80% reads, 20% writes, N=200)")
        print("=" * 70)

        num_total = 200
        num_writes = 40
        num_reads = 160

        read_latencies = []
        write_latencies = []
        read_errors = 0
        write_successes = 0
        write_rejections = 0
        write_errors = 0

        async def do_read():
            nonlocal read_errors
            start = time.perf_counter()
            try:
                async with session_factory() as session:
                    result = await session.execute(
                        select(Course).order_by(Course.id).limit(50)
                    )
                    _ = result.scalars().all()
                read_latencies.append(time.perf_counter() - start)
            except Exception:
                read_errors += 1

        async def do_write(student_id: int):
            nonlocal write_successes, write_rejections, write_errors
            start = time.perf_counter()
            try:
                async with session_factory() as session:
                    await enrollment_service.register(
                        student_id=student_id, course_id=1, db=session
                    )
                    write_successes += 1
            except HTTPException:
                write_rejections += 1
            except Exception:
                write_errors += 1
            write_latencies.append(time.perf_counter() - start)

        tasks = []
        tasks.extend([do_read() for _ in range(num_reads)])
        tasks.extend([do_write(i) for i in range(1, num_writes + 1)])

        import random
        random.shuffle(tasks)

        wall_start = time.perf_counter()
        await asyncio.gather(*tasks)
        wall_time = time.perf_counter() - wall_start

        result = {
            "type": "MIXED",
            "total_requests": num_total,
            "read_requests": num_reads,
            "write_requests": num_writes,
            "total_time_s": round(wall_time, 3),
            "throughput_rps": round(num_total / wall_time, 1),
            "read_avg_ms": round(statistics.mean(read_latencies) * 1000, 1) if read_latencies else 0,
            "write_avg_ms": round(statistics.mean(write_latencies) * 1000, 1) if write_latencies else 0,
            "read_errors": read_errors,
            "write_successes": write_successes,
            "write_rejections": write_rejections,
            "write_errors": write_errors,
        }
        LOAD_TEST_RESULTS.append(result)

        print(f"  Total: {num_total} requests in {wall_time:.3f}s ({num_total/wall_time:.1f} rps)")
        print(f"  Reads:  avg={result['read_avg_ms']:.1f}ms, errors={read_errors}")
        print(f"  Writes: avg={result['write_avg_ms']:.1f}ms, "
              f"successes={write_successes}, rejections={write_rejections}, errors={write_errors}")
        print(f"  Write correctness: {write_successes <= 50}")

        assert read_errors == 0
        assert write_errors == 0
        assert write_successes <= 50  # capacity

    finally:
        async with session_factory() as session:
            await session.execute(delete(Enrollment))
            await session.execute(
                update(Course).where(Course.id == 1).values(capacity=40)
            )
            await session.commit()
        await engine.dispose()
