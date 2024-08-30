import base64
import io
from uuid import uuid4
from decimal import Decimal

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.exceptions import SuspiciousOperation


# WARNING: quick and dirty, should be used for reference only.
def to_file(file_from_POST):
    """base64 encoded file to Django InMemoryUploadedFile that can be placed into request.FILES."""
    # 'data:image/png;base64,<base64 encoded string>'
    try:
        idx = file_from_POST.find(",")  # comma should be pretty early on
        if not idx or not file_from_POST.startswith("data:image/"):
            raise Exception()

        base64file = file_from_POST[idx + 1 :]
        attributes = file_from_POST[:idx]
        content_type = attributes[len("data:") : attributes.find(";")]
        file_extension = content_type.split("/")[1]
    except Exception:
        raise SuspiciousOperation("Invalid picture")

    buffer = io.BytesIO(base64.b64decode(base64file))
    image = InMemoryUploadedFile(
        buffer,
        field_name="image",
        name=f"{uuid4()}.{file_extension}",  # use UUIDv4 or something
        content_type=content_type,
        size=len(buffer.getbuffer()),
        charset=None,
    )

    return image


def round_to_fixed_exponent(number):
    return Decimal(number).quantize(Decimal("0.01"))
