# 히어로스쿨 찾아가는 교육 신청 시스템

교육 소개 → 신청 접수 → 신청 관리 흐름을 Django·DRF·PostgreSQL로 만든 채용 과제입니다.
소개 콘텐츠는 히어로스쿨의 **인공지능 히어로** 과정([hero-school.net](https://hero-school.net/visit/ai/))을 썼습니다.

- 데모: https://3-35-123-81.sslip.io (관리자 계정은 제출 메일 참고)
- 관리자 화면: https://3-35-123-81.sslip.io/manage/applications/
- API 루트: https://3-35-123-81.sslip.io/api/

## 과제 요구사항 대응

| 요구사항 | 구현 | 위치 |
|---|---|---|
| 교육 소개 페이지 | 교육명·한 줄 소개·교육목표·6교시 커리큘럼·추천대상·수업 현장 사진·대표 이미지 | `/courses/ai-hero/` |
| 교육 신청 페이지 | 기관명·이름·이메일·연락처·주소(카카오 우편번호)·연락 가능 날짜·시간대·개인정보 동의. 모바일 우선 반응형, `fetch`로 제출하고 결과·오류를 같은 자리에서 갱신 | `/courses/ai-hero/apply/` |
| 신청 저장·조회·수정·삭제 | Django admin 전체 CRUD + 관리자 전용 화면에서 상태·메모 즉시 수정 | `/admin/`, `/manage/applications/` |
| 신청 상태 구분 | 접수 / 확인중 / 완료 / 취소 | `Application.Status` |
| Django + PostgreSQL 모델 | `Course`, `CurriculumItem`, `Application` | `education/models.py` |
| DRF GET/POST API | 아래 [API](#api) 참고 | `education/views.py` |
| 연락 가능 날짜 기준 자동 안내 메일 | 접수 확인 메일(제출 후 1분 안) + 연락 안내 메일(연락 가능 날짜 당일 08:00) | `education/mails.py`, `deploy/crontab` |
| (우대) 관리자 전용 신청 목록 페이지 | 상태·날짜 필터, 검색, 오늘 연락할 신청 강조, 중복 신청 표시, 상태·메모 Ajax 저장 | `templates/education/manage.html` |
| (우대) Google Sheets 내보내기 | 관리자 화면 버튼 + 매일 08:00 자동 덮어쓰기 | `education/sheets.py` |
| (우대) AWS 배포 구성 | EC2 + RDS + Caddy(HTTPS)로 실제 배포, 생성·배포·삭제 스크립트 | [docs/AWS.md](docs/AWS.md) |
| (우대) AI 코딩 보조 도구 사용 내역 | 단계별 사용 내역과 사람이 판단·검증한 부분 | [docs/AI_USAGE.md](docs/AI_USAGE.md) |

## 설계에서 정한 것

용어는 [CONTEXT.md](CONTEXT.md)에 정리했습니다. 코드와 화면 문구가 이 용어를 따릅니다.

- **신청자는 학교·기관 담당자다.** 히어로스쿨은 강사가 학교로 찾아가는 B2B 수업이 주력이라, 신청 폼의 주소를 "수업이 열리는 기관의 주소"로 보고 기관명을 필수로 받습니다. 근거는 [ADR 0001](docs/adr/0001-applicant-is-organization-staff.md).
- **연락 가능 날짜는 상담 전화를 받을 날이다.** 수업 날짜가 아닙니다. 날짜와 함께 시간대(오전 / 오후 / 방과 후)를 받고, 이 시간대에 전화하려면 번호가 필요하므로 연락처도 받습니다. 날짜는 내일부터 30일 안의 평일만 고를 수 있습니다.
- **상태는 접수 → 확인중 → 완료, 그리고 취소.** 완료는 "상담 전화가 끝남"입니다. 취소를 삭제와 구분해 이력을 남기고, 취소된 신청에는 안내 메일이 나가지 않습니다.
- **중복 신청은 막지 않고 드러낸다.** 같은 이메일·같은 교육으로 접수·확인중인 신청이 둘 이상이면 관리자 화면에 "중복" 배지가 붙습니다. 제출 버튼은 전송 중 비활성화해 더블클릭만 막습니다.
- **메일은 1분마다 도는 명령 하나가 보낸다.** 신청 요청 안에서 SMTP를 부르지 않습니다. `send_mails`가 보낼 차례인 메일을 DB에서 찾아 보내고 발송 시각을 기록하므로, 같은 메일이 두 번 가지 않고, 실패한 메일은 다음 실행에서 다시 보냅니다. 서버가 08:00에 꺼져 있었어도 켜지면 그날 안내 메일을 보냅니다. Redis·Celery 없이 cron과 `flock`만 씁니다.
- **시트는 보고용 사본이다.** 내보낼 때마다 시트 전체를 DB 내용으로 덮어써서 몇 번 실행해도 결과가 같습니다. 시트에서 고친 내용은 다음 내보내기 때 사라지므로 수정은 관리자 화면에서 합니다. Google API가 장애여도 신청 접수에는 영향이 없습니다.
- **개인정보 동의는 필수 체크만.** 실제 운영 전제가 아니라 동의 여부를 저장하지 않고, 체크하지 않으면 접수되지 않게만 했습니다.

## 데이터 모델

```
Course 교육 ─┬─< CurriculumItem 커리큘럼 (교시, 주제, 활동, 내용)
             └─< Application 신청
                   기관명, 이름, 이메일, 연락처, 우편번호, 기본주소, 상세주소,
                   연락 가능 날짜, 연락 가능 시간대, 상태, 관리자 메모,
                   신청·수정 시각, 접수 확인 메일 발송 시각, 연락 안내 메일 발송 시각
```

- 신청 → 교육은 `PROTECT`라 신청이 있는 교육은 지워지지 않습니다.
- `(contact_date, status)` 인덱스는 매일 아침 "오늘 연락할 진행 중 신청" 조회용입니다.
- 연락처·우편번호 형식은 모델 검증기로, 날짜 범위·주말·동의는 신청 시점 기준이라 공개 API serializer에서만 검사합니다(관리자가 지난 신청을 고칠 때 막히지 않도록).

## API

| 메서드 | 경로 | 권한 | 설명 |
|---|---|---|---|
| GET | `/api/courses/<slug>/` | 공개 | 교육 정보와 커리큘럼 |
| POST | `/api/applications/` | 공개 (IP당 20회/시간) | 신청 접수. `status`를 보내도 항상 `접수`로 저장 |
| GET | `/api/applications/?status=&contact_date=&q=` | staff | 신청 목록 (중복 여부 `is_duplicate` 포함) |
| GET | `/api/applications/<id>/` | staff | 신청 상세 |
| PATCH | `/api/applications/<id>/` | staff | 상태·관리자 메모만 수정 |
| POST | `/api/exports/sheets/` | staff | 신청 목록 시트 덮어쓰기 |

인증은 Django 세션(관리자 로그인)을 그대로 씁니다. 삭제는 Django admin에서만 합니다.

```bash
curl -X POST https://3-35-123-81.sslip.io/api/applications/ -H 'Content-Type: application/json' -d '{
  "course": "ai-hero", "organization": "히어로중학교", "name": "김민지", "email": "minji@example.com",
  "phone": "010-1234-5678", "postcode": "07276", "address": "서울 영등포구 선유서로25길 28",
  "contact_date": "2026-11-20", "contact_slot": "after_school", "privacy_agreed": true }'
```

## 로컬 실행

필요한 것: [uv](https://docs.astral.sh/uv/), Docker, (CSS를 고칠 때만) Node.js

```bash
cp .env.example .env
docker compose up -d db                               # PostgreSQL 17
uv run --env-file .env python manage.py migrate
uv run --env-file .env python manage.py loaddata ai_hero
uv run --env-file .env python manage.py createsuperuser
uv run --env-file .env python manage.py runserver     # http://127.0.0.1:8000
uv run --env-file .env python manage.py send_mails    # 보낼 메일 발송 (EMAIL_HOST_USER가 비어 있으면 콘솔 출력)
npm install && npm run css                            # SCSS → static/css/main.css
```

메일을 실제로 보내려면 `.env`에 Gmail 주소와 [앱 비밀번호](https://myaccount.google.com/apppasswords)를, 시트 내보내기를 쓰려면 서비스 계정 JSON 경로와 시트 ID를 넣습니다(시트를 서비스 계정 이메일에 편집자로 공유). `EMAIL_HOST`를 바꾸면 SES 등 다른 SMTP로 옮길 수 있습니다.

## 테스트

```bash
uv run --env-file .env python manage.py test education
```

신청 검증(날짜 범위·주말·동의·연락처), 권한, 중복 표시, 관리자 수정 범위, 메일 발송 시점·재발송 방지·실패 후 재시도, 시트 내보내기(Google 호출은 mock)를 확인합니다.

## 하지 않은 것

- 신청 목록 페이지네이션: 수천 건을 넘으면 DRF 페이지네이션을 붙입니다.
- 공휴일 제외: 공휴일 목록 관리가 필요해 평일만 막았습니다.
- 신청자 본인 조회·취소, 상태 변경 알림 메일: 상태 안내는 상담 전화와 회신 메일로 합니다.
- 교육 이미지 업로드: 대표 이미지는 정적 파일 경로입니다. 운영이라면 S3 + `django-storages`로 옮깁니다.
- 동의 이력 저장, 보유기간 경과 데이터 파기: 실제 운영 시 필요합니다.

## 프로젝트 구조

```
config/            설정·URL
education/         모델, API·페이지 뷰, serializer, 메일(mails.py), 시트(sheets.py), 관리 명령, 테스트
templates/         페이지·메일 템플릿
static/            SCSS 원본, 빌드된 CSS, JS, 이미지
deploy/            AWS 생성(aws.sh)·배포(deploy.sh)·삭제(teardown.sh), cron
docs/              AWS 구성, AI 사용 내역, ADR
CONTEXT.md         도메인 용어집
```

교육 소개 문구와 이미지의 저작권은 (주)어썸스쿨에 있으며, 과제 데모 용도로만 사용했습니다.
