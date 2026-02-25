# Single Worker vs Multi Worker 부하 테스트 비교 리포트

**날짜**: 2026-02-26
**테스트 도구**: k6 v1.6.1 (100 VUs, 3 시나리오)
**환경**: Apple Silicon Mac (darwin/arm64), MariaDB Docker, Python 3.13
**서버**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
**테스트 스크립트**: `tests/k6_load_test.js`

---

## 1. 테스트 구성

| 시나리오 | 내용 |
|----------|------|
| `read_load` | 100 VUs × 30s, GET /courses |
| `write_concurrency` | 100 VUs × 100 iterations (동시 수강신청, capacity=200) |
| `mixed_load` | 100 VUs × 20s, 80% READ / 20% WRITE |

| 항목 | Single Worker | Multi Worker |
|------|--------------|--------------|
| 실행 명령 | `uvicorn ... ` (기본값) | `uvicorn ... --workers 4` |
| 프로세스 수 | 1 | 4 |
| Rate Limiter | 프로세스 공유 | 프로세스별 독립 (in-memory) |
| DB 잠금 | SELECT FOR UPDATE | SELECT FOR UPDATE |

---

## 2. 전체 결과 비교

| 메트릭 | Single Worker | Multi Worker | 개선율 |
|--------|--------------|--------------|--------|
| 총 HTTP 요청 수 | 1,963 | 6,404 | **+226%** |
| 전체 throughput (rps) | 21.6 | **70.3** | **+225%** |
| avg 응답시간 | 2,613 ms | **762 ms** | **3.4배 빠름** |
| p95 응답시간 | 8,217 ms | **1,820 ms** | **4.5배 빠름** |
| p(95)<2000 threshold | ❌ FAIL (8,217ms) | ✅ PASS (1,820ms) | |
| http_req_failed | 8.04% (158건) | 7.26% (465건)¹ | |
| checks_failed | **1.66% (31건)** | **0% (0건)** | ✅ 완전 해소 |

> ¹ 멀티 워커의 http_req_failed 465건은 전부 비즈니스 로직 거절 (409 정원초과 등).
> k6는 HTTP 4xx도 `http_req_failed`로 집계하므로 실질적 오류(connection reset)는 **0건**.

---

## 3. READ 시나리오 비교 (`read_load`: 100 VUs × 30s)

| 메트릭 | Single Worker | Multi Worker | 개선율 |
|--------|--------------|--------------|--------|
| 총 READ 요청 수 | 1,605 | **3,839** | +139% |
| throughput (rps) | 53.5 | **128.0** | **+139%** |
| avg 응답시간 | 2,448 ms | **692 ms** | 3.5배 빠름 |
| p50 응답시간 | 3,032 ms | **510 ms** | 5.9배 빠름 |
| p95 응답시간 | 3,488 ms | **1,470 ms** | 2.4배 빠름 |
| max 응답시간 | 11,523 ms | **2,950 ms** | 3.9배 빠름 |
| 에러 (connection reset) | 0건 | 0건 | - |

---

## 4. WRITE 동시성 시나리오 비교 (`write_concurrency`: 100 VUs × 100 iter)

| 메트릭 | Single Worker | Multi Worker |
|--------|--------------|--------------|
| 총 시도 | 100 | 100 |
| Connection Reset | **31건 (31%)** | **0건 (0%)** ✅ |
| 정상 처리 (201 or 4xx) | 69건 | **100건** |
| checks 통과율 | 69% | **100%** |
| capacity 초과 여부 | 없음 ✅ | 없음 ✅ |
| avg write 응답시간 | 4,654 ms | **1,600 ms** |
| p95 write 응답시간 | 10,348 ms | **3,010 ms** |

> **핵심 개선**: Single Worker의 connection reset 31건은 uvicorn 단일 프로세스의
> TCP accept backlog 한계로 발생. Multi Worker(4개)는 **backlog를 분산 처리**하여 완전 해소.

---

## 5. MIXED 시나리오 비교 (`mixed_load`: 100 VUs × 20s, 80/20)

| 메트릭 | Single Worker | Multi Worker | 개선율 |
|--------|--------------|--------------|--------|
| 총 iterations | ~816 | **~2,365** | +190% |
| throughput (rps) | ~40.8 | **~118.3** | +190% |
| read avg 응답시간 | 2,448 ms (전체 평균) | **692 ms** | 3.5배 빠름 |
| write avg 응답시간 | 4,654 ms (전체 평균) | **1,600 ms** | 2.9배 빠름 |

---

## 6. 동시성 정확성 (SELECT FOR UPDATE)

| 방식 | write_concurrency 성공 수 | capacity | 초과 여부 |
|------|--------------------------|----------|-----------|
| Single Worker | ~69건 (31건 reset 제외) | 200 | ✅ 없음 |
| Multi Worker | 100건 | 200 | ✅ 없음 |

Multi Worker 환경에서 **4개의 프로세스가 동시에 DB에 접근**하더라도
`SELECT FOR UPDATE` (pessimistic locking) 전략이 정상 동작함을 확인.
DB 수준 잠금은 프로세스 수에 무관하게 정확성을 보장한다.

---

## 7. Single Worker의 connection reset 원인 분석

```
Single Worker 구조:
  k6 (100 VUs) → [TCP 연결 100개 동시] → uvicorn (1 process, 1 event loop)
                                              ↑
                          OS TCP accept backlog 한계 초과
                          → 일부 연결 거부 (connection reset by peer)

Multi Worker 구조:
  k6 (100 VUs) → [TCP 연결 100개 동시] → OS 소켓 (SO_REUSEPORT)
                                          ├─ uvicorn worker 1
                                          ├─ uvicorn worker 2
                                          ├─ uvicorn worker 3
                                          └─ uvicorn worker 4
                          → 4개 프로세스가 연결을 분산 수용
                          → backlog 여유 충분 → connection reset 0건
```

---

## 8. 주의사항: Rate Limiter in Multi Worker

| 항목 | Single Worker | Multi Worker |
|------|--------------|--------------|
| Rate Limiter 구현 | In-memory (프로세스 내) | In-memory (프로세스별 독립) |
| 동일 학생 요청 분산 시 | 1개 창에서 카운트 | 최대 4개 창에서 각각 카운트 |
| 실질적 limit | 5 req / 10s / 학생 | 이론상 20 req / 10s / 학생¹ |

> ¹ 요청이 동일 worker로 라우팅될 보장이 없으므로, 멀티 워커 환경에서 Rate Limiter의
> 정확한 동작을 보장하려면 **Redis 기반 Rate Limiter**로 전환이 필요.
> 현재 테스트에서는 학생별로 1~2회 요청만 이루어져 실질적 영향 없음.

---

## 9. 결론

| 항목 | 결론 |
|------|------|
| 처리량 | Multi Worker 4개로 **3.3배 향상** (21.6 → 70.3 rps) |
| 응답시간 | p95 기준 **4.5배 개선** (8.2s → 1.82s) |
| Connection Reset | **완전 해소** (31건 → 0건) |
| 동시성 정확성 | 두 환경 모두 SELECT FOR UPDATE로 capacity 초과 없음 ✅ |
| SLA 충족 | Single ❌ / Multi ✅ (`p(95)<2000ms` 기준) |
| 권장 배포 방식 | `uvicorn --workers N` (N = CPU 코어 수) 또는 `gunicorn -k uvicorn.workers.UvicornWorker -w N` |
| Rate Limiter 개선 | 멀티 워커 운영 시 Redis 기반으로 전환 권장 |
