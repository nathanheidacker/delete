from pathlib import Path
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
import tempfile


def make_converter_getter():
    converter = None

    def get_converter() -> PdfConverter:
        nonlocal converter
        if converter is None:
            print("creating md converter")
            converter = PdfConverter(config={}, artifact_dict=create_model_dict())
            print("created md converter")
        return converter

    return get_converter


get_converter = make_converter_getter()


def save_pdf_to_tempfile(pdf_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(pdf_bytes)
        temp_file.flush()  # Ensure all data is written to disk
        return temp_file.name  # Return the file path


def convert(pdf: bytes) -> str:
    converter = get_converter()
    filename = save_pdf_to_tempfile(pdf)
    rendered = converter(filename)
    text, _, images = text_from_rendered(rendered)
    return text
