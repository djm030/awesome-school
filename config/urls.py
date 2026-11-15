from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import SimpleRouter

from education import views

router = SimpleRouter()
router.register("applications", views.ApplicationViewSet, basename="application")

urlpatterns = [
    path("", views.home, name="home"),
    path("courses/<slug:slug>/", views.course_detail, name="course-detail"),
    path("courses/<slug:slug>/apply/", views.apply, name="apply"),
    path("manage/applications/", views.manage, name="manage"),
    path("api/courses/<slug:slug>/", views.CourseDetailAPI.as_view(), name="api-course"),
    path("api/exports/sheets/", views.SheetExportAPI.as_view(), name="export-sheets"),
    path("api/", include(router.urls)),
    path("admin/", admin.site.urls),
]
