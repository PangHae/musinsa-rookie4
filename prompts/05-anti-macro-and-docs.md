# Prompt 05: Anti-Macro Protection and Documentation

## Request

1. **Update load test report in Korean**, also write commit body in Korean. Finish committing current work.

2. **Anti-macro measures**: The main problem with course registration servers is students using macros (automated scripts). Apply anti-macro countermeasures to the server.

3. **Documentation**: Write about the server performance considerations and anti-macro protections in `docs/REQUIREMENTS.md`.

4. **Prompt logging**: Log this prompt to `/prompts`.

5. **Commit**: Commit all changes.

## Changes Made

### Anti-Macro Protection (`app/rate_limiter.py`)
- Sliding window rate limiter: max 5 requests per 10 seconds per student
- Minimum interval enforcement: 1 second between consecutive requests
- Failure penalty: 10 consecutive failures → 30 second temporary block
- Applied to enrollment endpoint (`POST /enrollments`)
- HTTP 429 (Too Many Requests) response when rate limited

### Documentation Updates (`docs/REQUIREMENTS.md`)
- Added Section 4: Server performance and scalability analysis
  - Connection pool optimization details
  - Multi-worker deployment strategy with Gunicorn
  - Performance test results summary
- Added Section 5: Anti-macro countermeasures
  - Problem definition (macro threat model)
  - 3-layer defense strategy (JWT auth + rate limiting + failure penalty)
  - Normal user vs macro behavior comparison
  - Future extensibility options (Redis, CAPTCHA, IP blocking, queue system)
- Added Section 6: Authentication/authorization flow

### Tests (`tests/test_rate_limiter.py`)
- 7 test cases covering all rate limiter behaviors
- Rate limit enforcement, min interval, failure penalty, success reset, per-student independence, window expiry
- All 31 tests passing
