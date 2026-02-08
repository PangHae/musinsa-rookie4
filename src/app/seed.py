import random

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.course_schedule import CourseSchedule
from app.models.department import Department
from app.models.enrollment import Enrollment
from app.models.professor import Professor
from app.models.student import Student

# Korean name pools
SURNAMES = [
    "김", "이", "박", "최", "정", "강", "조", "윤", "장", "임",
    "한", "오", "서", "신", "권", "황", "안", "송", "류", "홍",
]

GIVEN_SYLLABLES_1 = [
    "민", "서", "지", "현", "수", "은", "도", "영", "준", "예",
    "하", "우", "태", "성", "진", "유", "승", "재", "시", "연",
]

GIVEN_SYLLABLES_2 = [
    "준", "아", "호", "우", "빈", "경", "율", "석", "원", "혁",
    "린", "규", "진", "미", "정", "환", "찬", "희", "윤", "기",
]

DEPARTMENTS = [
    ("컴퓨터공학과", "CS"),
    ("전자공학과", "EE"),
    ("기계공학과", "ME"),
    ("화학공학과", "CE"),
    ("건축공학과", "AE"),
    ("경영학과", "BA"),
    ("경제학과", "EC"),
    ("수학과", "MA"),
    ("물리학과", "PH"),
    ("화학과", "CH"),
    ("생명과학과", "LS"),
    ("영어영문학과", "EN"),
    ("국어국문학과", "KR"),
    ("심리학과", "PS"),
    ("사회학과", "SO"),
]

