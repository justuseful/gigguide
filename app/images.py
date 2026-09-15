import secrets
from pathlib import Path

from flask import current_app
from PIL import Image, ImageOps

ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "webp", "gif"}
MAX_DIMENSION = 1600


def save_image(file, max_dimension: int = MAX_DIMENSION) -> str | None:
    """Save an uploaded image, downscaling it if it's larger than max_dimension."""
    if file is None or not file.filename:
        return None
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_IMAGE_EXT:
        raise ValueError("Image must be png, jpg, webp or gif.")
    name = f"{secrets.token_hex(8)}.{ext}"
    path = Path(current_app.config["UPLOAD_DIR"]) / name
    file.save(path)
    if ext != "gif":  # avoid flattening animated gifs
        try:
            with Image.open(path) as img:
                img = ImageOps.exif_transpose(img)
                if img.width > max_dimension or img.height > max_dimension:
                    img.thumbnail((max_dimension, max_dimension))
                img.save(path)
        except Exception:
            current_app.logger.warning("Could not process image %s", name)
    return name


def delete_image(name: str | None):
    if not name:
        return
    try:
        (Path(current_app.config["UPLOAD_DIR"]) / name).unlink(missing_ok=True)
    except OSError:
        current_app.logger.warning("Could not delete image %s", name)
