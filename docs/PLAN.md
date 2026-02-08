# Implementation Plan

## Phase 1: Foundation
- FastAPI project setup, health check, DB connection

## Phase 2: Data Models + Seeding
- 6 tables: Department, Professor, Course, CourseSchedule, Student, Enrollment
- Seed data generation (15 depts, 105 profs, 510 courses, 10K students)

## Phase 3: Read-only Endpoints
- GET /departments
- GET /professors (filter by department)
- GET /courses (with enrolled count, schedules, filter by department)
- GET /students (paginated, filter by department)

## Phase 4: Registration + Cancellation
- POST /enrollments — with pessimistic locking (SELECT FOR UPDATE)
- DELETE /enrollments/{id}
- Business rules: capacity, duplicate, credit limit (18), schedule conflict

## Phase 5: Timetable
- GET /students/{id}/timetable

## Phase 6: Documentation
- README.md, docs/REQUIREMENTS.md, docs/API.md

## Phase 7: Testing
- Unit tests for all endpoints
- Concurrency test: 100 simultaneous registrations for capacity=1 course

## Phase 8: Polish
- SeedMiddleware for auto data initialization
- Error handling, input validation
- Git commit history