COURSE_NAMES = {
    "CS": [
        "프로그래밍기초", "자료구조", "알고리즘", "운영체제", "컴퓨터네트워크",
        "데이터베이스", "소프트웨어공학", "컴퓨터구조", "인공지능", "기계학습",
        "웹프로그래밍", "모바일프로그래밍", "정보보안", "클라우드컴퓨팅", "빅데이터분석",
        "컴파일러", "분산시스템", "컴퓨터그래픽스", "자연어처리", "딥러닝",
        "블록체인기초", "사물인터넷", "디지털논리설계", "임베디드시스템", "고급프로그래밍",
        "객체지향프로그래밍", "함수형프로그래밍", "병렬컴퓨팅", "소프트웨어테스팅",
        "프로젝트관리", "UI/UX설계", "게임프로그래밍", "로보틱스", "강화학습",
    ],
    "EE": [
        "회로이론", "전자기학", "신호와시스템", "전력전자", "반도체공학",
        "통신공학", "제어공학", "디지털신호처리", "전자회로", "마이크로프로세서",
        "VLSI설계", "안테나공학", "광전자공학", "전력시스템", "로봇공학",
        "센서공학", "전자재료", "아날로그회로설계", "RF공학", "전기기기",
        "디스플레이공학", "에너지변환공학", "자동제어", "전자계측", "전파공학",
        "임베디드제어", "통신이론", "전자기파", "회로설계실습", "반도체소자",
        "전력변환", "디지털시스템설계", "무선통신", "광통신",
    ],
    "ME": [
        "열역학", "유체역학", "재료역학", "동역학", "기계설계",
        "제조공학", "열전달", "진동학", "자동차공학", "에너지공학",
        "CAD/CAM", "로봇공학개론", "유한요소법", "기계가공", "메카트로닉스",
        "항공역학", "냉동공조", "터보기계", "기계진동", "제어시스템",
        "재료과학", "기계제도", "기계요소설계", "유압공학", "공업수학",
        "기구학", "생산시스템", "응력해석", "기계실험", "소음진동",
        "열공학설계", "유동해석", "기계재료", "나노기계",
    ],
    "CE": [
        "화학공학개론", "반응공학", "분리공정", "열역학", "유체역학",
        "공정제어", "촉매공학", "고분자공학", "생물화학공학", "환경공학",
        "화학공정설계", "전기화학", "나노소재", "공정시뮬레이션", "에너지화학",
        "석유화학", "식품공학", "약품제조", "화장품공학", "섬유공학",
        "화학분석", "물질전달", "반응속도론", "공정경제", "안전공학",
        "폐수처리", "대기오염", "유기화학", "무기화학", "화학실험",
        "고분자재료", "생체재료", "표면화학", "수처리공학",
    ],
    "AE": [
        "건축설계", "구조역학", "건축환경", "건축시공", "건축재료",
        "철근콘크리트", "강구조", "건축CAD", "도시계획", "건축법규",
        "지반공학", "측량학", "건설관리", "내진설계", "친환경건축",
        "건축음향", "조경설계", "건축설비", "인테리어설계", "BIM설계",
        "건축역사", "건축디자인", "구조설계실습", "건축적산", "건설안전",
        "토질역학", "수리학", "교통공학", "상하수도", "콘크리트공학",
        "기초공학", "건축계획", "건축미학", "스마트건축",
    ],
    "BA": [
        "경영학원론", "마케팅", "재무관리", "인사관리", "경영전략",
        "회계원리", "경영정보시스템", "생산관리", "조직행동론", "국제경영",
        "소비자행동", "브랜드관리", "투자론", "기업재무", "경영분석",
        "광고론", "유통관리", "벤처경영", "e-비즈니스", "서비스경영",
        "리더십", "협상론", "프로젝트경영", "공급망관리", "품질경영",
        "경영통계", "원가관리", "세무회계", "경영시뮬레이션", "창업론",
        "디지털마케팅", "데이터경영", "ESG경영", "기업윤리",
    ],
    "EC": [
        "경제학원론", "미시경제학", "거시경제학", "계량경제학", "국제경제학",
        "화폐금융론", "재정학", "산업조직론", "노동경제학", "경제수학",
        "경제통계학", "한국경제론", "경제사", "발전경제학", "환경경제학",
        "행동경제학", "게임이론", "공공경제학", "도시경제학", "금융경제학",
        "경제정책론", "국제금융론", "무역학", "정보경제학", "법경제학",
        "경제성장론", "경제예측", "경매이론", "복지경제학", "자원경제학",
        "부동산경제", "농업경제", "의료경제", "디지털경제",
    ],
    "MA": [
        "미적분학", "선형대수학", "해석학", "대수학", "위상수학",
        "확률론", "통계학", "수치해석", "미분방정식", "복소해석",
        "이산수학", "정수론", "기하학", "조합론", "최적화이론",
        "편미분방정식", "함수해석", "다변수해석", "응용수학", "수리통계",
        "금융수학", "암호학", "그래프이론", "수학교육론", "프랙탈기하",
        "행렬론", "집합론", "논리학", "수학사", "계산수학",
        "확률과정론", "비선형동역학", "수리물리", "데이터과학수학",
    ],
    "PH": [
        "일반물리학", "역학", "전자기학", "양자역학", "열통계물리",
        "광학", "현대물리", "고체물리", "핵물리", "입자물리",
        "천체물리", "유체물리", "플라즈마물리", "물리수학", "상대론",
        "반도체물리", "나노물리", "생물물리", "전산물리", "음향학",
        "레이저물리", "비선형물리", "초전도물리", "표면물리", "물리실험",
        "양자광학", "물질과학", "에너지물리", "우주론", "중력이론",
        "양자정보", "물리교육", "분자물리", "통계역학",
    ],
    "CH": [
        "일반화학", "유기화학", "무기화학", "물리화학", "분석화학",
        "생화학", "고분자화학", "환경화학", "전기화학", "양자화학",
        "유기합성", "촉매화학", "나노화학", "약품화학", "재료화학",
        "화학열역학", "분광학", "결정학", "계산화학", "식품화학",
        "화학실험", "화학세미나", "천연물화학", "금속유기화학", "광화학",
        "핵화학", "표면화학", "콜로이드화학", "화학교육", "산업화학",
        "의약화학", "농약화학", "고체화학", "화학특론",
    ],
    "LS": [
        "일반생물학", "세포생물학", "분자생물학", "유전학", "생태학",
        "미생물학", "동물학", "식물학", "생리학", "발생학",
        "진화생물학", "면역학", "바이러스학", "생물정보학", "신경과학",
        "줄기세포학", "암생물학", "생물통계", "유전공학", "단백질공학",
        "생물다양성", "해양생물학", "생물화학", "약리학", "독성학",
        "환경생물학", "생물실험", "동물행동학", "비교해부학", "식물생리학",
        "곤충학", "수산생물학", "생태계관리", "생물교육",
    ],
    "EN": [
        "영어학개론", "영문학개론", "영작문", "영어회화", "영어음성학",
        "영어통사론", "영어의미론", "영미소설", "영미시", "영미희곡",
        "번역이론", "영어교육론", "비즈니스영어", "미디어영어", "영어담화분석",
        "셰익스피어", "미국문학사", "영국문학사", "비교문학", "문학비평",
        "응용언어학", "사회언어학", "심리언어학", "코퍼스언어학", "영어발달사",
        "영한번역", "한영번역", "통역입문", "학술영어", "프레젠테이션영어",
        "아동문학", "현대영미소설", "영어문체론", "다문화영어",
    ],
    "KR": [
        "국어학개론", "국문학개론", "현대소설", "현대시", "고전소설",
        "고전시가", "국어음운론", "국어문법론", "국어의미론", "한국문학사",
        "창작실습", "문예비평", "국어교육론", "아동문학", "구비문학",
        "한문학", "글쓰기", "화법과작문", "미디어국어", "한국어교육",
        "방언학", "사회언어학", "국어정책론", "국어사", "문학과사회",
        "서사이론", "시론", "소설론", "수필론", "비교문학",
        "고전문법", "현대문법", "텍스트언어학", "디지털인문학",
    ],
    "PS": [
        "심리학개론", "발달심리학", "사회심리학", "인지심리학", "임상심리학",
        "성격심리학", "생리심리학", "심리통계", "심리측정", "상담심리학",
        "학습심리학", "지각심리학", "심리학연구법", "조직심리학", "범죄심리학",
        "건강심리학", "교육심리학", "소비자심리학", "스포츠심리학", "문화심리학",
        "노인심리학", "아동심리학", "가족심리학", "중독심리학", "신경심리학",
        "긍정심리학", "동기심리학", "감정심리학", "미디어심리학", "환경심리학",
        "법심리학", "심리치료", "집단상담", "심리학특강",
    ],
    "SO": [
        "사회학개론", "사회조사방법론", "사회통계학", "사회이론", "문화사회학",
        "정치사회학", "경제사회학", "도시사회학", "농촌사회학", "환경사회학",
        "가족사회학", "교육사회학", "종교사회학", "의료사회학", "범죄사회학",
        "미디어사회학", "정보사회학", "젠더와사회", "인구학", "사회복지론",
        "사회운동론", "노동사회학", "국제사회학", "비교사회학", "한국사회론",
        "사회심리학", "사회정책론", "사회계층론", "사회변동론", "지역사회학",
        "소비사회학", "과학기술사회학", "복지국가론", "사회학특강",
    ],
}

