# Redis Rate Limiter 테스트 리포트

## 실행 환경

| 항목 | 값 |
|------|-----|
| 날짜 | 2026-02-22 |
| Python | 3.13.12 |
| pytest | 8.3.4 |
| pytest-asyncio | 0.25.0 |
| redis 클라이언트 | redis[asyncio] 5.2.1 |
| Redis 서버 | redis:latest (Docker, localhost:6379) |

---

## 테스트 결과 요약

| 테스트 파일 | 통과 | 실패 | 총계 |
|-------------|------|------|------|
| `tests/test_rate_limiter.py` | 7 | 0 | 7 |
| `tests/test_redis_rate_limiter.py` | 10 | 0 | 10 |
| **합계** | **17** | **0** | **17** |

**전체 결과: ✅ 17 passed (4.03s)**

---

## 테스트 케이스 상세

### `tests/test_rate_limiter.py` — 기존 계약 검증 (Redis 버전)

기존 인메모리 Rate Limiter와 동일한 동작 계약을 Redis 버전이 만족하는지 검증합니다.

| # | 테스트명 | 검증 내용 | 결과 |
|---|---------|-----------|------|
| 1 | `test_allows_normal_requests` | 한도 내 요청은 모두 허용 | ✅ PASSED |
| 2 | `test_blocks_after_rate_limit` | 한도 초과 시 거부 및 메시지 확인 | ✅ PASSED |
| 3 | `test_min_interval_enforcement` | 빠른 연속 요청 차단, 대기 후 허용 | ✅ PASSED |
| 4 | `test_failure_penalty_blocks` | 연속 실패 시 임시 차단, 만료 후 해제 | ✅ PASSED |
| 5 | `test_success_resets_failures` | 성공 시 실패 카운터 초기화 | ✅ PASSED |
| 6 | `test_independent_per_student` | 학생별 독립적인 Rate Limit 적용 | ✅ PASSED |
| 7 | `test_window_expiry` | 슬라이딩 윈도우 만료 후 카운터 리셋 | ✅ PASSED |

### `tests/test_redis_rate_limiter.py` — Redis 고유 기능 검증

Redis 구현에 특화된 동작과 멀티 프로세스 공유 상태를 검증합니다.

| # | 테스트명 | 검증 내용 | 결과 |
|---|---------|-----------|------|
| 1 | `test_allows_normal_requests` | 기본 허용 동작 | ✅ PASSED |
| 2 | `test_blocks_after_rate_limit` | Rate Limit 초과 차단 | ✅ PASSED |
| 3 | `test_independent_per_student` | 학생별 독립 상태 | ✅ PASSED |
| 4 | `test_min_interval_blocks_rapid_requests` | 최소 간격 차단 | ✅ PASSED |
| 5 | `test_min_interval_allows_after_wait` | 대기 후 허용 | ✅ PASSED |
| 6 | `test_window_expiry_resets_count` | 윈도우 만료 시 카운터 리셋 | ✅ PASSED |
| 7 | `test_failure_penalty_triggers_block` | 연속 실패 차단 | ✅ PASSED |
| 8 | `test_block_expires_after_duration` | 차단 만료 후 해제 | ✅ PASSED |
| 9 | `test_success_resets_failure_count` | 성공 시 실패 카운터 초기화 | ✅ PASSED |
| 10 | `test_shared_state_across_instances` | **멀티 워커 공유 상태 검증** | ✅ PASSED |

---

## 핵심 테스트: 멀티 워커 공유 상태

`test_shared_state_across_instances` 는 이번 도입의 핵심 목적을 검증합니다.

```python
# 동일한 Redis key_prefix를 가진 두 인스턴스 생성 (= 두 개의 gunicorn 워커 시뮬레이션)
worker1 = RedisRateLimiter(**kwargs)  # 워커 1
worker2 = RedisRateLimiter(**kwargs)  # 워커 2

# worker1이 요청 한도를 소진
await worker1.check(1)  # 카운터: 1
await worker1.check(1)  # 카운터: 2
await worker1.check(1)  # 카운터: 3 (max_requests=3)

# worker2는 Redis에서 공유된 카운터를 읽어 차단
allowed, reason = await worker2.check(1)
assert not allowed  # ✅ PASSED — 공유 상태 정상 동작
```

인메모리 방식에서는 `worker2`가 자신의 카운터(0)를 보고 허용했겠지만,
Redis 방식에서는 공유 카운터(3)를 보고 올바르게 차단합니다.

---

## TDD 진행 기록

| 단계 | 내용 |
|------|------|
| RED | `test_redis_rate_limiter.py` 작성 → `ModuleNotFoundError` 확인 |
| GREEN | `redis_rate_limiter.py` 구현 → 9/10 통과 |
| 버그 수정 | `block_duration=0.5`에서 `ex=0` 에러 → `px` (밀리초)로 수정 |
| GREEN | 10/10 통과 |
| REFACTOR | `rate_limiter.py`를 Redis 버전 싱글톤으로 교체 |
| 검증 | 기존 `test_rate_limiter.py` 포함 17/17 통과 |
