from django.core.management.base import BaseCommand

from education.sheets import export_applications


class Command(BaseCommand):
    help = "신청 목록 시트를 지금 있는 전체 신청으로 덮어쓴다. cron이 매일 08:00에 실행한다."

    def handle(self, **options):
        self.stdout.write(f"시트에 {export_applications()}건을 내보냈다")
