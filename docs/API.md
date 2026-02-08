# API 명세서

Base URL: `http://localhost:8000`

Swagger UI: `http://localhost:8000/docs`

---

## 1. Health Check

### `GET /health`

서버 상태 확인

**Response** `200 OK`
```json
{
  "status": "ok"
}
```

---

## 2. 학과 (Departments)

### `GET /departments`

전체 학과 목록 조회

**Response** `200 OK`
```json
[
  {
    "id": 1,
    "name": "컴퓨터공학과",
    "code": "CS"
  }
]
```

---

## 3. 교수 (Professors)

### `GET /professors`

교수 목록 조회

**Query Parameters**
| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| department_id | int | N | 학과 ID로 필터링 |

**Response** `200 OK`
```json
[
  {
    "id": 1,
    "name": "김민준",
    "employee_number": "P0001",
    "department_id": 1,
    "department_name": "컴퓨터공학과"
  }
]
```

---

## 4. 강좌 (Courses)

### `GET /courses`

강좌 목록 조회 (수강 인원, 시간표 포함)

**Query Parameters**
| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| department_id | int | N | 학과 ID로 필터링 |

**Response** `200 OK`
```json
[
  {
    "id": 1,
    "name": "프로그래밍기초",
    "code": "CS0001",
    "credits": 3,
    "capacity": 40,
    "enrolled": 15,
    "department_id": 1,
    "department_name": "컴퓨터공학과",
    "professor_id": 1,
    "professor_name": "김민준",
    "schedules": [
      {
        "day_of_week": "월",
        "start_time": "09:00",
        "end_time": "10:15"
      },
      {
        "day_of_week": "수",
        "start_time": "09:00",
        "end_time": "10:15"
      }
    ]
  }
]
```

---

## 5. 학생 (Students)

### `GET /students`

학생 목록 조회 (페이지네이션)

**Query Parameters**
| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| page | int | N | 1 | 페이지 번호 (1부터) |
| size | int | N | 20 | 페이지 크기 (1-100) |
| department_id | int | N | - | 학과 ID로 필터링 |

**Response** `200 OK`
```json
{
  "total": 10000,
  "page": 1,
  "size": 20,
  "items": [
    {
      "id": 1,
      "name": "박서빈",
      "student_number": "S00001",
      "year": 2,
      "department_id": 1,
      "department_name": "컴퓨터공학과"
    }
  ]
}
```

---

## 6. 수강신청 (Enrollments)

### `POST /enrollments`

수강신청

**Request Body**
```json
{
  "student_id": 1,
  "course_id": 1
}
```

**Response** `201 Created`
```json
{
  "id": 1,
  "student_id": 1,
  "course_id": 1,
  "course_name": "프로그래밍기초",
  "registered_at": "2025-01-15T10:30:00"
}
```

**Error Responses**

| 상태 코드 | 조건 | 응답 |
|-----------|------|------|
| 404 | 학생 없음 | `{"detail": "Student not found"}` |
| 404 | 강좌 없음 | `{"detail": "Course not found"}` |
| 409 | 정원 초과 | `{"detail": "Course is full"}` |
| 409 | 중복 수강 | `{"detail": "Already enrolled in this course"}` |
| 409 | 학점 초과 | `{"detail": "Credit limit exceeded (current: 15, attempting: 4, max: 18)"}` |
| 409 | 시간 충돌 | `{"detail": "Schedule conflict on 월 (09:00-10:15)"}` |
| 422 | 유효성 오류 | Pydantic validation error |

### `DELETE /enrollments/{enrollment_id}`

수강취소

**Path Parameters**
| 파라미터 | 타입 | 설명 |
|---------|------|------|
| enrollment_id | int | 수강신청 ID |

**Response** `204 No Content`

(응답 본문 없음)

**Error Responses**

| 상태 코드 | 조건 | 응답 |
|-----------|------|------|
| 404 | 수강신청 없음 | `{"detail": "Enrollment not found"}` |

---

## 7. 시간표 (Timetable)

### `GET /students/{student_id}/timetable`

학생의 이번 학기 시간표 조회

**Path Parameters**
| 파라미터 | 타입 | 설명 |
|---------|------|------|
| student_id | int | 학생 ID |

**Response** `200 OK`
```json
{
  "student_id": 1,
  "student_name": "박서빈",
  "total_credits": 9,
  "courses": [
    {
      "enrollment_id": 1,
      "course_id": 1,
      "course_name": "프로그래밍기초",
      "course_code": "CS0001",
      "credits": 3,
      "professor_name": "김민준",
      "schedules": [
        {
          "day_of_week": "월",
          "start_time": "09:00",
          "end_time": "10:15"
        }
      ]
    }
  ]
}
```

**Error Responses**

| 상태 코드 | 조건 | 응답 |
|-----------|------|------|
| 404 | 학생 없음 | `{"detail": "Student not found"}` |
