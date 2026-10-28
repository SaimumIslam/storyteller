"""OCR helper for image-based PDF pages. Tesseract + Bangla."""
from __future__ import annotations

from pathlib import Path

import pytesseract
from pdf2image import convert_from_path
from PIL import Image, ImageFilter, ImageOps


def _preprocess(img: Image.Image) -> Image.Image:
    img = img.convert("L")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.MedianFilter(size=3))
    img = img.point(lambda p: 255 if p > 160 else 0)
    return img


def ocr_pdf_page(pdf_path: Path, page_num: int, lang: str = "ben", dpi: int = 300) -> str:
    """OCR a single PDF page (1-indexed). Returns extracted text."""
    images = convert_from_path(
        str(pdf_path),
        dpi=dpi,
        first_page=page_num,
        last_page=page_num,
    )
    if not images:
        return ""
    img = _preprocess(images[0])
    return pytesseract.image_to_string(img, lang=lang).strip()


def ocr_image(img: Image.Image, lang: str = "ben") -> str:
    return pytesseract.image_to_string(_preprocess(img), lang=lang).strip()
