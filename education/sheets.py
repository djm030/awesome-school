import gspread
from django.conf import settings
from django.utils import timezone

from .models import Application

HEADER = ["ID", "신청 시각", "교육", "기관명", "이름", "이메일", "연락처", "우편번호", "주소", "상세주소",
          "연락 가능 날짜", "연락 가능 시간대", "상태", "관리자 메모"]


def sheet_rows():
    for a in Application.objects.select_related("course").order_by("created_at"):
        yield [a.pk, f"{timezone.localtime(a.created_at):%Y-%m-%d %H:%M}", a.course.name, a.organization, a.name,
               a.email, a.phone, a.postcode, a.address, a.address_detail, a.contact_date.isoformat(),
               a.get_contact_slot_display(), a.get_status_display(), a.memo]


def export_applications():
    """신청 목록 시트를 지금 DB 의 전체 신청으로 덮어쓴다. 시트는 보고용 사본이다. 내보낸 행 수를 돌려준다."""
    rows = list(sheet_rows())
    note = f"※ 시스템에서 내보낸 사본입니다. 내보낼 때마다 전체가 덮어써지니 여기서 고치지 마세요. (내보낸 시각 {timezone.localtime():%Y-%m-%d %H:%M})"
    sheet = gspread.service_account(filename=settings.GOOGLE_SERVICE_ACCOUNT_FILE).open_by_key(settings.GOOGLE_SHEET_ID).sheet1
    sheet.clear()
    sheet.update([[note], HEADER, *rows], value_input_option="RAW")  # RAW: 010-... 이 숫자로 바뀌지 않게
    return len(rows)
