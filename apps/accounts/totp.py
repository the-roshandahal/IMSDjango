import base64
import io
from urllib.parse import quote

import qrcode
from django_otp.plugins.otp_totp.models import TOTPDevice


def get_or_create_unconfirmed_device(user) -> TOTPDevice:
    device, _ = TOTPDevice.objects.get_or_create(
        user=user, name="default", defaults={"confirmed": False}
    )
    if device.confirmed:
        # Re-enrolling: replace the key so the old device/secret is invalidated.
        device.delete()
        device = TOTPDevice.objects.create(user=user, name="default", confirmed=False)
    return device


def provisioning_payload(device: TOTPDevice, issuer: str = "IMS") -> dict:
    secret_b32 = base64.b32encode(device.bin_key).decode("utf-8").rstrip("=")
    label = quote(f"{issuer}:{device.user.username}")
    otpauth_url = f"otpauth://totp/{label}?secret={secret_b32}&issuer={quote(issuer)}&digits={device.digits}"

    img = qrcode.make(otpauth_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return {"secret": secret_b32, "otpauth_url": otpauth_url, "qr_code_base64": qr_base64}
