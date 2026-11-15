from django.core.management.base import BaseCommand
from django.utils import timezone

from education.mails import send_due_mails


class Command(BaseCommand):
    help = "발송할 때가 된 접수 확인 메일과 연락 안내 메일을 보낸다. cron이 1분마다 실행한다."

    def handle(self, **options):
        if sent := send_due_mails(timezone.localtime()):
            self.stdout.write(f"{timezone.localtime():%Y-%m-%d %H:%M} 메일 {sent}통 발송")
