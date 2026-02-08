# 요구사항 분석 및 설계 문서

## 1. 요구사항 분석

### 1.1 명시적 요구사항

| 구분 | 요구사항 |
|------|---------|
| 학생 목록 조회 | 학생 리스트를 조회할 수 있어야 함 |
| 강좌 목록 조회 | 전체/학과별 조회, 정원·수강인원·시간표 포함 |
| 교수 목록 조회 | 교수 리스트를 조회할 수 있어야 함 |
| 수강신청 | 학생이 강좌에 수강신청 |
| 수강취소 | 수강신청을 취소 |
| 시간표 조회 | 이번 학기 내 시간표 조회 |
| 학점 제한 | 학기당 최대 18학점 |
| 시간 충돌 방지 | 동일 시간대 중복 수강 불가 |
| 정원 초과 방지 | 정원을 절대 초과할 수 없음 (동시성 핵심) |

### 1.2 암묵적 요구사항

분석을 통해 도출한 암묵적 요구사항:

- **중복 수강 방지**: 동일 강좌에 중복 신청 불가 (UNIQUE 제약)
- **데이터 무결성**: FK 제약을 통한 참조 무결성 보장
- **성능**: 10,000명 학생, 500개 강좌 규모에서 1분 이내 시작
- **멱등성**: 시딩은 이미 데이터가 있으면 건너뛰기
- **에러 응답**: 적절한 HTTP 상태 코드와 에러 메시지

## 2. 데이터 모델 설계

### 2.1 ERD

```
departments (1) ──< (N) professors
departments (1) ──< (N) courses
departments (1) ──< (N) students
professors  (1) ──< (N) courses
courses     (1) ──< (N) course_schedules
courses     (1) ──< (N) enrollments
students    (1) ──< (N) enrollments
```

### 2.2 테이블 설계

#### departments
| 컬럼 | 타입 | 제약 |
|------|------|------|
| id | INT | PK, AUTO_INCREMENT |
| name | VARCHAR(100) | NOT NULL, UNIQUE |
| code | VARCHAR(10) | NOT NULL, UNIQUE |

#### professors
| 컬럼 | 타입 | 제약 |
|------|------|------|
| id | INT | PK, AUTO_INCREMENT |
| name | VARCHAR(50) | NOT NULL |
| employee_number | VARCHAR(20) | NOT NULL, UNIQUE |
| department_id | INT | FK → departments.id |

#### courses
| 컬럼 | 타입 | 제약 |
|------|------|------|
| id | INT | PK, AUTO_INCREMENT |
| name | VARCHAR(100) | NOT NULL |
| code | VARCHAR(20) | NOT NULL, UNIQUE |
| credits | INT | NOT NULL |
| capacity | INT | NOT NULL |
| department_id | INT | FK → departments.id |
| professor_id | INT | FK → professors.id |

#### course_schedules
| 컬럼 | 타입 | 제약 |
|------|------|------|
| id | INT | PK, AUTO_INCREMENT |
| course_id | INT | FK → courses.id |
| day_of_week | VARCHAR(10) | NOT NULL |
| start_time | VARCHAR(5) | NOT NULL |
| end_time | VARCHAR(5) | NOT NULL |

**설계 결정**: `course_schedules`를 별도 테이블로 분리한 이유:
- 하나의 강좌가 여러 요일에 진행될 수 있음 (예: 월/수)
- SQL 레벨에서의 시간 충돌 검사가 용이
- 정규화를 통한 데이터 일관성 보장

#### students
| 컬럼 | 타입 | 제약 |
|------|------|------|
| id | INT | PK, AUTO_INCREMENT |
| name | VARCHAR(50) | NOT NULL |
| student_number | VARCHAR(20) | NOT NULL, UNIQUE |
| year | INT | NOT NULL |
| department_id | INT | FK → departments.id |

#### enrollments
| 컬럼 | 타입 | 제약 |
|------|------|------|
| id | INT | PK, AUTO_INCREMENT |
| student_id | INT | FK → students.id |
| course_id | INT | FK → courses.id |
| registered_at | DATETIME | NOT NULL, DEFAULT NOW() |
| - | - | UNIQUE(student_id, course_id) |

## 3. 동시성 제어 전략

### 3.1 문제 정의

> 정원이 1명 남은 강좌에 100명이 동시에 수강신청하면, 정확히 1명만 성공해야 한다.

이는 전형적인 **lost update** 문제이며, 적절한 동시성 제어 없이는 정원을 초과하는 등록이 발생할 수 있다.

### 3.2 선택지 분석

| 전략 | 장점 | 단점 |
|------|------|------|
| **Optimistic Locking** (버전 컬럼) | 경합 적을 때 성능 우수 | 높은 경합 시 재시도 폭주 |
| **Pessimistic Locking** (SELECT FOR UPDATE) | 경합 시에도 안정적 | 락 보유 시간만큼 직렬화 |
| Application-level Lock | DB 부하 없음 | 단일 프로세스에서만 동작 |

### 3.3 선택: Pessimistic Locking (비관적 잠금)

