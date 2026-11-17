from django.contrib import admin

from organizations.models import Membership, Organization


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    raw_id_fields = ("user",)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")
    inlines = [MembershipInline]
