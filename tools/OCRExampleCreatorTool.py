"""
OCR Example Creator Tool

This tool extracts the first page from a PDF or converts an image to JPEG format,
saving it to a specified location for use as OCR reference examples.
"""

import os
from pathlib import Path
from typing import Type

from copilot.baseutils.logging_envvar import copilot_debug
from copilot.core.tool_input import ToolField, ToolInput
from copilot.core.tool_wrapper import ToolWrapper

SUPPORTED_MIME_FORMATS = {
    "JPEG": "image/jpeg",
    "JPG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "GIF": "image/gif",
    "PDF": "application/pdf",
}


class OCRExampleCreatorToolInput(ToolInput):
    path: str = ToolField(
        description="Absolute or relative path to the image or PDF file to use as reference. "
        "For PDFs, only the first page will be used. "
        "The file must exist in the local file system."
    )


def convert_to_pil_img(bitmap):
    """Converts a pypdfium2 bitmap to a PIL Image.

    Args:
        bitmap: The pypdfium2 bitmap object to convert.

    Returns:
        PIL.Image: The converted PIL Image object.
    """
    import pypdfium2.internal as pdfium_i
    import PIL.Image

    dest_mode = pdfium_i.BitmapTypeToStrReverse[bitmap.format]

    image = PIL.Image.frombuffer(
        dest_mode,
        (bitmap.width, bitmap.height),
        bitmap.buffer,
        "raw",
        bitmap.mode,
        bitmap.stride,
        1,
    )
    image.readonly = False
    return image


def read_mime(file_path):
    """Reads the MIME type of a file.

    Args:
        file_path (str): The path to the file to check.

    Returns:
        str or None: The MIME type of the file, or None if unable to determine.
    """
    import filetype

    try:
        guess_result = filetype.guess(file_path)
        mime = guess_result.mime if guess_result else None
    except Exception as e:
        copilot_debug(f"Error reading mime type: {e}")
        mime = None
    return mime


def get_file_path(input_params):
    """Resolves the file path from input parameters.

    Args:
        input_params (dict): The input parameters containing the path.

    Returns:
        str: The resolved absolute file path.
    """
    rel_path = input_params.get("path")
    file_path = "/app" + rel_path
    copilot_debug(f"Tool OCRExampleCreatorTool input: {file_path}")
    copilot_debug(f"Current directory: {os.getcwd()}")

    if not Path(file_path).exists():
        file_path = ".." + rel_path
    if not Path(file_path).exists():
        file_path = rel_path
    if not Path(file_path).is_file():
        raise FileNotFoundError(f"Filename {file_path} doesn't exist")

    return file_path


def extract_and_save_first_page(file_path, mime):
    """
    Extracts the first page/image from a file and saves it as a temporary JPEG.

    For PDFs: Renders the first page as a JPEG image
    For images: Converts to JPEG if needed

    Args:
        file_path: Path to the source file
        mime: MIME type of the source file

    Returns:
        str: Path to the temporary saved image
    """
    import pypdfium2 as pdfium
    from PIL import Image
    import tempfile

    # Create temporary file for output
    temp_fd, temp_path = tempfile.mkstemp(suffix=".jpeg", prefix="ocr_ref_")
    os.close(temp_fd)  # Close the file descriptor, we'll write with PIL

    if mime == SUPPORTED_MIME_FORMATS["PDF"]:
        # Extract first page from PDF
        pdf = pdfium.PdfDocument(file_path)
        if len(pdf) == 0:
            raise ValueError("PDF file has no pages")

        # Render first page
        page = pdf.get_page(0)
        bitmap = page.render()
        pil_image = convert_to_pil_img(bitmap)

        # Save as JPEG
        old_umask = os.umask(0o077)
        try:
            pil_image.save(temp_path, "JPEG")
            os.chmod(temp_path, 0o600)
        finally:
            os.umask(old_umask)

        copilot_debug(f"Extracted first page from PDF to: {temp_path}")

    elif mime in [SUPPORTED_MIME_FORMATS["JPEG"], SUPPORTED_MIME_FORMATS["JPG"]]:
        # Copy JPEG image directly
        import shutil

        old_umask = os.umask(0o077)
        try:
            shutil.copy2(file_path, temp_path)
            os.chmod(temp_path, 0o600)
        finally:
            os.umask(old_umask)
        copilot_debug(f"Copied JPEG image to: {temp_path}")

    else:
        # Convert other image formats to JPEG
        img = Image.open(file_path)
        img = img.convert("RGB")

        old_umask = os.umask(0o077)
        try:
            img.save(temp_path, "JPEG")
            os.chmod(temp_path, 0o600)
        finally:
            os.umask(old_umask)

        copilot_debug(f"Converted image to JPEG: {temp_path}")

    return temp_path


class OCRExampleCreatorTool(ToolWrapper):
    """
    Creates reference images from documents for OCR.

    This tool extracts the first page from a PDF or converts an image to JPEG format,
    saving it to a specified location. The generated images can be used as reference
    examples for OCR extraction.

    Workflow:
    1. Takes a document file (PDF or image)
    2. Extracts the first page (for PDFs) or converts the image
    3. Saves it as a JPEG file to the specified output path

    Best practices:
    - Add visual markers (red boxes) to highlight important fields before processing
    - Use representative examples of the document types you'll process
    - Save references in a organized directory structure
    """

    name: str = "OCRExampleCreatorTool"
    description: str = (
        "Extracts the first page from a PDF or converts an image to JPEG format, "
        "saving it to a temporary file. Use this to create reference images for OCR extraction. "
        "For PDFs, extracts and saves the first page as JPEG. "
        "For images, converts to JPEG format. Returns the path to the temporary file. "
        "Best practice: add visual markers (red boxes) to highlight important fields before processing. "
        "Supports: JPEG, PNG, WebP, GIF, and PDF files."
    )

    args_schema: Type[ToolInput] = OCRExampleCreatorToolInput

    def run(self, input_params, *args, **kwargs):
        """Executes the OCR example creation process.

        Args:
            input_params (dict): The input parameters for the tool.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            dict: A dictionary containing the result of the operation, including success status and file paths.
        """
        try:
            copilot_debug("OCRExampleCreatorTool started")

            # Get and validate input file
            file_path = get_file_path(input_params)
            mime = read_mime(file_path)

            if mime not in SUPPORTED_MIME_FORMATS.values():
                raise ValueError(
                    f"File {file_path} has unsupported format (mime: {mime}). "
                    f"Supported formats: {list(SUPPORTED_MIME_FORMATS.keys())}"
                )

            copilot_debug(f"Input file: {file_path}")

            # Extract and save first page/image to temporary file
            temp_output_path = extract_and_save_first_page(file_path, mime)

            return {
                "success": True,
                "message": "Reference image created successfully in temporary file",
                "input_file": file_path,
                "output_file": temp_output_path,
                "format": "JPEG",
            }

        except Exception as e:
            errmsg = f"An error occurred: {e}"
            copilot_debug(errmsg)
            return {"success": False, "error": errmsg}