**이유**:
1. **높은 경합 시나리오**: 인기 강좌에 100명이 동시 신청하는 상황에서 optimistic locking은 대부분의 요청이 충돌 후 재시도해야 하므로 비효율적
2. **안정성**: SELECT FOR UPDATE는 DBMS가 보장하는 행 수준 잠금으로, 확실하게 하나의 트랜잭션만 통과
3. **짧은 락 보유 시간**: 수강신청 트랜잭션은 몇 가지 검증 + INSERT로 밀리초 단위 — 병목이 되지 않음
4. **다중 프로세스 호환**: DB 레벨 잠금이므로 워커를 여러 개 띄워도 동일하게 동작

### 3.4 트랜잭션 흐름

```
BEGIN TRANSACTION
│
├─ 1. 학생 존재 확인
│
├─ 2. SELECT * FROM courses WHERE id = ? FOR UPDATE
│     └─ 해당 강좌 행에 배타적 잠금 획득
│        (다른 트랜잭션은 이 행을 읽거나 수정할 때 대기)
│
├─ 3. 현재 수강 인원 조회 (COUNT)
│     └─ capacity 초과 시 → 409 "Course is full"
│
├─ 4. 중복 수강 확인
│     └─ 이미 등록 시 → 409 "Already enrolled"
│
├─ 5. 학점 제한 확인
│     └─ 현재 학점 + 강좌 학점 > 18 → 409 "Credit limit exceeded"
│
├─ 6. 시간 충돌 확인
│     └─ 같은 요일, 겹치는 시간대 → 409 "Schedule conflict"
│
├─ 7. INSERT INTO enrollments (student_id, course_id)
│
COMMIT (잠금 해제)
```

### 3.5 격리 수준

**READ COMMITTED** 격리 수준을 사용합니다.

`REPEATABLE READ`(MariaDB 기본값) 대신 `READ COMMITTED`를 선택한 이유:
- `REPEATABLE READ`에서는 트랜잭션 시작 시점의 스냅샷을 읽기 때문에, `FOR UPDATE`로 강좌 행을 잠근 후에도 수강 인원 조회가 오래된 스냅샷을 반환할 수 있음
- `READ COMMITTED`에서는 각 SELECT가 최신 커밋된 데이터를 읽으므로, `FOR UPDATE` 잠금을 획득한 후의 수강 인원 조회가 정확함
- `FOR UPDATE` + `READ COMMITTED` 조합은 높은 경합 시나리오에서 가장 안정적인 동시성 제어를 제공

## 4. 서버 성능 및 확장성

### 4.1 문제 정의

수강신청 시스템은 특정 시간에 수천~수만 명의 학생이 동시에 접속하는 **피크 트래픽** 패턴을 가진다. 단일 프로세스, 소규모 커넥션 풀로는 동시 접속자 증가 시 병목이 발생한다.

### 4.2 병목 분석 및 해결

#### (1) DB 커넥션 풀 부족

| 항목 | 개선 전 | 개선 후 |
|------|--------|--------|
| pool_size | 20 | 50 |
| max_overflow | 10 | 30 |
| pool_recycle | 3600s | 1800s |
| pool_timeout | 없음 | 10s |
| pool_pre_ping | 없음 | 활성화 |

