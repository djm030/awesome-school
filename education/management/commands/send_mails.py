from django.core.management.base import BaseCommand
from django.utils import timezone

from education.mails import send_due_mails


class Command(BaseCommand):
    help = "보낼 차례인 안내 메일(접수 확인·연락 안내)을 보낸다. cron 으로 1분마다 실행한다."

    def handle(self, **options):
        if sent := send_due_mails(timezone.localtime()):
            self.stdout.write(f"{timezone.localtime():%Y-%m-%d %H:%M} 메일 {sent}통 발송")
