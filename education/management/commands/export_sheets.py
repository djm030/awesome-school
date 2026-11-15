from django.core.management.base import BaseCommand

from education.sheets import export_applications


class Command(BaseCommand):
    help = "신청 목록 시트를 현재 전체 신청으로 덮어쓴다. cron 으로 매일 아침 실행한다."

    def handle(self, **options):
        self.stdout.write(f"시트에 {export_applications()}건 내보냄")
