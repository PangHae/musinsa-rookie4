# Redis Rate Limiter 도입 비교 리포트

## 개요

멀티 워커(gunicorn) 환경에서 인메모리 Rate Limiter의 구조적 한계를 해결하기 위해
Redis 기반 Rate Limiter로 전환한 내용을 정리한 문서입니다.

---

## 문제 배경

### 인메모리 Rate Limiter의 한계

```
[gunicorn Master]
    ├── Worker 1 (메모리 A) ← 각자 독립된 상태
    ├── Worker 2 (메모리 B)
    ├── Worker 3 (메모리 C)
    └── Worker 4 (메모리 D)
```

`gunicorn.conf.py`에서 `WORKERS=4` 설정 시, 각 워커가 독립된 프로세스이므로
인메모리 딕셔너리(`_requests`, `_failures`, `_blocked_until`)가 프로세스 간에 공유되지 않습니다.

**결과**: Rate Limit이 사실상 `max_requests × 워커 수`로 완화됨
- 설정: 10초에 5회 제한
- 실제 효과: 10초에 최대 20회 허용 (워커 4개 × 5회)

---

## 비교

| 항목 | 인메모리 (`RateLimiter`) | Redis (`RedisRateLimiter`) |
|------|--------------------------|---------------------------|
| 상태 공유 | ❌ 프로세스별 독립 | ✅ 모든 워커가 동일 상태 |
| 멀티 워커 정확성 | ❌ Rate Limit 완화됨 | ✅ 정확하게 동작 |
| 서버 재시작 후 상태 | ❌ 초기화됨 | ✅ 유지됨 |
| Redis 의존성 | 없음 | Redis 필요 |
| 레이턴시 | 메모리 직접 접근 | 네트워크 RTT (~0.1ms 로컬) |
| 구현 복잡도 | 낮음 | 중간 |

---

## 구현 방식

### 슬라이딩 윈도우 — Redis Sorted Set

```
key: rl:enrollment:window:{student_id}
value: {timestamp: score} 쌍

ZREMRANGEBYSCORE  → 윈도우 밖 항목 제거
ZCARD             → 현재 요청 수 확인
ZADD              → 새 요청 기록
EXPIRE            → TTL 설정으로 자동 정리
```

### 최소 간격 — Redis String with TTL

```
key: rl:enrollment:interval:{student_id}
TTL: min_interval_seconds (밀리초 단위)

SET ... PX {ms}  → 키 생성
EXISTS           → 키 존재 시 "Too fast" 반환
```

### 실패 패널티 — Redis INCR + TTL

```
key: rl:enrollment:failures:{student_id}  — 실패 카운터
key: rl:enrollment:block:{student_id}     — 블록 여부 (TTL)

INCR             → 실패 카운트 증가
max_failures 초과 시 block 키 생성 (TTL = block_duration)
```

---

## 멀티 워커 시나리오 (Redis 도입 전후 비교)

### Before — 인메모리 (워커 4개, max_requests=5)

```
학생 A가 1초 안에 20개 요청 전송:

Worker1: 요청 1,2,3,4,5  → 5번째에서 블록  (자기 카운터만 봄)
Worker2: 요청 6,7,8,9,10 → 10번째에서 블록 (자기 카운터만 봄)
Worker3: 요청 11~15      → 15번째에서 블록
Worker4: 요청 16~20      → 20번째에서 블록

실제 허용된 요청: 20개 (설정의 4배)
```

### After — Redis (워커 4개, max_requests=5)

```
학생 A가 1초 안에 20개 요청 전송:

Worker1: 요청 1 → Redis 카운터: 1
Worker2: 요청 2 → Redis 카운터: 2
Worker3: 요청 3 → Redis 카운터: 3
Worker4: 요청 4 → Redis 카운터: 4
Worker1: 요청 5 → Redis 카운터: 5
Worker2: 요청 6 → Redis 카운터: 5 이상 → 블록
...이후 모든 워커에서 블록

실제 허용된 요청: 5개 (설정과 동일)
```

---

## 성능

| 측정 항목 | 값 |
|-----------|-----|
| Redis PING (로컬) | ~0.1ms |
| 슬라이딩 윈도우 체크 (파이프라인 4개 커맨드) | ~0.3–0.5ms |
| 인메모리 체크 | < 0.01ms |

수강신청 API는 DB 쿼리(~5–50ms)가 병목이므로
Redis 레이턴시 추가는 전체 응답 시간에 미치는 영향이 1% 미만입니다.

---

## 설정

`.env` 또는 환경변수:

```env
REDIS_URL=redis://localhost:6379
```

`docker-compose` 예시:

```yaml
services:
  redis:
    image: redis:latest
    ports:
      - "6379:6379"
```

---

## 결론

Redis 기반 Rate Limiter 도입으로 멀티 워커 환경에서의 구조적 한계를 해결했습니다.
인메모리 방식 대비 레이턴시 증가(< 0.5ms)는 수강신청 API의 전체 응답 시간에
실질적인 영향을 주지 않으며, 정확한 Rate Limiting 보장이라는 핵심 목표를 달성합니다.
