from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from .models import Application, Course, CourseGoal, CoursePhoto, CurriculumItem

MAX_IMAGE_BYTES = 5 * 1024 * 1024


def limit_image_size(image):
    if image.size > MAX_IMAGE_BYTES:
        raise ValidationError("이미지는 5MB까지 올릴 수 있습니다.")


class NoColonMixin:
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)


class StaffLoginForm(NoColonMixin, AdminAuthenticationForm):
    error_messages = {
        **AdminAuthenticationForm.error_messages,
        "invalid_login": "아이디나 비밀번호가 맞지 않습니다. 관리자 계정으로 로그인해 주세요.",
    }


class LinesField(forms.CharField):
    """JSON 목록을 한 줄에 한 항목씩 적는 textarea로 편집한다."""

    widget = forms.Textarea(attrs={"rows": 4})

    def prepare_value(self, value):
        return "\n".join(value) if isinstance(value, list) else value

    def to_python(self, value):
        return [line.strip() for line in (value or "").splitlines() if line.strip()]


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else [data] if data else []
        return [super(MultipleImageField, self).clean(file, initial) for file in files]


class CourseForm(NoColonMixin, forms.ModelForm):
    targets = LinesField(label="추천 대상", help_text="한 줄에 하나씩 적습니다.")
    photos = MultipleImageField(label="사진 추가", required=False, validators=[limit_image_size],
                                help_text="여러 장을 한 번에 고를 수 있습니다. 한 장에 5MB까지입니다.")
    delete_photos = forms.ModelMultipleChoiceField(CoursePhoto.objects.none(), required=False)

    class Meta:
        model = Course
        fields = ["name", "slug", "summary", "format_note", "targets", "image"]
        labels = {"slug": "주소 이름"}
        help_texts = {
            "slug": "소개 페이지 주소(/courses/주소 이름/)에 쓰입니다. 영문 소문자, 숫자, 하이픈만 쓸 수 있고 만든 뒤에는 바꿀 수 없습니다.",
            "image": "5MB까지 올릴 수 있습니다.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["image"].validators.append(limit_image_size)
        self.fields["slug"].validators.append(RegexValidator(r"^[a-z0-9-]+\Z", "영문 소문자, 숫자, 하이픈만 쓸 수 있습니다."))
        if self.instance.pk:
            self.fields["slug"].disabled = True  # 이미 공유된 소개 페이지 링크가 깨지지 않게 한다
            self.fields["delete_photos"].queryset = self.instance.photos.all()


class RowForm(NoColonMixin, forms.ModelForm):
    pass


class RowFormSet(forms.BaseInlineFormSet):
    default_error_messages = {"too_few_forms": "한 행 이상 입력해 주세요."}

    def get_unique_error_message(self, unique_check):
        labels = [str(self.model._meta.get_field(name).verbose_name) for name in unique_check if name != self.fk.name]
        return f"{', '.join(labels)} 값이 겹칩니다. 다른 값으로 바꿔 주세요."


ROW_OPTIONS = {
    "form": RowForm, "formset": RowFormSet, "extra": 0, "min_num": 1, "validate_min": True, "can_delete": True,
}
GoalFormSet = forms.inlineformset_factory(Course, CourseGoal, fields=["title", "body"], **ROW_OPTIONS)
CurriculumFormSet = forms.inlineformset_factory(
    Course, CurriculumItem, fields=["period", "topic", "activity", "content"],
    widgets={"content": forms.Textarea(attrs={"rows": 2})}, **ROW_OPTIONS,
)


class ApplicationForm(NoColonMixin, forms.ModelForm):
    """관리자용이다. 날짜 범위와 주말 제한은 신청자가 쓰는 공개 API에서만 검사한다."""

    class Meta:
        model = Application
        fields = [
            "course", "organization", "name", "email", "phone", "postcode", "address", "address_detail",
            "contact_date", "contact_slot", "status", "memo",
        ]
        widgets = {
            "contact_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "memo": forms.Textarea(attrs={"rows": 3}),
        }


class ApplicationCreateForm(ApplicationForm):
    """전화 문의를 관리자가 대신 등록할 때 쓴다. 이미 통화로 안내했으면 접수 확인 메일을 끌 수 있다."""

    class Meta(ApplicationForm.Meta):
        fields = [*ApplicationForm.Meta.fields, "send_confirmation"]
