import logging

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import generics, mixins, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .models import Application, Course
from .serializers import ApplicationCreateSerializer, ApplicationStaffSerializer, CourseSerializer
from .sheets import export_applications

logger = logging.getLogger(__name__)


# --- 페이지 ---

def home(request):
    if not (course := Course.objects.order_by("pk").first()):
        raise Http404("등록된 교육이 없습니다.")
    return redirect("course-detail", slug=course.slug)


def course_detail(request, slug):
    course = get_object_or_404(Course.objects.prefetch_related("curriculum"), slug=slug)
    return render(request, "education/course_detail.html", {"course": course})


def apply(request, slug):
    course = get_object_or_404(Course, slug=slug)
    first, last = Application.contact_date_range(timezone.localdate())
    return render(request, "education/apply.html", {
        "course": course, "date_min": first, "date_max": last, "slots": Application.TimeSlot.choices,
    })


@staff_member_required
def manage(request):
    sheet_id = settings.GOOGLE_SHEET_ID
    return render(request, "education/manage.html", {
        "statuses": Application.Status.choices,
        "today": timezone.localdate(),
        "sheet_url": sheet_id and f"https://docs.google.com/spreadsheets/d/{sheet_id}",
    })


# --- API ---

class CourseDetailAPI(generics.RetrieveAPIView):
    queryset = Course.objects.prefetch_related("curriculum")
    serializer_class = CourseSerializer
    lookup_field = "slug"
    permission_classes = [AllowAny]


class ApplicationViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                         mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """POST 는 누구나(throttle), 조회·수정은 staff 만. 삭제는 Django admin 에서."""

    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_permissions(self):
        return [AllowAny()] if self.action == "create" else [IsAdminUser()]

    def get_throttles(self):
        return [AnonRateThrottle()] if self.action == "create" else []

    def get_serializer_class(self):
        return ApplicationCreateSerializer if self.action == "create" else ApplicationStaffSerializer

    def get_queryset(self):
        # ponytail: 페이지네이션 없음. 신청이 수천 건을 넘으면 DRF PageNumberPagination 추가
        qs = Application.objects.select_related("course").with_duplicate_flag()
        params = self.request.query_params
        if status := params.get("status"):
            qs = qs.filter(status=status)
        if raw := params.get("contact_date"):
            if not (day := parse_date(raw)):
                raise ValidationError({"contact_date": "YYYY-MM-DD 형식이어야 합니다."})
            qs = qs.filter(contact_date=day)
        if q := params.get("q", "").strip():
            qs = qs.filter(Q(organization__icontains=q) | Q(name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q))
        return qs


class SheetExportAPI(APIView):
    """신청 목록 시트 덮어쓰기. 실패해도 신청 데이터에는 영향이 없다."""

    permission_classes = [IsAdminUser]

    def post(self, request):
        if not (settings.GOOGLE_SERVICE_ACCOUNT_FILE and settings.GOOGLE_SHEET_ID):
            return Response({"detail": "Google 시트 설정(GOOGLE_SERVICE_ACCOUNT_FILE, GOOGLE_SHEET_ID)이 없습니다."}, status=503)
        try:
            rows = export_applications()
        except Exception as error:  # 키 파일·권한·Google API 장애를 관리자에게 그대로 보여 준다
            logger.exception("시트 내보내기 실패")
            return Response({"detail": f"Google 시트 오류: {error}"}, status=502)
        return Response({"rows": rows})
