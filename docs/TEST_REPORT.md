# 테스트 보고서

## 실행 환경

- Python 3.13.12
- pytest 8.3.4 + pytest-asyncio 0.25.0
- 테스트 DB: MariaDB (`course_registration_test`)

## 실행 결과

```
31 passed in 5.56s
```

**전체 31개 테스트 통과, 실패 0건.**

## 테스트 목록

### test_health.py — 헬스체크 (1개)

| 테스트 | 설명 | 결과 |
|--------|------|------|
| `test_health_check` | `GET /health` → 200 OK | PASSED |

### test_courses.py — 조회 API (6개)

| 테스트 | 설명 | 결과 |
|--------|------|------|
| `test_get_departments` | 학과 목록 조회 | PASSED |
| `test_get_professors` | 교수 목록 조회 | PASSED |
| `test_get_professors_by_department` | 학과별 교수 필터링 | PASSED |
| `test_get_courses` | 강좌 목록 조회 (정원/수강인원 포함) | PASSED |
| `test_get_courses_by_department` | 학과별 강좌 필터링 | PASSED |
| `test_get_students_paginated` | 학생 목록 페이지네이션 | PASSED |
| `test_get_students_by_department` | 학과별 학생 필터링 | PASSED |

### test_enrollments.py — 수강신청/취소 (12개)

| 테스트 | 설명 | 결과 |
|--------|------|------|
| `test_register_course` | 정상 수강신청 → 201 | PASSED |
| `test_register_without_auth` | 인증 없이 수강신청 → 403 | PASSED |
| `test_register_for_another_student` | 타인 사칭 수강신청 → 403 | PASSED |
| `test_register_duplicate` | 중복 수강신청 → 409 | PASSED |
| `test_register_student_not_found` | 존재하지 않는 학생 → 401 | PASSED |
| `test_register_course_not_found` | 존재하지 않는 강좌 → 404 | PASSED |
| `test_cancel_enrollment` | 정상 수강취소 → 204 | PASSED |
| `test_cancel_not_found` | 존재하지 않는 수강 취소 → 404 | PASSED |
| `test_cancel_another_students_enrollment` | 타인 수강 취소 시도 → 403 | PASSED |
| `test_timetable` | 시간표 조회 (수강신청 후) | PASSED |
| `test_timetable_student_not_found` | 존재하지 않는 학생 시간표 → 404 | PASSED |
| `test_credit_limit_exceeded` | 18학점 초과 수강신청 → 409 | PASSED |

### test_concurrency.py — 동시성 (1개)

| 테스트 | 설명 | 결과 |
|--------|------|------|
| `test_concurrent_registration` | 정원 1명 강좌에 100명 동시 신청 → 정확히 1명 성공 | PASSED |

### test_load.py — 부하 테스트 (3개)

| 테스트 | 설명 | 결과 |
|--------|------|------|
| `test_load_read_endpoints` | 동시 10/50/100/200/500건 읽기 요청 처리 | PASSED |
| `test_load_write_endpoints` | 동시 10/50/100/200/500건 수강신청 (정원=1, 정확성 검증) | PASSED |
| `test_load_mixed_workload` | 혼합 부하 200건 (읽기 80%, 쓰기 20%) | PASSED |

### test_rate_limiter.py — 매크로 방지 (7개)

| 테스트 | 설명 | 결과 |
|--------|------|------|
| `test_allows_normal_requests` | 정상 속도 요청 허용 | PASSED |
| `test_blocks_after_rate_limit` | Rate limit 초과 시 차단 | PASSED |
| `test_min_interval_enforcement` | 최소 요청 간격 미만 시 차단 | PASSED |
| `test_failure_penalty_blocks` | 연속 실패 시 일시 차단 | PASSED |
| `test_success_resets_failures` | 성공 시 실패 카운터 초기화 | PASSED |
| `test_independent_per_student` | 학생별 독립 제한 | PASSED |
| `test_window_expiry` | 윈도우 만료 후 다시 허용 | PASSED |

## 테스트 분류

| 분류 | 테스트 수 | 통과 | 실패 |
|------|----------|------|------|
| 헬스체크 | 1 | 1 | 0 |
| 조회 API | 7 | 7 | 0 |
| 수강신청/취소 | 12 | 12 | 0 |
| 동시성 | 1 | 1 | 0 |
| 부하 테스트 | 3 | 3 | 0 |
| 매크로 방지 | 7 | 7 | 0 |
| **합계** | **31** | **31** | **0** |

## 실행 방법

```bash
# 전체 테스트
pytest tests/ -v

# 개별 파일
pytest tests/test_enrollments.py -v
pytest tests/test_concurrency.py -v
pytest tests/test_load.py -v -s
pytest tests/test_rate_limiter.py -v
```
