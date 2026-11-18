import tempfile
from datetime import date, datetime
from io import BytesIO
from unittest.mock import patch

from PIL import Image

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils.timezone import make_aware

from .mails import send_due_mails
from .models import Application, Course

TODAY = date(2026, 11, 16)  # 월요일
VALID = {
    "course": "ai-hero", "organization": "히어로중학교", "name": "김민지", "email": "minji@example.com",
    "phone": "010-1234-5678", "postcode": "07276", "address": "서울 영등포구 선유서로25길 28",
    "contact_date": "2026-11-17", "contact_slot": "afternoon", "privacy_agreed": True,
}


def make_application(course, **overrides):
    fields = {k: v for k, v in VALID.items() if k not in ("course", "privacy_agreed")}
    return Application.objects.create(course=course, **{**fields, "contact_date": date(2026, 11, 17), **overrides})


@patch("django.utils.timezone.localdate", lambda: TODAY)
class ApplicationCreateTests(TestCase):
    fixtures = ["ai_hero"]

    def setUp(self):
        cache.clear()  # 앞선 테스트의 신청 횟수가 throttle에 걸리지 않게 한다

    def post(self, **overrides):
        return self.client.post("/api/applications/", {**VALID, **overrides}, content_type="application/json")

    def test_valid_application_is_received_whatever_status_is_sent(self):
        response = self.post(status="done")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Application.objects.get().status, Application.Status.RECEIVED)

    def test_contact_date_must_be_weekday_within_30_days_from_tomorrow(self):
        for day in ["2026-11-16", "2026-11-21", "2026-12-17"]:  # 오늘, 토요일, 31일 뒤는 모두 거절한다
            with self.subTest(day=day):
                self.assertEqual(self.post(contact_date=day).status_code, 400)
        self.assertEqual(self.post(contact_date="2026-12-16").status_code, 201)  # 30일 뒤 수요일

    def test_privacy_consent_and_phone_format_are_required(self):
        response = self.post(privacy_agreed=False, phone="12345")
        self.assertEqual(set(response.json()), {"privacy_agreed", "phone"})


