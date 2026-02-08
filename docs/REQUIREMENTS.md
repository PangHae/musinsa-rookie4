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

## 4. API 설계 원칙

- **RESTful**: 리소스 중심 URL, 적절한 HTTP 메서드
- **일관된 에러 응답**: `{"detail": "에러 메시지"}` 형식
- **페이지네이션**: 학생 목록은 `page`, `size` 파라미터로 페이지네이션
- **필터링**: 학과별 필터 (`department_id` 쿼리 파라미터)
- **자동 문서화**: FastAPI의 OpenAPI (Swagger UI at `/docs`)

## 5. 데이터 시딩 전략

- **프로그래밍 방식 생성**: 정적 SQL/CSV 파일이 아닌 코드에서 생성
- **결정적 시드**: `random.Random(42)` — 매번 동일한 데이터 생성
- **멱등성**: 이미 데이터가 존재하면 건너뛰기
- **배치 삽입**: 1,000건씩 일괄 삽입으로 성능 확보
- **현실적 데이터**: 한국어 이름, 실제 학과/강좌명, 현실적 시간표
