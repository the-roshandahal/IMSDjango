from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models

ALLOWED_EXTENSIONS = ["pdf", "jpg", "jpeg", "png", "docx", "xlsx"]


def validate_file_extension(value):
    ext = value.name.rsplit(".", 1)[-1].lower() if "." in value.name else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(f"Unsupported file type .{ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}.")


def validate_file_size(value):
    max_bytes = settings.DOCUMENT_MAX_UPLOAD_MB * 1024 * 1024
    if value.size > max_bytes:
        raise ValidationError(f"File is larger than the {settings.DOCUMENT_MAX_UPLOAD_MB}MB limit.")


class ScanStatus(models.TextChoices):
    NOT_SCANNED = "not_scanned", "Not scanned"
    CLEAN = "clean", "Clean"
    INFECTED = "infected", "Infected"


class Document(models.Model):
    """SRS Section 5.16. Generic attachment -- one model covers products
    (SDS/certificates), purchase orders (invoices), equipment/vehicles
    (service records), and deep clean projects (contracts/site photos),
    via a GenericForeignKey rather than five near-identical tables.

    `scan_status` defaults to NOT_SCANNED and stays there: this project
    has no antivirus engine wired up (would need ClamAV or a paid cloud
    API), so real malware scanning is a documented gap, not something
    faked with a false "clean" result. Extension allowlist + size limit
    ARE enforced for real.
    """

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    file = models.FileField(upload_to="documents/%Y/%m/", validators=[validate_file_extension, validate_file_size])
    original_filename = models.CharField(max_length=255, blank=True)
    description = models.CharField(max_length=255, blank=True)
    scan_status = models.CharField(max_length=16, choices=ScanStatus.choices, default=ScanStatus.NOT_SCANNED)

    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def save(self, *args, **kwargs):
        if not self.original_filename and self.file:
            self.original_filename = self.file.name.rsplit("/", 1)[-1]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.original_filename or self.file.name
