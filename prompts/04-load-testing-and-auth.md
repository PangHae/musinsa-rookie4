# Prompt 04: Load Testing, Performance Optimization, and Authentication

## Request

1. **Server Performance Optimization**: Focus on connection pool sizing and single-process bottleneck. Ensure the server can withstand high concurrent load.

2. **Load Test Code & Report**: Write load test code and execute actual tests. Produce a report documenting how many concurrent users and simultaneous API calls the server can handle. Place the report in `docs/`.

3. **Authentication/Authorization**: Add an auth layer so that the same student cannot call the same API endpoint multiple times impersonating others. Prevent unauthorized access to enrollment/cancellation endpoints.

4. **Prompt Logging**: Log this prompt to the `prompts/` directory in English.

5. **Commit**: Commit all completed code changes.

## Changes Made

### Performance Optimization
- Increased DB connection pool: `pool_size=50`, `max_overflow=30` (was 20/10)
- Added `pool_pre_ping=True` for connection health checks
- Added `pool_timeout=10s` to fail fast under load
- Made pool settings configurable via environment variables
- Added `gunicorn.conf.py` for multi-worker production deployment
- Added `gunicorn` to dependencies

### Authentication
- Added JWT-based authentication (`app/auth.py`)
- Added login endpoint `POST /auth/login` (authenticate by student_number)
- Protected `POST /enrollments` and `DELETE /enrollments/{id}` with JWT
- Student ID extracted from JWT token — students can only register/cancel for themselves
- Added ownership validation on enrollment cancellation

### Load Testing
- Created `tests/test_load.py` with three test scenarios:
  - Read throughput at 10/50/100/200/500 concurrent requests
  - Write throughput with pessimistic locking under contention
  - Mixed workload (80% read, 20% write)
- Generated `docs/LOAD_TEST_REPORT.md` with actual benchmark results

### Test Updates
- Updated `tests/test_enrollments.py` to include JWT auth headers
- Added new test cases: `test_register_without_auth`, `test_register_for_another_student`, `test_cancel_another_students_enrollment`
- All 24 tests passing