- `pool_pre_ping=True`: 사용 전 커넥션 상태를 확인하여 끊어진 연결로 인한 오류 방지
- `pool_timeout=10s`: 커넥션을 얻지 못하면 빠르게 실패하여 사용자에게 즉시 피드백
- 모든 설정을 환경변수로 관리 가능 (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW` 등)

#### (2) 단일 프로세스 병목 (GIL)

Python의 GIL(Global Interpreter Lock)로 인해 단일 프로세스에서는 CPU 코어 1개만 활용 가능.

**해결**: Gunicorn 멀티 워커 배포

```bash
# 프로덕션 실행
PYTHONPATH=src gunicorn app.main:app -c gunicorn.conf.py
```

| 설정 | 값 | 근거 |
|------|-----|------|
| workers | `min(CPU * 2 + 1, 8)` | CPU 바운드 + I/O 바운드 혼합 작업에 최적 |
| worker_class | UvicornWorker | 비동기 ASGI 지원 |
| max_requests | 2000 + 지터 | 메모리 누수 방지를 위한 워커 재활용 |
| timeout | 60s | 느린 요청이 워커를 점유하지 않도록 제한 |

### 4.3 성능 테스트 결과 요약

부하 테스트(`tests/test_load.py`) 실행 결과:

| 시나리오 | 동시 요청 | 처리량 | P95 지연 | 오류 |
|---------|----------|--------|---------|------|
| 읽기 (강좌 조회) | 500 | 1,195 rps | 386 ms | 0 |
| 쓰기 (수강신청, 정원=1) | 500 | 746 rps | 591 ms | 0 |
| 혼합 (80%읽기, 20%쓰기) | 200 | 580 rps | - | 0 |

**핵심 결론**: 단일 프로세스에서 500건 동시 요청을 무결성 위반 없이 처리. 멀티 워커 시 1,000~2,000명 동시 접속 가능.

상세 결과는 [LOAD_TEST_REPORT.md](LOAD_TEST_REPORT.md) 참조.

## 5. 매크로 방지 대책

### 5.1 문제 정의

수강신청 시스템의 가장 큰 위협은 **매크로(자동화 스크립트)**를 사용하는 학생이다. 매크로는 수강신청 시작 시점에 밀리초 단위로 반복 요청을 보내어:
- 정상 사용자보다 압도적으로 빠르게 신청을 시도
- 서버 리소스를 독점하여 다른 학생의 접근을 방해
- 공정한 수강신청 환경을 훼손

### 5.2 방어 전략

3단계 방어 체계를 구현하였다.

#### (1) JWT 기반 인증 (`app/auth.py`)

| 대책 | 효과 |
|------|------|
| 학번으로 로그인 → JWT 토큰 발급 | 인증되지 않은 요청 차단 |
| 토큰에서 student_id 추출 | 다른 학생 사칭 불가 |
| 토큰 만료 시간 (60분) | 탈취된 토큰의 악용 시간 제한 |

#### (2) 학생별 Rate Limiting (`app/rate_limiter.py`)

슬라이딩 윈도우 기반의 학생별 요청 제한:

| 파라미터 | 값 | 설명 |
|---------|-----|------|
| max_requests | 5 | 10초 내 최대 요청 수 |
| window_seconds | 10.0 | 슬라이딩 윈도우 크기 |
| min_interval_seconds | 1.0 | 연속 요청 간 최소 대기 시간 |

**동작 방식**:
- 학생별로 요청 타임스탬프를 기록
- 윈도우 내 요청 수가 `max_requests`를 초과하면 **429 Too Many Requests** 반환
- 이전 요청과의 간격이 `min_interval_seconds` 미만이면 즉시 거부
- 정상적인 수동 요청(클릭 후 1~2초 대기)은 영향 없음

#### (3) 반복 실패 차단

| 파라미터 | 값 | 설명 |
|---------|-----|------|
| max_failures | 10 | 연속 실패 허용 횟수 |
| block_duration_seconds | 30.0 | 차단 지속 시간 |

**동작 방식**:
- 수강신청 실패(정원 초과, 중복 등) 시 실패 카운터 증가
- 연속 10회 실패 시 해당 학생을 30초간 일시 차단
- 성공 시 실패 카운터 초기화
- 매크로가 빈 강좌를 무차별 시도하는 패턴을 차단

### 5.3 매크로 vs 정상 사용자 시나리오

| 행동 패턴 | 정상 사용자 | 매크로 |
|----------|-----------|--------|
| 요청 간격 | 2~10초 (클릭, 확인, 클릭) | 10~100ms (밀리초 단위 반복) |
| 10초 내 요청 수 | 1~3회 | 100회 이상 |
| 실패 후 행동 | 다른 강좌 탐색 | 즉시 재시도 |
| **Rate Limiter 결과** | **통과** | **차단 (429)** |

### 5.4 향후 확장 가능한 추가 대책

현재 구현에 포함되지 않았으나, 필요 시 적용 가능한 추가 방어:

| 대책 | 설명 |
|------|------|
| Redis 기반 Rate Limiting | 멀티 프로세스/서버 환경에서 상태 공유 |
| CAPTCHA | 의심스러운 요청 시 사람 인증 요구 |
| IP 기반 제한 | 동일 IP에서의 과도한 요청 차단 |
| 수강신청 시작 시간 랜덤화 | 학과별로 시작 시간을 분산하여 피크 완화 |
| 대기열(Queue) 시스템 | 선착순 대신 추첨 또는 대기열 기반 공정 배분 |

## 6. 인증/인가

### 6.1 인증 흐름

```
학생 ──POST /auth/login──> JWT 토큰 발급
                                │
학생 ──POST /enrollments──> Authorization: Bearer <token>
         │                        │
         └── student_id 검증 ──> 토큰의 student_id와 요청 body의 student_id 일치 확인
```

- 수강신청(`POST /enrollments`)과 수강취소(`DELETE /enrollments/{id}`)는 JWT 인증 필수
- 조회 API(강좌, 학생, 교수, 시간표)는 인증 불요
- 학생은 본인의 수강신청만 등록/취소 가능 (타인 사칭 불가)

## 7. API 설계 원칙

- **RESTful**: 리소스 중심 URL, 적절한 HTTP 메서드
- **일관된 에러 응답**: `{"detail": "에러 메시지"}` 형식
- **페이지네이션**: 학생 목록은 `page`, `size` 파라미터로 페이지네이션
- **필터링**: 학과별 필터 (`department_id` 쿼리 파라미터)
- **자동 문서화**: FastAPI의 OpenAPI (Swagger UI at `/docs`)

## 8. 데이터 시딩 전략

- **프로그래밍 방식 생성**: 정적 SQL/CSV 파일이 아닌 코드에서 생성
- **결정적 시드**: `random.Random(42)` — 매번 동일한 데이터 생성
- **멱등성**: 이미 데이터가 존재하면 건너뛰기
- **배치 삽입**: 1,000건씩 일괄 삽입으로 성능 확보
- **현실적 데이터**: 한국어 이름, 실제 학과/강좌명, 현실적 시간표
