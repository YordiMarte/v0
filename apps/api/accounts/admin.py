from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm

from accounts.models import User


class UserCreationForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "full_name")


class UserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = ("email", "full_name")


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = UserEditForm
    add_form = UserCreationForm
    ordering = ("email",)
    list_display = ("email", "full_name", "is_staff", "is_active")
    search_fields = ("email", "full_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("full_name",)}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "password1", "password2"),
            },
        ),
    )
