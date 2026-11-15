from django.contrib import admin

from .models import Application, Course, CurriculumItem


class CurriculumInline(admin.TabularInline):
    model = CurriculumItem
    extra = 0


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "summary"]
    prepopulated_fields = {"slug": ["name"]}
    inlines = [CurriculumInline]


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ["created_at", "organization", "name", "email", "phone", "contact_date", "contact_slot", "status"]
    list_filter = ["status", "contact_slot", "course", "contact_date"]
    search_fields = ["organization", "name", "email", "phone"]
    date_hierarchy = "contact_date"
    readonly_fields = ["created_at", "updated_at", "confirmation_sent_at", "reminder_sent_at"]
    fieldsets = [
        ("신청 내용", {"fields": ["course", "organization", "name", "email", "phone"]}),
        ("수업 장소", {"fields": ["postcode", "address", "address_detail"]}),
        ("상담 연락", {"fields": ["contact_date", "contact_slot", "status", "memo"]}),
        ("기록", {"fields": readonly_fields}),
    ]
