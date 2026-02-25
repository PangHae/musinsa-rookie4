# 부하 테스트 3종 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** test_load_http.py(httpx+ASGI) 및 k6 부하 테스트를 작성하고, 기존 test_load.py와 비교한 마크다운 리포트를 생성한다.

**Architecture:**
- test_load_http.py: httpx AsyncClient + ASGITransport, 테스트 DB 오버라이드, rate limiter 초기화, 동일 시나리오
- k6_load_test.js: 실제 HTTP → localhost:8000, setup()에서 로그인으로 토큰 취득, 100 VU 시나리오
- 리포트: 세 테스트의 stdout/JSON 결과를 취합해 docs/load-test-report-2026-02-25.md 생성

**Tech Stack:** Python 3.13 / FastAPI / httpx / SQLAlchemy async / k6 / MariaDB

---

## Task 1: test_load_http.py 작성

**Files:**
- Create: `tests/test_load_http.py`

**Step 1: 파일 생성**

`tests/test_load_http.py` 전체 내용:

```python
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
```

**Step 2: 테스트 실행하여 통과 확인**

```bash
cd /Users/panghae/panghae/musinsa-rookie4
pytest tests/test_load_http.py -v -s 2>&1 | tee /tmp/load_http_results.txt
```

Expected: 3개 테스트 모두 PASSED

**Step 3: 커밋**

```bash
git add tests/test_load_http.py
git commit -m "Test: httpx + ASGI Transport 부하 테스트 추가"
```

---

## Task 2: k6_load_test.js 작성

**Files:**
- Create: `tests/k6_load_test.js`

**Step 1: 파일 생성**

`tests/k6_load_test.js` 전체 내용:

```javascript
/**
 * k6 부하 테스트 — 실제 HTTP (TCP/IP → localhost:8000)
 *
 * 전제조건:
 *   1. 서버가 테스트 DB로 실행 중:
 *      DB_NAME=course_registration_test uvicorn app.main:app --host 0.0.0.0 --port 8000
 *   2. k6 설치됨: brew install k6
 *
 * 실행:
 *   k6 run tests/k6_load_test.js --summary-export=k6_summary.json
 *
 * 시나리오:
 *   - read_load    : 100 VUs × 30초, GET /courses
 *   - write_concurrency: 100 VUs × 1회, POST /enrollments (동시성 테스트)
 *   - mixed_load   : 100 VUs × 20초, 80% READ / 20% WRITE
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// 커스텀 메트릭
const writeSuccessRate = new Rate('write_success_rate');
const readLatency     = new Trend('read_latency',  true);
const writeLatency    = new Trend('write_latency', true);

export const options = {
  scenarios: {
    // 시나리오 1: READ 부하 (100 VUs, 30초)
    read_load: {
      executor:  'constant-vus',
      vus:       100,
      duration:  '30s',
      exec:      'readScenario',
      startTime: '0s',
    },
    // 시나리오 2: WRITE 동시성 (100 VUs, 각 1회 — 동시에 신청)
    write_concurrency: {
      executor:   'shared-iterations',
      vus:        100,
      iterations: 100,
      maxDuration:'30s',
      exec:       'writeScenario',
      startTime:  '35s',  // read 종료 후 5초 뒤 시작
    },
    // 시나리오 3: MIXED (100 VUs, 20초, 80/20)
    mixed_load: {
      executor:  'constant-vus',
      vus:       100,
      duration:  '20s',
      exec:      'mixedScenario',
      startTime: '70s',  // write 종료 후
    },
  },
  thresholds: {
    // 리포트용 기준치 (실패해도 테스트는 계속)
    http_req_duration: ['p(95)<2000'],
    http_req_failed:   ['rate<0.5'],
  },
};

// ─── setup: 학생 토큰 취득 ─────────────────────────────────────────────────
export function setup() {
  const tokens = [];

  // S00001 ~ S00100 로그인
  for (let i = 1; i <= 100; i++) {
    const studentNumber = `S${String(i).padStart(5, '0')}`;
    const res = http.post(
      `${BASE_URL}/auth/login`,
      JSON.stringify({ student_number: studentNumber }),
      { headers: { 'Content-Type': 'application/json' } }
    );

    if (res.status === 200) {
      const body = JSON.parse(res.body);
      tokens.push({
        token:      body.access_token,
        student_id: body.student_id,
      });
    } else {
      console.warn(`Login failed for ${studentNumber}: ${res.status} ${res.body}`);
    }
  }

  console.log(`Setup complete: ${tokens.length}/100 tokens acquired`);
  return { tokens };
}

// ─── 시나리오 1: READ ──────────────────────────────────────────────────────
export function readScenario() {
  const start = Date.now();
  const res = http.get(`${BASE_URL}/courses`);
  readLatency.add(Date.now() - start);

  check(res, {
    'read status 200': (r) => r.status === 200,
  });
}

// ─── 시나리오 2: WRITE 동시성 ─────────────────────────────────────────────
export function writeScenario(data) {
  // VU 인덱스로 토큰 선택 (0-based)
  const idx = (__VU - 1) % data.tokens.length;
  const { token, student_id } = data.tokens[idx];

  const start = Date.now();
  const res = http.post(
    `${BASE_URL}/enrollments`,
    JSON.stringify({ student_id: student_id, course_id: 1 }),
    {
      headers: {
        'Content-Type':  'application/json',
        'Authorization': `Bearer ${token}`,
      },
    }
  );
  writeLatency.add(Date.now() - start);

  const success = res.status === 201;
  writeSuccessRate.add(success);

  check(res, {
    'write 201 or expected failure': (r) => [201, 400, 409, 422, 429].includes(r.status),
  });
}

// ─── 시나리오 3: MIXED ────────────────────────────────────────────────────
export function mixedScenario(data) {
  // 80% read, 20% write
  if (Math.random() < 0.8) {
    readScenario();
  } else {
    writeScenario(data);
  }
  sleep(0.1);
}
```

