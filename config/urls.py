from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView
from rest_framework.routers import SimpleRouter

from education import staff_views, views
from education.forms import StaffLoginForm

router = SimpleRouter()
router.register("applications", views.ApplicationViewSet, basename="application")

urlpatterns = [
    path("", views.home, name="home"),
    path("courses/<slug:slug>/", views.course_detail, name="course-detail"),
    path("courses/<slug:slug>/apply/", views.apply, name="apply"),
    path("manage/", RedirectView.as_view(pattern_name="manage-applications")),
    path("manage/login/", auth_views.LoginView.as_view(
        template_name="manage/login.html", authentication_form=StaffLoginForm), name="login"),
    path("manage/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("manage/applications/", staff_views.application_list, name="manage-applications"),
    path("manage/applications/new/", staff_views.application_create, name="manage-application-new"),
    path("manage/applications/<int:pk>/", staff_views.application_edit, name="manage-application"),
    path("manage/applications/<int:pk>/delete/", staff_views.application_delete, name="manage-application-delete"),
    path("manage/courses/", staff_views.course_list, name="manage-courses"),
    path("manage/courses/new/", staff_views.course_form, name="manage-course-new"),
    path("manage/courses/<slug:slug>/", staff_views.course_form, name="manage-course"),
    path("manage/courses/<slug:slug>/delete/", staff_views.course_delete, name="manage-course-delete"),
    path("api/courses/<slug:slug>/", views.CourseDetailAPI.as_view(), name="api-course"),
    path("api/exports/sheets/", views.SheetExportAPI.as_view(), name="export-sheets"),
    path("api/", include(router.urls)),
    path("admin/", admin.site.urls),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)  # DEBUG일 때만 동작한다. 서버에서는 Caddy가 서빙한다.
