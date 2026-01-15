import pyotp
import qrcode
import io
import base64
from typing import Tuple


def generate_totp_secret() -> str:
    """Generate a new TOTP secret"""
    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str, issuer: str = "HoldemAdmin") -> str:
    """Get the TOTP provisioning URI for QR code"""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=issuer)


def generate_qr_code(uri: str) -> str:
    """Generate QR code as base64 encoded PNG"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return base64.b64encode(buffer.getvalue()).decode()


def verify_totp(secret: str, code: str) -> bool:
    """Verify a TOTP code"""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)  # Allow 1 window tolerance (30 seconds)


def setup_two_factor(email: str) -> Tuple[str, str, str]:
    """
    Set up 2FA for a user.
    Returns: (secret, uri, qr_code_base64)
    """
    secret = generate_totp_secret()
    uri = get_totp_uri(secret, email)
    qr_code = generate_qr_code(uri)
    return secret, uri, qr_code
