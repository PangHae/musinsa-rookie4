# 대학교 수강신청 시스템

대학교 수강신청 REST API 백엔드 시스템입니다.

## 기술 스택

- **Language**: Python 3.13
- **Framework**: FastAPI
- **Database**: MariaDB
- **ORM**: SQLAlchemy (async, aiomysql)

## 사전 요구사항

- Python 3.13+
- MariaDB 10.6+

## 설치 및 실행

### 1. 데이터베이스 생성

```sql
CREATE DATABASE course_registration CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

테스트용 DB (선택):
```sql
CREATE DATABASE course_registration_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일을 편집하여 DB 접속 정보를 설정합니다
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. 서버 실행

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

서버 시작 시 자동으로:
- 데이터베이스 테이블 생성
- 초기 데이터 시딩 (15개 학과, 510개 강좌, 10,000명 학생, 105명 교수)

### 5. 확인

- Health Check: http://localhost:8000/health
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 서버 포트

**8000** (기본값)

## 테스트 실행

```bash
pytest tests/ -v
```

동시성 테스트만 실행:
```bash
pytest tests/test_concurrency.py -v
```

## API 문서

상세 API 명세는 [docs/API.md](docs/API.md)를 참조하세요.

## 설계 문서

요구사항 분석 및 설계 결정은 [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md)를 참조하세요.
