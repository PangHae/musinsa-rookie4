# 대학교 수강신청 시스템

대학교 수강신청 REST API 백엔드 시스템입니다.

## 기술 스택

- **Language**: Python 3.13
- **Framework**: FastAPI
- **Database**: MariaDB
- **ORM**: SQLAlchemy (async, aiomysql)
- **Cache / Rate Limiting**: Redis

## 사전 요구사항

- Python 3.13+
- MariaDB 10.6+
- Redis 6.0+ (멀티 워커 Rate Limiting에 필요)

## 설치 및 실행

### 1. Redis 실행

```bash
docker run -d -p 6379:6379 redis:latest
```

### 2. 데이터베이스 생성

```sql
CREATE DATABASE course_registration CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

테스트용 DB (선택):
```sql
CREATE DATABASE course_registration_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 3. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일을 편집하여 DB 및 Redis 접속 정보를 설정합니다
```

주요 환경변수:

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DB_HOST` | `localhost` | MariaDB 호스트 |
| `DB_PORT` | `3306` | MariaDB 포트 |
| `DB_USER` | — | DB 사용자 |
| `DB_PASSWORD` | — | DB 비밀번호 |
| `DB_NAME` | `course_registration` | DB 이름 |
| `JWT_SECRET` | **(필수)** | JWT 서명 시크릿 (미설정 시 서버 기동 불가) |
| `REDIS_URL` | `redis://localhost:6379` | Redis 연결 URL |

### 4. 의존성 설치

```bash
pip install -r requirements.txt
```

### 5. 서버 실행

개발 모드 (단일 프로세스):
```bash
PYTHONPATH=src uvicorn app.main:app --host 0.0.0.0 --port 8000
```

프로덕션 모드 (멀티 워커):
```bash
PYTHONPATH=src gunicorn app.main:app -c gunicorn.conf.py
```

서버 시작 시 자동으로:
- 데이터베이스 테이블 생성
- 초기 데이터 시딩 (15개 학과, 510개 강좌, 10,000명 학생, 105명 교수)

### 6. 확인

- Health Check: http://localhost:8000/health
- Swagger UI: http://localhost:8000/docs

## 서버 포트

**8000** (기본값)

## 인증

수강신청/취소 API는 JWT 인증이 필요합니다.

```bash
# 1. 로그인 (학번으로 인증)
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"student_number": "S00001"}'

# 2. 반환된 access_token으로 수강신청
curl -X POST http://localhost:8000/enrollments \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"student_id": 1, "course_id": 1}'
```

## 테스트 실행

```bash
pytest tests/ -v
```

동시성 테스트만 실행:
```bash
pytest tests/test_concurrency.py -v
```

부하 테스트:
```bash
pytest tests/test_load.py -v -s
```

## API 문서

상세 API 명세는 [docs/API.md](docs/API.md)를 참조하세요.

## Rate Limiting

멀티 워커(gunicorn) 환경에서의 정확한 Rate Limiting을 위해 Redis를 사용합니다.

- **방식**: 슬라이딩 윈도우 (Redis Sorted Set)
- **기본 설정**: 10초에 최대 5회 요청, 연속 요청 간격 1초 이상
- **멀티 워커**: 모든 워커가 Redis 상태를 공유하여 정확한 제한 적용

상세 내용: [docs/redis/comparison-report.md](docs/redis/comparison-report.md)

## 설계 문서

요구사항 분석 및 설계 결정은 [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md)를 참조하세요.
