# 부하 테스트 3종 비교 설계

**날짜**: 2026-02-25
**목적**: test_load.py / test_load_http.py / k6 세 가지 방식의 부하 테스트를 구현하고 결과를 비교 리포트로 생성한다.

---

## 배경

현재 `tests/test_load.py`는 서비스 레이어를 직접 호출하므로 HTTP 스택(미들웨어·인증·Rate Limiter)이 측정 범위에서 제외된다. 실제 운영 환경과의 차이를 확인하기 위해 두 가지 방식을 추가한다.

| 방식 | 계층 | 네트워크 | 서버 필요 |
|------|------|----------|-----------|
| `test_load.py` | Service + DB | 없음 | 불필요 |
| `test_load_http.py` | FastAPI 전체 (ASGI) | 없음 | 불필요 |
| k6 | FastAPI 전체 + TCP/IP | 실제 소켓 | 필요 |

---

## test_load_http.py 설계

### 방식
- `httpx.AsyncClient` + `ASGITransport(app=app)`
- 테스트 DB(`course_registration_test`) 오버라이드 (`app.dependency_overrides[get_db]`)
- 각 테스트 시작 전 rate limiter 상태 초기화

### 시나리오 (test_load.py와 동일)
1. **READ**: `GET /courses` — 동시성 10·50·100·200·500
2. **WRITE**: `POST /enrollments` (capacity=1) — 동시성 10·50·100·200·500
3. **MIXED**: 80% READ + 20% WRITE, N=200

### 주요 고려사항
- enrollment 요청: 요청별 고유 student_id + JWT 헤더 (다른 학생이 동시 신청하는 실상 재현)
- 동시 첫 요청은 rate limiter의 min_interval 제약에 걸리지 않음 (이전 요청 없음)
- 출력 포맷은 test_load.py와 동일하게 통일 (비교 용이성)

---

## k6_load_test.js 설계

### 방식
- k6 실행 → 실제 TCP/IP → `http://localhost:8000`
- 서버는 테스트 DB 환경변수로 기동: `DB_NAME=course_registration_test`

### 토큰 취득
- k6 `setup()` 함수에서 `POST /auth/login` 100회 호출
- student_number 형식: `S00001`~`S00100`
- 취득한 토큰 배열을 VU에 분배

### 시나리오
1. **READ 부하**: 100 VUs, 30초, `GET /courses`
2. **WRITE 동시성**: 100 VUs × 1회, `POST /enrollments` (capacity=1 코스)
3. **MIXED**: 100 VUs, 80% read / 20% write

### 출력
- `--out json=k6_results.json` 으로 상세 메트릭 저장
- `--summary-export=k6_summary.json` 으로 집계값 저장

---

## 리포트 설계

**파일**: `docs/load-test-report-2026-02-25.md`

### 구성
1. 측정 방식 비교 표 (무엇을 포함/제외하는지)
2. READ 성능 비교 (동시성 레벨별 throughput, p50/p95/p99)
3. WRITE 동시성 정확성 비교 (capacity=1일 때 성공 건수)
4. MIXED 워크로드 비교
5. 분석 및 결론

### 생성 방법
- pytest 테스트는 `-s` 플래그로 실행 후 stdout 캡처
- k6 결과는 `k6_summary.json` 파싱
- 리포트는 수동 또는 스크립트로 취합

---

## 파일 목록

| 파일 | 설명 |
|------|------|
| `tests/test_load_http.py` | httpx + ASGI Transport 부하 테스트 |
| `tests/k6_load_test.js` | k6 부하 테스트 스크립트 |
| `docs/load-test-report-2026-02-25.md` | 비교 리포트 (테스트 후 생성) |
