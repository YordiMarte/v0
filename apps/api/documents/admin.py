from django.contrib import admin

from documents.models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("original_name", "organization", "status", "size_bytes", "created_at")
    list_filter = ("status",)
    search_fields = ("original_name", "organization__name")
    readonly_fields = [field.name for field in Document._meta.fields]

    def has_add_permission(self, request):
        return False