class ApplicationStaffApiTests(TestCase):
    fixtures = ["ai_hero"]

    def setUp(self):
        self.course = Course.objects.get(slug="ai-hero")
        self.first = make_application(self.course)
        self.second = make_application(self.course, email="MINJI@example.com")

    def test_anonymous_cannot_read_applications(self):
        self.assertEqual(self.client.get("/api/applications/").status_code, 403)

    def test_staff_sees_duplicates_until_one_is_cancelled(self):
        self.client.force_login(User.objects.create_user("staff", is_staff=True))
        flags = lambda: {row["id"]: row["is_duplicate"] for row in self.client.get("/api/applications/").json()}
        self.assertEqual(flags(), {self.first.pk: True, self.second.pk: True})

        response = self.client.patch(f"/api/applications/{self.second.pk}/", {"status": "cancelled", "memo": "중복", "email": "x@x.com"},
                                     content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.second.refresh_from_db()
        self.assertEqual((self.second.status, self.second.memo, self.second.email), ("cancelled", "중복", "MINJI@example.com"))
        self.assertEqual(flags(), {self.first.pk: False, self.second.pk: False})


class MailTests(TestCase):
    fixtures = ["ai_hero"]

    def setUp(self):
        course = Course.objects.get(slug="ai-hero")
        self.active = make_application(course)  # 연락 가능 날짜 11/17
        make_application(course, email="cancelled@example.com", status=Application.Status.CANCELLED)

    def run_at(self, *args):
        return send_due_mails(make_aware(datetime(*args)))

    def test_confirmation_goes_once_and_not_to_cancelled(self):
        self.assertEqual(self.run_at(2026, 11, 16, 10, 0), 1)
        self.assertEqual(self.run_at(2026, 11, 16, 10, 1), 0)
        self.assertEqual(mail.outbox[0].to, ["minji@example.com"])

    def test_reminder_goes_once_from_8am_on_contact_date(self):
        self.run_at(2026, 11, 16, 10, 0)
        self.assertEqual(self.run_at(2026, 11, 17, 7, 59), 0)
        self.assertEqual(self.run_at(2026, 11, 17, 8, 0), 1)
        self.assertEqual(self.run_at(2026, 11, 17, 8, 1), 0)
        self.assertIn("오후", mail.outbox[-1].subject)

    def test_failed_send_is_retried_next_run(self):
        with patch("education.mails.send_mail", side_effect=OSError("smtp down")):
            self.assertEqual(self.run_at(2026, 11, 16, 10, 0), 0)
        self.assertEqual(self.run_at(2026, 11, 16, 10, 1), 1)


class SheetExportTests(TestCase):
    fixtures = ["ai_hero"]

    def setUp(self):
        make_application(Course.objects.get(slug="ai-hero"))
        self.client.force_login(User.objects.create_user("staff", is_staff=True))

    @override_settings(GOOGLE_SERVICE_ACCOUNT_FILE="", GOOGLE_SHEET_ID="")
    def test_not_configured_returns_503(self):
        self.assertEqual(self.client.post("/api/exports/sheets/").status_code, 503)

    @override_settings(GOOGLE_SERVICE_ACCOUNT_FILE="key.json", GOOGLE_SHEET_ID="sheet")
    def test_export_overwrites_sheet_with_note_header_and_rows(self):
        with patch("education.sheets.gspread.service_account") as service_account:
            response = self.client.post("/api/exports/sheets/")
        self.assertEqual(response.json(), {"rows": 1})
        sheet = service_account.return_value.open_by_key.return_value.sheet1
        sheet.clear.assert_called_once()
        values = sheet.update.call_args.args[0]
        self.assertEqual(values[1][0], "ID")
        self.assertEqual(values[2][6], "010-1234-5678")  # RAW 입력이라 연락처가 문자열로 남는다


def png(name="photo.png"):
    buffer = BytesIO()
    Image.new("RGB", (4, 3), "purple").save(buffer, "PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class StaffPageTests(TestCase):
    fixtures = ["ai_hero"]

    def setUp(self):
        self.course = Course.objects.get(slug="ai-hero")
        self.client.force_login(User.objects.create_user("staff", is_staff=True))

    def application_data(self, **overrides):
        fields = {k: v for k, v in VALID.items() if k not in ("course", "privacy_agreed")}
        return {**fields, "course": self.course.pk, "status": "received", "memo": "", **overrides}

    def test_anonymous_and_non_staff_are_sent_to_login(self):
        self.client.logout()
        self.assertRedirects(self.client.get("/manage/applications/"), "/manage/login/?next=/manage/applications/")
        self.client.force_login(User.objects.create_user("member"))
        self.assertEqual(self.client.get("/manage/courses/").status_code, 302)

    def test_staff_registered_application_skips_confirmation_mail_when_unchecked(self):
        self.client.post("/manage/applications/new/", self.application_data(email="quiet@example.com"))
        self.client.post("/manage/applications/new/", self.application_data(email="mail@example.com", send_confirmation="on"))
        self.assertEqual(send_due_mails(make_aware(datetime(2026, 11, 16, 10, 0))), 1)
        self.assertEqual(mail.outbox[0].to, ["mail@example.com"])

    def test_reminder_goes_again_on_rescheduled_contact_date(self):
        application = make_application(self.course, confirmation_sent_at=make_aware(datetime(2026, 11, 16)))
        reminders_at = lambda *day: send_due_mails(make_aware(datetime(*day, 8, 0)))
        self.assertEqual(reminders_at(2026, 11, 17), 1)
        response = self.client.post(f"/manage/applications/{application.pk}/", self.application_data(contact_date="2026-11-20"))
        self.assertRedirects(response, "/manage/applications/")
        self.assertEqual((reminders_at(2026, 11, 20), reminders_at(2026, 11, 20)), (1, 0))

    def test_delete_application(self):
        application = make_application(self.course)
        self.client.post(f"/manage/applications/{application.pk}/delete/")
        self.assertFalse(Application.objects.exists())

    def test_create_course_with_image_photos_and_curriculum(self):
        response = self.client.post("/manage/courses/new/", {
            "name": "코딩 히어로", "slug": "coding-hero", "summary": "한 줄 소개", "format_note": "4교시",
            "targets": "코딩이 처음인 학생\n게임을 좋아하는 학생",
            "goals-TOTAL_FORMS": "1", "goals-INITIAL_FORMS": "0", "goals-0-title": "논리", "goals-0-body": "문제를 나눠 생각한다",
            "image": png("main.png"), "photos": [png("a.png"), png("b.png")],
            "curriculum-TOTAL_FORMS": "2", "curriculum-INITIAL_FORMS": "0",
            "curriculum-0-period": "1", "curriculum-0-topic": "순서", "curriculum-0-activity": "놀이", "curriculum-0-content": "내용",
            "curriculum-1-period": "", "curriculum-1-topic": "", "curriculum-1-activity": "", "curriculum-1-content": "",
        })
        self.assertRedirects(response, "/manage/courses/")
        course = Course.objects.get(slug="coding-hero")
        self.assertEqual(list(course.goals.values_list("title", "body")), [("논리", "문제를 나눠 생각한다")])
        self.assertEqual(course.targets, ["코딩이 처음인 학생", "게임을 좋아하는 학생"])
        self.assertEqual((course.curriculum.count(), course.photos.count()), (1, 2))
        self.client.logout()
        self.assertContains(self.client.get("/"), "코딩 히어로")  # 교육이 둘이 되면 첫 화면은 목록이다

    def test_course_with_applications_cannot_be_deleted(self):
        make_application(self.course)
        response = self.client.post("/manage/courses/ai-hero/delete/")
        self.assertContains(response, "신청 1건이 있어서 삭제할 수 없습니다")
        self.assertTrue(Course.objects.filter(slug="ai-hero").exists())

    def course_post(self, **overrides):
        course = self.course
        data = {
            "name": course.name, "summary": course.summary, "format_note": course.format_note,
            "targets": "\n".join(course.targets),
            "goals-TOTAL_FORMS": "0", "goals-INITIAL_FORMS": "0",
            "curriculum-TOTAL_FORMS": "0", "curriculum-INITIAL_FORMS": "0",
        }
        for prefix, rows in (("goals", course.goals.all()), ("curriculum", course.curriculum.all())):
            fields = ["title", "body"] if prefix == "goals" else ["period", "topic", "activity", "content"]
            data[f"{prefix}-TOTAL_FORMS"] = data[f"{prefix}-INITIAL_FORMS"] = str(len(rows))
            for i, row in enumerate(rows):
                data[f"{prefix}-{i}-id"] = row.pk
                data.update({f"{prefix}-{i}-{name}": getattr(row, name) for name in fields})
        return self.client.post("/manage/courses/ai-hero/", {**data, **overrides})

    def test_swapping_two_periods_saves(self):
        first, second = self.course.curriculum.all()[:2]
        response = self.course_post(**{"curriculum-0-period": 2, "curriculum-1-period": 1})
        self.assertRedirects(response, "/manage/courses/")
        self.assertEqual(self.course.curriculum.first().pk, second.pk)

    def test_duplicate_period_and_foreign_photo_are_form_errors(self):
        response = self.course_post(**{"curriculum-1-period": 1, "delete_photos": ["999"]})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "교시 값이 겹칩니다")
        self.assertEqual(self.course.photos.count(), 3)

    def test_edit_page_shows_reminder_only_for_current_contact_date(self):
        application = make_application(self.course, reminder_sent_at=make_aware(datetime(2026, 11, 17, 8, 0)))
        self.assertContains(self.client.get(f"/manage/applications/{application.pk}/"), "2026-11-17 08:00")
        Application.objects.filter(pk=application.pk).update(contact_date=date(2026, 11, 20))
        self.assertNotContains(self.client.get(f"/manage/applications/{application.pk}/"), "2026-11-17 08:00")
