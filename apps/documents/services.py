from django.contrib.contenttypes.models import ContentType

from apps.documents.models import Document


def attach_document(*, obj, file, uploaded_by, description=""):
    content_type = ContentType.objects.get_for_model(obj)
    return Document.objects.create(
        content_type=content_type, object_id=obj.pk, file=file, description=description, uploaded_by=uploaded_by,
    )


def documents_for(obj):
    content_type = ContentType.objects.get_for_model(obj)
    return Document.objects.filter(content_type=content_type, object_id=obj.pk).select_related("uploaded_by")
