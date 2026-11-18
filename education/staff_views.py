from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import ApplicationCreateForm, ApplicationForm, CourseForm, CurriculumFormSet, GoalFormSet
from .models import Application, Course

staff_required = user_passes_test(lambda user: user.is_active and user.is_staff)


@staff_required
def application_list(request):
    sheet_id = settings.GOOGLE_SHEET_ID
    return render(request, "manage/applications.html", {
        "statuses": Application.Status.choices,
        "today": timezone.localdate(),
        "sheet_url": sheet_id and f"https://docs.google.com/spreadsheets/d/{sheet_id}",
    })


@staff_required
def application_create(request):
    form = ApplicationCreateForm(request.POST or None, initial={"course": Course.objects.first()})
    if form.is_valid():
        application = form.save()
        messages.success(request, f"{application.organization} {application.name} 신청을 등록했습니다.")
        return redirect("manage-applications")
    return render(request, "manage/application_form.html", {"form": form})


@staff_required
def application_edit(request, pk):
    application = get_object_or_404(Application, pk=pk)
    form = ApplicationForm(request.POST or None, instance=application)
    if form.is_valid():
        form.save()
        messages.success(request, f"{application.organization} {application.name} 신청을 저장했습니다.")
        return redirect("manage-applications")
    return render(request, "manage/application_form.html", {"form": form, "application": application})


@staff_required
def application_delete(request, pk):
    application = get_object_or_404(Application, pk=pk)
    if request.method == "POST":
        application.delete()
        messages.success(request, f"{application.organization} {application.name} 신청을 삭제했습니다.")
        return redirect("manage-applications")
    return render(request, "manage/confirm_delete.html", {
        "kind": "신청", "target": application, "back": reverse("manage-application", args=[pk]),
        "warning": "삭제한 신청은 되돌릴 수 없습니다. 기록을 남기려면 삭제하지 말고 상태를 취소로 바꿔 주세요.",
    })


@staff_required
def course_list(request):
    courses = Course.objects.annotate(
        application_count=Count("applications", distinct=True), period_count=Count("curriculum", distinct=True)
    )
    return render(request, "manage/courses.html", {"courses": courses})


@staff_required
def course_form(request, slug=None):
    course = get_object_or_404(Course, slug=slug) if slug else Course()
    form = CourseForm(request.POST or None, request.FILES or None, instance=course)
    goals = GoalFormSet(request.POST or None, instance=course)
    curriculum = CurriculumFormSet(request.POST or None, instance=course)
    rows = [goals, curriculum]
    if request.method == "POST" and all([form.is_valid(), *(formset.is_valid() for formset in rows)]):
        with transaction.atomic():
            course = form.save()
            for formset in rows:
                formset.instance = course
                formset.save()
            # ponytail: 지운 사진과 바꾼 대표 이미지의 파일은 볼륨에 남는다. 용량이 문제 되면 정리 명령을 둔다.
            course.photos.filter(pk__in=[photo.pk for photo in form.cleaned_data["delete_photos"]]).delete()
            for image in form.cleaned_data["photos"]:
                course.photos.create(image=image)
        messages.success(request, f"{course.name} 교육을 저장했습니다.")
        return redirect("manage-courses")
    return render(request, "manage/course_form.html", {"form": form, "goals": goals, "curriculum": curriculum, "course": course})


@staff_required
def course_delete(request, slug):
    course = get_object_or_404(Course, slug=slug)
    count = course.applications.count()
    blocked = f"이 교육에 신청 {count}건이 있어서 삭제할 수 없습니다." if count else ""
    if request.method == "POST" and not blocked:
        course.delete()
        messages.success(request, f"{course.name} 교육을 삭제했습니다.")
        return redirect("manage-courses")
    return render(request, "manage/confirm_delete.html", {
        "kind": "교육", "target": course, "back": reverse("manage-course", args=[slug]), "blocked": blocked,
        "warning": "교육목표, 커리큘럼, 수업 현장 사진도 함께 지워집니다. 소개 페이지 주소도 더는 열리지 않습니다.",
    })
