import io
import uuid

import qrcode
from django.core.files.base import ContentFile

from apps.catalogue.models import Product


def provision_codes(product: Product) -> None:
    """Generates qr_code_data + qr_code_image for a newly created product.
    Called explicitly from the create serializer (not a post_save signal) so
    the create path stays a single, testable, traceable call."""
    if not product.qr_code_data:
        product.qr_code_data = f"PROD-{product.pk}-{uuid.uuid4().hex[:12]}"

    img = qrcode.make(product.qr_code_data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    product.qr_code_image.save(f"product-{product.pk}.png", ContentFile(buf.getvalue()), save=False)
    product.save(update_fields=["qr_code_data", "qr_code_image"])
