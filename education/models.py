from datetime import timedelta

from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Exists, OuterRef
from django.utils import timezone


class Course(models.Model):
    name = models.CharField("교육명", max_length=100)
    slug = models.SlugField(unique=True)
    summary = models.CharField("한 줄 소개", max_length=200)
    targets = models.JSONField("추천대상", default=list, help_text='["...", "..."]')
    format_note = models.CharField("수업형태", max_length=200)
    image = models.ImageField("대표 이미지", upload_to="courses/")

    class Meta:
        verbose_name = verbose_name_plural = "교육"
        ordering = ["pk"]

    def __str__(self):
        return self.name


class CourseGoal(models.Model):
    course = models.ForeignKey(Course, models.CASCADE, related_name="goals")
    title = models.CharField("목표", max_length=50)
    body = models.CharField("설명", max_length=200)

    class Meta:
        verbose_name = verbose_name_plural = "교육목표"
        ordering = ["pk"]

    def __str__(self):
        return self.title


class CoursePhoto(models.Model):
    course = models.ForeignKey(Course, models.CASCADE, related_name="photos")
    image = models.ImageField("수업 현장 사진", upload_to="courses/photos/")

    class Meta:
        verbose_name = verbose_name_plural = "수업 현장 사진"
        ordering = ["pk"]


class CurriculumItem(models.Model):
    course = models.ForeignKey(Course, models.CASCADE, related_name="curriculum")
    period = models.PositiveSmallIntegerField("교시")
    topic = models.CharField("주제", max_length=100)
    activity = models.CharField("활동", max_length=100)
    content = models.TextField("내용")

    class Meta:
        verbose_name = verbose_name_plural = "커리큘럼"
        ordering = ["period"]
        # 교시를 서로 바꿔 저장할 때 행마다 검사하면 중간 상태에서 충돌하므로 커밋 시점에 검사한다.
        constraints = [models.UniqueConstraint(
            fields=["course", "period"], name="unique_course_period", deferrable=models.Deferrable.DEFERRED
        )]

    def __str__(self):
        return f"{self.period}교시 {self.topic}"


class ApplicationQuerySet(models.QuerySet):
    def with_duplicate_flag(self):
        """진행 중(접수·확인중)인 신청에 같은 이메일, 같은 교육의 진행 중 신청이 하나 더 있으면 is_duplicate가 참이다."""
        others = Application.objects.filter(
            course=OuterRef("course"), email__iexact=OuterRef("email"), status__in=Application.ACTIVE_STATUSES
        ).exclude(pk=OuterRef("pk"))
        flag = models.Q(Exists(others)) & models.Q(status__in=Application.ACTIVE_STATUSES)
        return self.annotate(is_duplicate=models.ExpressionWrapper(flag, output_field=models.BooleanField()))

    def confirmation_due(self):
        return self.filter(send_confirmation=True, confirmation_sent_at__isnull=True).exclude(
            status=Application.Status.CANCELLED
        )

    def reminder_due(self, today):
        """연락 안내 메일은 연락 가능 날짜 당일에만 나간다. 그래서 오늘 날짜로 된 발송 기록이 없으면 오늘 날짜분은 아직 안 보낸 것이다.
        관리자가 날짜를 바꾸면 새 날짜에는 그날 기록이 없으므로 다시 나간다. Application.reminder_sent가 같은 규칙을 화면에 쓴다."""
        return self.filter(contact_date=today, status__in=Application.ACTIVE_STATUSES).exclude(reminder_sent_at__date=today)


class Application(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "received", "접수"
        REVIEWING = "reviewing", "확인중"
        DONE = "done", "완료"
        CANCELLED = "cancelled", "취소"

    class TimeSlot(models.TextChoices):
        MORNING = "morning", "오전 (09~12시)"
        AFTERNOON = "afternoon", "오후 (13~15시)"
        AFTER_SCHOOL = "after_school", "방과 후 (15~18시)"

    ACTIVE_STATUSES = (Status.RECEIVED, Status.REVIEWING)

    course = models.ForeignKey(Course, models.PROTECT, related_name="applications", verbose_name="교육")
    organization = models.CharField("기관명", max_length=100)
    name = models.CharField("이름", max_length=50)
    email = models.EmailField("이메일")
    phone = models.CharField(
        "연락처",
        max_length=20,
        validators=[RegexValidator(r"^0\d{1,2}-?\d{3,4}-?\d{4}$", "전화번호 형식이 아닙니다. 예: 010-1234-5678")],
    )
    postcode = models.CharField("우편번호", max_length=5, validators=[RegexValidator(r"^\d{5}$", "우편번호는 숫자 5자리입니다.")])
    address = models.CharField("기본주소", max_length=200)
    address_detail = models.CharField("상세주소", max_length=200, blank=True)
    contact_date = models.DateField("연락 가능 날짜")
    contact_slot = models.CharField("연락 가능 시간대", max_length=20, choices=TimeSlot)
    status = models.CharField("상태", max_length=20, choices=Status, default=Status.RECEIVED)
    memo = models.TextField("관리자 메모", blank=True)
    send_confirmation = models.BooleanField("접수 확인 메일 보내기", default=True)
    created_at = models.DateTimeField("신청 시각", auto_now_add=True)
    updated_at = models.DateTimeField("수정 시각", auto_now=True)
    confirmation_sent_at = models.DateTimeField("접수 확인 메일 발송", null=True, blank=True, editable=False)
    reminder_sent_at = models.DateTimeField("연락 안내 메일 발송", null=True, blank=True, editable=False)

    objects = ApplicationQuerySet.as_manager()

    class Meta:
        verbose_name = verbose_name_plural = "신청"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["contact_date", "status"])]

    def __str__(self):
        return f"{self.organization} {self.name} ({self.get_status_display()})"

    @property
    def reminder_sent(self):
        """지금 연락 가능 날짜분의 연락 안내 메일을 보낸 시각이다. 날짜를 바꾸기 전에 보낸 메일이면 None이다."""
        sent = self.reminder_sent_at
        return sent if sent and timezone.localdate(sent) == self.contact_date else None

    @staticmethod
    def contact_date_range(today):
        """연락 가능 날짜로 고를 수 있는 첫날과 마지막 날을 돌려준다. 내일부터 30일 뒤까지이며 주말은 serializer가 따로 막는다."""
        return today + timedelta(days=1), today + timedelta(days=30)