**Step 2: k6 테스트 사전 DB 준비 (Python one-liner)**

테스트 DB에서 course_id=1 capacity를 200으로 설정 (k6 WRITE 처리량 측정용):

```bash
cd /Users/panghae/panghae/musinsa-rookie4
python -c "
import asyncio
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.conftest import TEST_DB_URL
from app.models.enrollment import Enrollment
from app.models.course import Course

async def prepare():
    engine = create_async_engine(TEST_DB_URL, isolation_level='READ_COMMITTED')
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as s:
        await s.execute(delete(Enrollment))
        await s.execute(update(Course).where(Course.id == 1).values(capacity=200))
        await s.commit()
    await engine.dispose()
    print('DB prepared: enrollments cleared, course 1 capacity=200')

asyncio.run(prepare())
"
```

**Step 3: 서버 시작 (테스트 DB 연결)**

별도 터미널에서:

```bash
cd /Users/panghae/panghae/musinsa-rookie4
DB_NAME=course_registration_test uvicorn app.main:app --host 0.0.0.0 --port 8000
```

헬스체크 확인:
```bash
curl -s http://localhost:8000/health
# Expected: {"status":"ok"} or 200 OK
```

**Step 4: k6 실행 및 결과 저장**

```bash
cd /Users/panghae/panghae/musinsa-rookie4
k6 run tests/k6_load_test.js \
  --summary-export=k6_summary.json \
  2>&1 | tee /tmp/k6_results.txt
```

Expected: 3가지 시나리오 모두 실행, `k6_summary.json` 생성

**Step 5: 커밋**

```bash
git add tests/k6_load_test.js
git commit -m "Test: k6 부하 테스트 스크립트 추가"
```

---

## Task 3: test_load.py (기존) 실행 및 결과 캡처

**Step 1: 기존 test_load.py 실행**

```bash
cd /Users/panghae/panghae/musinsa-rookie4
pytest tests/test_load.py -v -s 2>&1 | tee /tmp/load_direct_results.txt
```

Expected: 3개 테스트 PASSED, stdout에 메트릭 출력

---

## Task 4: 비교 리포트 생성

**Files:**
- Create: `docs/load-test-report-2026-02-25.md`

**Step 1: 세 테스트 결과 취합 후 리포트 작성**

