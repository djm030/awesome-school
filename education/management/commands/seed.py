import shutil
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

SEED_MEDIA = Path(__file__).resolve().parents[2] / "fixtures" / "media"


class Command(BaseCommand):
    help = "인공지능 히어로 교육 시드(ai_hero)를 넣고 시드 이미지를 MEDIA_ROOT에 복사한다. 같은 pk의 교육 내용은 시드로 되돌아간다."

    def handle(self, *args, **options):
        shutil.copytree(SEED_MEDIA, settings.MEDIA_ROOT, dirs_exist_ok=True)
        call_command("loaddata", "ai_hero", verbosity=options["verbosity"])
