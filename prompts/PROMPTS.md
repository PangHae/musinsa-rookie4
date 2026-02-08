# Prompt History

## #initial-setup

> Please analyze this codebase and create a CLAUDE.md file, which will be given to future instances of Claude Code to operate in this repository.

> I will use fastapi for backend framework, mariadb for database, and requirements.txt for package manager. and u should log my every request prompt in /prompt directory. update CLAUDE.md first

## #implementation

> Implement the following plan:
>
> (The full Phase 1-8 implementation plan was provided — see docs/PLAN.md)

## #resume-and-finalize

> log your plan in my docs directory, and resume where you stopped because of limit

> use docker for mariadb

> use docker name bold_elbakyan for mariadb

> docker is already running check using docker ps

> check is server is runnable and every requirements are succeed. Also add middleware for creating data if not exists in database(use seed.py). this work must finished in 1 minutes. After all check list passed, commit rest of codes.

> update plan.md to initial plan that you generated. not consist by current state and remaining work. update prompts that i have really gave it to you not changed in to korean.

## #load-testing-and-auth

> is there auto data generating function if there is no middleware?

> 이 서버 여러 명이 접속했을 때 얼마나 견딜 수 있는지에 대한 내용도 고려된 서버야?

> 1. 커넥션 풀, 단일 프로세스 병목 이 두 가지를 중점으로 고려해서 성능 부하에 견딜 수 있도록 서버 코드 작성 2. 해당 내용에 대한 테스트 코드 작성 및 실제 테스트 결과 몇 명까지 동시 접속과 api 동시 호출이 가능한지 보고서를 작성해 /docs 폴더에 배치. 3. 동일 학생이 동일 api를 여러 번 호출하지 못하도록 인증/인가 단계 추가. 4. 이 내용을 prompts 폴더에 영문 형태로 추가 5. 완료된 코드 커밋

## #anti-macro-and-docs

> 1. update load_test_report in korean, also write commit body in korean. finish commiting current work. 2. 수강신청 서버의 주된 문제는 매크로를 사용하는 학생들이 많다는 것이기 때문에, 매크로 방지 대책도 서버에 적용해줘. 3. 앞서 고려한 서버 성능 문제와 현재 작성할 예정인 매크로 방지에 대해 고려한 내용을 docs/REQUIREMENTS.md에 작성. 4. 현재 프롬프트를 /prompts에 로깅. 5. 수정한 내용 커밋.

## #test-report-and-prompt-merge

> 1. docs에 test pass, fail과 관련된 문서 추가, 어떤 test에 pass하고 fail하는지, 어떤 테스트들이 있는지 작성. 2. prompts 한 개의 문서로 통합. 제목을 단계로 구분하고(ex. #initial-setup), 입력한 prompt들을 나열. 해당 프롬프트 실행을 통해 어떤 작업을 했는지는 명시하지 않기.
