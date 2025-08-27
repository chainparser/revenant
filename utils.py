import qrcode
import base64
from io import BytesIO

def generate_qr_code(data: str) -> str:
    """Generate a base64 QR code image from string data."""
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def format_usd(amount: str | float | int) -> str:
    """Format a number into USD currency string, e.g. 15231.89 → $15,231.89"""
    try:
        value = float(amount)
        return "${:,.2f}".format(value)
    except (ValueError, TypeError):
        return "$0.00"
