import logging

from django.core.mail import send_mail
from django.template.loader import render_to_string

from .models import Application

logger = logging.getLogger(__name__)
REMINDER_HOUR = 8  # 연락 안내 메일은 연락 가능 날짜 당일 이 시각 이후에 보낸다


def send_due_mails(now):
    """보낼 차례인 메일을 보내고 보낸 시각을 기록한다. 실패한 메일은 기록하지 않아 다음 실행에서 다시 보낸다."""
    # ponytail: 동시 실행 방지는 cron 의 flock(서버 한 대)뿐. 여러 대에서 돌리면 select_for_update(skip_locked=True) 추가
    sent = 0
    unconfirmed = Application.objects.filter(confirmation_sent_at__isnull=True).exclude(status=Application.Status.CANCELLED)
    for application in unconfirmed.select_related("course"):
        subject = f"[히어로스쿨] {application.course.name} 수업 신청이 접수되었습니다"
        sent += _send(application, subject, "mail/confirmation.txt", "confirmation_sent_at", now)

    if now.hour >= REMINDER_HOUR:
        due = Application.objects.filter(
            contact_date=now.date(), status__in=Application.ACTIVE_STATUSES, reminder_sent_at__isnull=True
        ).select_related("course")
        for application in due:
            subject = f"[히어로스쿨] 오늘 {application.get_contact_slot_display()}에 상담 전화를 드립니다"
            sent += _send(application, subject, "mail/reminder.txt", "reminder_sent_at", now)
    return sent


def _send(application, subject, template, sent_field, now):
    body = render_to_string(template, {"application": application})
    try:
        send_mail(subject, body, None, [application.email])
    except Exception:
        logger.exception("메일 발송 실패: %s #%s", template, application.pk)
        return 0
    Application.objects.filter(pk=application.pk).update(**{sent_field: now})
    return 1
