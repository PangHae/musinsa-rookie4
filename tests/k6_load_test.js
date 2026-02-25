/**
 * k6 부하 테스트 — 실제 HTTP (TCP/IP → localhost:8000)
 *
 * 전제조건:
 *   1. 서버가 테스트 DB로 실행 중:
 *      DB_NAME=course_registration_test uvicorn app.main:app --host 0.0.0.0 --port 8000
 *   2. k6 설치됨: brew install k6
 *
 * 실행:
 *   k6 run tests/k6_load_test.js --summary-export=k6_summary.json
 *
 * 시나리오:
 *   - read_load    : 100 VUs × 30초, GET /courses
 *   - write_concurrency: 100 VUs × 1회, POST /enrollments (동시성 테스트)
 *   - mixed_load   : 100 VUs × 20초, 80% READ / 20% WRITE
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// 커스텀 메트릭
const writeSuccessRate = new Rate('write_success_rate');
const readLatency     = new Trend('read_latency',  true);
const writeLatency    = new Trend('write_latency', true);

export const options = {
  scenarios: {
    // 시나리오 1: READ 부하 (100 VUs, 30초)
    read_load: {
      executor:  'constant-vus',
      vus:       100,
      duration:  '30s',
      exec:      'readScenario',
      startTime: '0s',
    },
    // 시나리오 2: WRITE 동시성 (100 VUs, 각 1회 — 동시에 신청)
    write_concurrency: {
      executor:   'shared-iterations',
      vus:        100,
      iterations: 100,
      maxDuration:'30s',
      exec:       'writeScenario',
      startTime:  '35s',  // read 종료 후 5초 뒤 시작
    },
    // 시나리오 3: MIXED (100 VUs, 20초, 80/20)
    mixed_load: {
      executor:  'constant-vus',
      vus:       100,
      duration:  '20s',
      exec:      'mixedScenario',
      startTime: '70s',  // write 종료 후
    },
  },
  thresholds: {
    // 리포트용 기준치 (실패해도 테스트는 계속)
    http_req_duration: ['p(95)<2000'],
    http_req_failed:   ['rate<0.5'],
  },
};

// ─── setup: 학생 토큰 취득 ─────────────────────────────────────────────────
export function setup() {
  const tokens = [];

  // S00001 ~ S00100 로그인
  for (let i = 1; i <= 100; i++) {
    const studentNumber = `S${String(i).padStart(5, '0')}`;
    const res = http.post(
      `${BASE_URL}/auth/login`,
      JSON.stringify({ student_number: studentNumber }),
      { headers: { 'Content-Type': 'application/json' } }
    );

    if (res.status === 200) {
      const body = JSON.parse(res.body);
      tokens.push({
        token:      body.access_token,
        student_id: body.student_id,
      });
    } else {
      console.warn(`Login failed for ${studentNumber}: ${res.status} ${res.body}`);
    }
  }

  console.log(`Setup complete: ${tokens.length}/100 tokens acquired`);
  return { tokens };
}

// ─── 시나리오 1: READ ──────────────────────────────────────────────────────
export function readScenario() {
  const start = Date.now();
  const res = http.get(`${BASE_URL}/courses`);
  readLatency.add(Date.now() - start);

  check(res, {
    'read status 200': (r) => r.status === 200,
  });
}

// ─── 시나리오 2: WRITE 동시성 ─────────────────────────────────────────────
export function writeScenario(data) {
  // VU 인덱스로 토큰 선택 (0-based)
  const idx = (__VU - 1) % data.tokens.length;
  const { token, student_id } = data.tokens[idx];

  const start = Date.now();
  const res = http.post(
    `${BASE_URL}/enrollments`,
    JSON.stringify({ student_id: student_id, course_id: 1 }),
    {
      headers: {
        'Content-Type':  'application/json',
        'Authorization': `Bearer ${token}`,
      },
    }
  );
  writeLatency.add(Date.now() - start);

  const success = res.status === 201;
  writeSuccessRate.add(success);

  check(res, {
    'write 201 or expected failure': (r) => [201, 400, 409, 422, 429].includes(r.status),
  });
}

// ─── 시나리오 3: MIXED ────────────────────────────────────────────────────
export function mixedScenario(data) {
  // 80% read, 20% write
  if (Math.random() < 0.8) {
    readScenario();
  } else {
    writeScenario(data);
  }
  sleep(0.1);
}
