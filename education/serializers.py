from django.utils import timezone
from rest_framework import serializers

from .models import Application, Course, CurriculumItem


class CurriculumItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CurriculumItem
        fields = ["period", "topic", "activity", "content"]


class CourseSerializer(serializers.ModelSerializer):
    curriculum = CurriculumItemSerializer(many=True, read_only=True)

    class Meta:
        model = Course
        fields = ["slug", "name", "summary", "goals", "targets", "format_note", "image", "photos", "curriculum"]


class ApplicationCreateSerializer(serializers.ModelSerializer):
    """신청자가 쓰는 공개 접수용이다. 상태와 메모는 입력받지 않는다."""

    course = serializers.SlugRelatedField(slug_field="slug", queryset=Course.objects.all())
    privacy_agreed = serializers.BooleanField(write_only=True)

    class Meta:
        model = Application
        fields = [
            "id", "course", "organization", "name", "email", "phone", "postcode", "address", "address_detail",
            "contact_date", "contact_slot", "privacy_agreed", "status", "created_at",
        ]
        read_only_fields = ["id", "status", "created_at"]

    def validate_privacy_agreed(self, agreed):
        if not agreed:
            raise serializers.ValidationError("개인정보 수집·이용에 동의해 주세요.")
        return agreed

    def validate_contact_date(self, day):
        first, last = Application.contact_date_range(timezone.localdate())
        if not first <= day <= last:
            raise serializers.ValidationError(f"{first:%m/%d}부터 {last:%m/%d}까지 고를 수 있습니다.")
        if day.weekday() >= 5:
            raise serializers.ValidationError("주말은 고를 수 없습니다. 평일을 골라 주세요.")
        return day

    def create(self, validated_data):
        validated_data.pop("privacy_agreed")
        return super().create(validated_data)


class ApplicationStaffSerializer(serializers.ModelSerializer):
    """관리자가 조회하고 수정할 때 쓴다. 바꿀 수 있는 필드는 상태와 메모뿐이다."""

    course = serializers.CharField(source="course.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    contact_slot_display = serializers.CharField(source="get_contact_slot_display", read_only=True)
    is_duplicate = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = Application
        fields = [
            "id", "course", "organization", "name", "email", "phone", "postcode", "address", "address_detail",
            "contact_date", "contact_slot", "contact_slot_display", "status", "status_display", "memo",
            "is_duplicate", "created_at", "updated_at", "confirmation_sent_at", "reminder_sent_at",
        ]
        read_only_fields = [f for f in fields if f not in ("status", "memo")]
