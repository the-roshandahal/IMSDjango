from django.contrib import admin

from apps.documents.models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["original_filename", "content_type", "object_id", "uploaded_by", "uploaded_at", "scan_status"]
    list_filter = ["content_type", "scan_status"]