아래 내용 기반으로 실제 측정값을 채워 작성 (실행 결과 확인 후 수치 기입):

```markdown
# 부하 테스트 비교 리포트

**날짜**: 2026-02-25
**테스트 환경**: Apple Silicon Mac, MariaDB Docker, Python 3.13

---

## 1. 측정 방식 비교

| 항목 | test_load.py | test_load_http.py | k6 |
|------|-------------|-------------------|-----|
| 계층 | Service + DB | FastAPI 전체 (ASGI) | FastAPI 전체 + TCP/IP |
| HTTP 파싱/라우팅 | X | O | O |
| 미들웨어 | X | O | O |
| Rate Limiter | X | O (초기화 후) | O |
| JWT 인증 검증 | X | O | O |
| 실제 TCP 소켓 | X | X | O |
| 서버 실행 필요 | X | X | O |
| 실행 도구 | pytest | pytest | k6 |

---

## 2. READ 처리량 비교 (GET /courses)

### test_load.py (Service 직접 호출)
| 동시성 | throughput (rps) | avg (ms) | p95 (ms) | p99 (ms) | errors |
|--------|-----------------|----------|----------|----------|--------|
| 10 | | | | | |
| 50 | | | | | |
| 100 | | | | | |
| 200 | | | | | |
| 500 | | | | | |

### test_load_http.py (httpx + ASGI)
| 동시성 | throughput (rps) | avg (ms) | p95 (ms) | p99 (ms) | errors |
|--------|-----------------|----------|----------|----------|--------|
| 10 | | | | | |
| 50 | | | | | |
| 100 | | | | | |
| 200 | | | | | |
| 500 | | | | | |

### k6 (실제 HTTP, 100 VUs × 30s)
| 메트릭 | 값 |
|--------|-----|
| 총 요청 수 | |
| throughput (rps) | |
| avg (ms) | |
| p50 (ms) | |
| p95 (ms) | |
| p99 (ms) | |
| 에러율 | |

---

## 3. WRITE 동시성 정확성 비교 (POST /enrollments, capacity=1)

| 방식 | N=10 | N=50 | N=100 | N=200 | N=500 |
|------|------|------|-------|-------|-------|
| test_load.py | successes=? correct=? | ... | | | |
| test_load_http.py | successes=? correct=? | ... | | | |
| k6 (100 VUs) | N/A (처리량 테스트) | | | | |

---

## 4. MIXED 워크로드 비교

| 방식 | throughput (rps) | read avg (ms) | write avg (ms) | write successes |
|------|-----------------|--------------|----------------|-----------------|
| test_load.py | | | | |
| test_load_http.py | | | | |
| k6 | | | | |

---

## 5. 분석

### HTTP 스택 오버헤드
- test_load.py → test_load_http.py: HTTP 레이어(라우팅·미들웨어·인증·직렬화) 추가 비용
- test_load_http.py → k6: 실제 TCP/IP + OS 소켓 추가 비용

### 동시성 정확성
- 세 방식 모두 capacity=1 코스에서 N명 동시 신청 시 정확히 1명만 성공해야 함
- SELECT FOR UPDATE (pessimistic locking) 전략의 유효성 검증

### Rate Limiter 영향
- test_load.py: Rate Limiter 없음 (서비스 직접 호출)
- test_load_http.py: Rate Limiter 통과 (각 student별 독립 창)
- k6: Rate Limiter 통과 (실제 HTTP, 각 학생 토큰 독립)

---

## 6. 결론

(테스트 실행 후 수치 기반으로 작성)
```

**Step 2: 커밋**

```bash
git add docs/load-test-report-2026-02-25.md k6_summary.json
git commit -m "Docs: 부하 테스트 3종 비교 리포트 추가"
```

---

## 실행 순서 요약

```
1. pytest tests/test_load_http.py -v -s   # Task 1 검증
2. pytest tests/test_load.py -v -s        # Task 3 (기존)
3. 서버 시작 (별도 터미널)
4. k6 run tests/k6_load_test.js           # Task 2 검증
5. 리포트 작성                            # Task 4
```
