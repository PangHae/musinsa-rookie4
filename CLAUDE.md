# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

University course registration system (대학교 수강신청 시스템) — a REST API backend.
The core challenge is **concurrency control**: when 100 students simultaneously register for a course with 1 seat remaining, exactly 1 must succeed. No capacity overflows allowed.

Requirements document: `docs/PROBLEM.md`

## Tech Stack

- **Language**: Python 3.13
- **Framework**: FastAPI (async, auto-generated OpenAPI/Swagger at `/docs`)
- **Database**: MariaDB
- **ORM**: SQLAlchemy (async)
- **Package Manager**: pip with `requirements.txt`

## Prompt Logging

Every user request prompt must be logged to `prompts/` directory as markdown files. This is a required deliverable for evaluation.

## Key Business Rules

- Max 18 credits per student per semester
- No schedule conflicts (same time slot, two courses)
- Course capacity must never be exceeded (concurrency-critical)
- Data seeded at startup: 10+ departments, 500+ courses, 10,000+ students, 100+ professors
- Data must be generated programmatically (no static SQL/CSV dumps)
- Health check: `GET /health` → 200 OK (must respond within 1 minute of server start)

## Required API Endpoints

- `GET /health` — health check (required)
- Student list query
- Course list query (all, by department — includes capacity/enrolled/schedule)
- Professor list query
- Course registration (수강신청)
- Course cancellation (수강취소)
- My timetable query (이번 학기)

## Required Documents

| File | Purpose |
|------|---------|
| `README.md` | Build & run instructions, server port |
| `docs/REQUIREMENTS.md` | Requirement analysis, design decisions, concurrency strategy |
| `docs/` API doc | Full API spec (request/response formats, error codes) |
| `prompts/*.md` | AI prompt history |

## Commit Message Convention
check `docs/COMMIT_MESSAGE`

## Concurrency Control (Critical)

The concurrency strategy must be documented in `docs/REQUIREMENTS.md`. Options to consider:
- Database-level: `SELECT ... FOR UPDATE` (pessimistic locking), optimistic locking with version column
- Application-level: in-memory locks (only works single-process)
- Transaction isolation levels

This will be tested with simultaneous request scenarios during evaluation.

## Evaluation Priority (highest weight first)

1. **Works**: builds, runs, health check responds
2. **Core features**: business rules + concurrency correctness
3. **Depth**: AI usage quality, design docs, code quality, tests, git history