TIME_SLOTS = [
    ("09:00", "10:15"),
    ("10:30", "11:45"),
    ("12:00", "13:15"),
    ("13:30", "14:45"),
    ("15:00", "16:15"),
    ("16:30", "17:45"),
]

WEEKDAYS = ["월", "화", "수", "목", "금"]


def _generate_name(rng: random.Random) -> str:
    return rng.choice(SURNAMES) + rng.choice(GIVEN_SYLLABLES_1) + rng.choice(GIVEN_SYLLABLES_2)


async def seed_database(session: AsyncSession) -> None:
    """Seed the database with initial data. Idempotent — skips if data exists."""
    result = await session.execute(select(Department.id).limit(1))
    if result.scalar_one_or_none() is not None:
        return

    rng = random.Random(42)  # deterministic seed

    # 1. Departments
    dept_rows = [
        {"name": name, "code": code} for name, code in DEPARTMENTS
    ]
    await session.execute(insert(Department), dept_rows)
    await session.flush()

    # Fetch department IDs
    dept_result = await session.execute(select(Department.id, Department.code))
    dept_map = {code: id_ for id_, code in dept_result.all()}

    # 2. Professors (7 per department = 105 total)
    prof_rows = []
    prof_counter = 1
    for code, dept_id in dept_map.items():
        for i in range(7):
            prof_rows.append({
                "name": _generate_name(rng),
                "employee_number": f"P{prof_counter:04d}",
                "department_id": dept_id,
            })
            prof_counter += 1
    await session.execute(insert(Professor), prof_rows)
    await session.flush()

    # Fetch professor IDs grouped by department
    prof_result = await session.execute(
        select(Professor.id, Professor.department_id)
    )
    dept_profs: dict[int, list[int]] = {}
    for pid, did in prof_result.all():
        dept_profs.setdefault(did, []).append(pid)

    # 3. Courses (34 per department ≈ 510 total)
    course_rows = []
    course_counter = 1
    course_meta = []  # track (code, dept_id, prof_id) for schedule generation

    for code, dept_id in dept_map.items():
        names = COURSE_NAMES[code]
        profs = dept_profs[dept_id]
        for i, name in enumerate(names):
            prof_id = profs[i % len(profs)]
            course_code = f"{code}{course_counter:04d}"
            credits = rng.choice([2, 3, 3, 3, 3, 4])  # mostly 3 credits
            capacity = rng.choice([30, 30, 40, 40, 50, 60])
            course_rows.append({
                "name": name,
                "code": course_code,
                "credits": credits,
                "capacity": capacity,
                "department_id": dept_id,
                "professor_id": prof_id,
            })
            course_meta.append(course_code)
            course_counter += 1

    await session.execute(insert(Course), course_rows)
    await session.flush()

    # Fetch course IDs
    course_result = await session.execute(select(Course.id, Course.code))
    course_id_map = {code: id_ for id_, code in course_result.all()}

    # 4. Course schedules (1-2 days per course)
    schedule_rows = []
    for code in course_meta:
        course_id = course_id_map[code]
        slot = rng.choice(TIME_SLOTS)
        num_days = rng.choice([1, 2, 2, 2])  # usually 2 days
        days = rng.sample(WEEKDAYS, num_days)
        for day in days:
            schedule_rows.append({
                "course_id": course_id,
                "day_of_week": day,
                "start_time": slot[0],
                "end_time": slot[1],
            })

    # Batch insert schedules
    for i in range(0, len(schedule_rows), 1000):
        await session.execute(insert(CourseSchedule), schedule_rows[i:i + 1000])
    await session.flush()

    # 5. Students (10,000)
    student_rows = []
    for i in range(1, 10001):
        dept_id = rng.choice(list(dept_map.values()))
        year = rng.choice([1, 1, 2, 2, 3, 3, 4])
        student_rows.append({
            "name": _generate_name(rng),
            "student_number": f"S{i:05d}",
            "year": year,
            "department_id": dept_id,
        })

    # Batch insert students
    for i in range(0, len(student_rows), 1000):
        await session.execute(insert(Student), student_rows[i:i + 1000])

    await session.commit()
