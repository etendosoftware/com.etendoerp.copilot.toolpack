import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from langsmith import unit

from tools.OCRExampleCreatorTool import (
    SUPPORTED_MIME_FORMATS,
    OCRExampleCreatorTool,
    OCRExampleCreatorToolInput,
    convert_to_pil_img,
    extract_and_save_first_page,
    get_file_path,
    read_mime,
)


class TestOCRExampleCreatorTool(unittest.TestCase):
    """Test suite for OCRExampleCreatorTool"""

    @unit
    def test_convert_to_pil_img(self):
        """Test bitmap to PIL image conversion"""
        mock_bitmap = MagicMock()
        mock_bitmap.width = 100
        mock_bitmap.height = 100
        mock_bitmap.buffer = b"\x00" * (100 * 100 * 4)
        mock_bitmap.format = 2
        mock_bitmap.mode = "RGBA"
        mock_bitmap.stride = 400

        pil_image = convert_to_pil_img(mock_bitmap)
        self.assertEqual(pil_image.size, (100, 100))

    @patch("filetype.guess")
    @unit
    def test_read_mime_success(self, mock_guess):
        """Test MIME type reading from file - success case"""
        mock_guess.return_value = MagicMock(mime="image/jpeg")
        result = read_mime("dummy_path")
        self.assertEqual(result, "image/jpeg")

    @patch("filetype.guess")
    @unit
    def test_read_mime_failure(self, mock_guess):
        """Test MIME type reading from file - failure case"""
        mock_guess.return_value = None
        result = read_mime("dummy_path")
        self.assertIsNone(result)

    @patch("filetype.guess")
    @unit
    def test_read_mime_exception(self, mock_guess):
        """Test MIME type reading handles exceptions"""
        mock_guess.side_effect = Exception("File error")
        result = read_mime("dummy_path")
        self.assertIsNone(result)

    @patch("tools.OCRExampleCreatorTool.Path")
    @unit
    def test_get_file_path_with_app_prefix(self, mock_path):
        """Test file path resolution with /app prefix"""
        input_params = {"path": "/test/image.png"}
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.is_file.return_value = True
        mock_path.return_value = mock_path_instance

        result = get_file_path(input_params)
        self.assertEqual(result, "/app/test/image.png")

    @patch("tools.OCRExampleCreatorTool.Path")
    @unit
    def test_get_file_path_with_relative_prefix(self, mock_path):
        """Test file path resolution falls back to relative path"""
        input_params = {"path": "/test/image.png"}
        mock_path_instance = MagicMock()
        # First call (/app prefix) returns False, second (.. prefix) returns True
        mock_path_instance.exists.side_effect = [False, True]
        mock_path_instance.is_file.return_value = True
        mock_path.return_value = mock_path_instance

        result = get_file_path(input_params)
        self.assertEqual(result, "../test/image.png")

    @patch("tools.OCRExampleCreatorTool.Path")
    @unit
    def test_get_file_path_direct_path(self, mock_path):
        """Test file path resolution uses direct path as last resort"""
        input_params = {"path": "/test/image.png"}
        mock_path_instance = MagicMock()
        # /app and .. prefixes fail, direct path works
        mock_path_instance.exists.side_effect = [False, False]
        mock_path_instance.is_file.return_value = True
        mock_path.return_value = mock_path_instance

        result = get_file_path(input_params)
        self.assertEqual(result, "/test/image.png")

    @patch("tools.OCRExampleCreatorTool.Path")
    @unit
    def test_get_file_path_not_found(self, mock_path):
        """Test file path resolution when file doesn't exist"""
        input_params = {"path": "/nonexistent/image.png"}
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = False
        mock_path_instance.is_file.return_value = False
        mock_path.return_value = mock_path_instance

        with self.assertRaises(FileNotFoundError):
            get_file_path(input_params)

    @unit
    def test_ocr_example_creator_tool_input_schema(self):
        """Test OCRExampleCreatorToolInput schema validation"""
        valid_input = OCRExampleCreatorToolInput(path="/test/image.png")
        self.assertEqual(valid_input.path, "/test/image.png")

    @unit
    def test_ocr_example_creator_tool_metadata(self):
        """Test OCRExampleCreatorTool metadata"""
        tool = OCRExampleCreatorTool()

        self.assertEqual(tool.name, "OCRExampleCreatorTool")
        self.assertIsNotNone(tool.description)
        self.assertIn("PDF", tool.description)
        self.assertIn("JPEG", tool.description)
        self.assertEqual(tool.args_schema, OCRExampleCreatorToolInput)

    @unit
    def test_supported_mime_formats(self):
        """Test that required MIME formats are defined"""
        self.assertIn("JPEG", SUPPORTED_MIME_FORMATS)
        self.assertIn("JPG", SUPPORTED_MIME_FORMATS)
        self.assertIn("PNG", SUPPORTED_MIME_FORMATS)
        self.assertIn("WEBP", SUPPORTED_MIME_FORMATS)
        self.assertIn("GIF", SUPPORTED_MIME_FORMATS)
        self.assertIn("PDF", SUPPORTED_MIME_FORMATS)

        self.assertEqual(SUPPORTED_MIME_FORMATS["JPEG"], "image/jpeg")
        self.assertEqual(SUPPORTED_MIME_FORMATS["PDF"], "application/pdf")

    @patch("tools.OCRExampleCreatorTool.extract_and_save_first_page")
    @patch("tools.OCRExampleCreatorTool.read_mime")
    @patch("tools.OCRExampleCreatorTool.get_file_path")
    @unit
    def test_ocr_example_creator_tool_run_success(
        self, mock_get_file_path, mock_read_mime, mock_extract
    ):
        """Test OCRExampleCreatorTool.run success case"""
        tool = OCRExampleCreatorTool()

        temp_dir = tempfile.gettempdir()
        mock_get_file_path.return_value = os.path.join(temp_dir, "test.png")
        mock_read_mime.return_value = "image/png"
        mock_extract.return_value = os.path.join(temp_dir, "output.jpeg")

        input_params = {"path": "/test/image.png"}
        result = tool.run(input_params)

        self.assertIsInstance(result, dict)
        self.assertTrue(result["success"])
        self.assertEqual(result["format"], "JPEG")
        self.assertIn("output_file", result)
        mock_extract.assert_called_once()

    @patch("tools.OCRExampleCreatorTool.read_mime")
    @patch("tools.OCRExampleCreatorTool.get_file_path")
    @unit
    def test_ocr_example_creator_tool_run_unsupported_format(
        self, mock_get_file_path, mock_read_mime
    ):
        """Test OCRExampleCreatorTool.run with unsupported format"""
        tool = OCRExampleCreatorTool()

        temp_dir = tempfile.gettempdir()
        mock_get_file_path.return_value = os.path.join(temp_dir, "test.tiff")
        mock_read_mime.return_value = "image/tiff"

        input_params = {"path": "/test/image.tiff"}
        result = tool.run(input_params)

        self.assertIsInstance(result, dict)
        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertIn("unsupported format", result["error"])

    @patch("tools.OCRExampleCreatorTool.get_file_path")
    @unit
    def test_ocr_example_creator_tool_run_file_not_found(self, mock_get_file_path):
        """Test OCRExampleCreatorTool.run with file not found"""
        tool = OCRExampleCreatorTool()

        mock_get_file_path.side_effect = FileNotFoundError("File not found")

        input_params = {"path": "/nonexistent/image.png"}
        result = tool.run(input_params)

        self.assertIsInstance(result, dict)
        self.assertFalse(result["success"])
        self.assertIn("error", result)

    @patch("pypdfium2.PdfDocument")
    @patch("tools.OCRExampleCreatorTool.convert_to_pil_img")
    @unit
    def test_extract_and_save_first_page_pdf(self, mock_convert, mock_pdf_doc):
        """Test extract_and_save_first_page with PDF file"""
        from PIL import Image

        # Mock PDF with 1 page
        mock_pdf = MagicMock()
        mock_pdf.__len__.return_value = 1
        mock_page = MagicMock()
        mock_bitmap = MagicMock()
        mock_page.render.return_value = mock_bitmap
        mock_pdf.get_page.return_value = mock_page
        mock_pdf_doc.return_value = mock_pdf

        # Create a real RGB PIL image
        mock_pil_image = Image.new("RGB", (100, 100), color="white")
        mock_convert.return_value = mock_pil_image

        # Create a temporary file to use as input (won't be read for PDF)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            result = extract_and_save_first_page(tmp_path, SUPPORTED_MIME_FORMATS["PDF"])

            self.assertTrue(os.path.exists(result))
            self.assertTrue(result.endswith(".jpeg"))

            # Verify the file was created with proper permissions
            file_stat = os.stat(result)
            self.assertEqual(file_stat.st_mode & 0o777, 0o600)

            # Cleanup output
            os.unlink(result)
        finally:
            os.unlink(tmp_path)

    @patch("pypdfium2.PdfDocument")
    @unit
    def test_extract_and_save_first_page_pdf_empty(self, mock_pdf_doc):
        """Test extract_and_save_first_page with empty PDF"""
        mock_pdf = MagicMock()
        mock_pdf.__len__.return_value = 0
        mock_pdf_doc.return_value = mock_pdf

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with self.assertRaises(ValueError) as context:
                extract_and_save_first_page(tmp_path, SUPPORTED_MIME_FORMATS["PDF"])
            self.assertIn("no pages", str(context.exception))
        finally:
            os.unlink(tmp_path)

    @unit
    def test_extract_and_save_first_page_jpeg(self):
        """Test extract_and_save_first_page with JPEG file (copy)"""
        from PIL import Image

        # Create a temporary JPEG file
        with tempfile.NamedTemporaryFile(suffix=".jpeg", delete=False) as tmp:
            img = Image.new("RGB", (100, 100), color="red")
            img.save(tmp.name, "JPEG")
            tmp_path = tmp.name

        try:
            result = extract_and_save_first_page(tmp_path, SUPPORTED_MIME_FORMATS["JPEG"])

            self.assertTrue(os.path.exists(result))
            self.assertTrue(result.endswith(".jpeg"))
            self.assertNotEqual(result, tmp_path)  # Should be a copy

            # Verify the file was created with proper permissions
            file_stat = os.stat(result)
            self.assertEqual(file_stat.st_mode & 0o777, 0o600)

            # Cleanup output
            os.unlink(result)
        finally:
            os.unlink(tmp_path)

    @unit
    def test_extract_and_save_first_page_png(self):
        """Test extract_and_save_first_page with PNG file (convert to JPEG)"""
        from PIL import Image

        # Create a temporary PNG file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            img = Image.new("RGB", (100, 100), color="blue")
            img.save(tmp.name, "PNG")
            tmp_path = tmp.name

        try:
            result = extract_and_save_first_page(tmp_path, SUPPORTED_MIME_FORMATS["PNG"])

            self.assertTrue(os.path.exists(result))
            self.assertTrue(result.endswith(".jpeg"))

            # Verify the output is a valid JPEG
            output_img = Image.open(result)
            self.assertEqual(output_img.format, "JPEG")

            # Verify the file was created with proper permissions
            file_stat = os.stat(result)
            self.assertEqual(file_stat.st_mode & 0o777, 0o600)

            # Cleanup output
            os.unlink(result)
        finally:
            os.unlink(tmp_path)

    @unit
    def test_extract_and_save_first_page_webp(self):
        """Test extract_and_save_first_page with WebP file (convert to JPEG)"""
        from PIL import Image

        # Create a temporary WebP file
        with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as tmp:
            img = Image.new("RGB", (100, 100), color="green")
            img.save(tmp.name, "WEBP")
            tmp_path = tmp.name

        try:
            result = extract_and_save_first_page(tmp_path, SUPPORTED_MIME_FORMATS["WEBP"])

            self.assertTrue(os.path.exists(result))
            self.assertTrue(result.endswith(".jpeg"))

            # Verify the output is a valid JPEG
            output_img = Image.open(result)
            self.assertEqual(output_img.format, "JPEG")

            # Cleanup output
            os.unlink(result)
        finally:
            os.unlink(tmp_path)

    @unit
    def test_extract_and_save_first_page_gif(self):
        """Test extract_and_save_first_page with GIF file (convert to JPEG)"""
        from PIL import Image

        # Create a temporary GIF file
        with tempfile.NamedTemporaryFile(suffix=".gif", delete=False) as tmp:
            img = Image.new("RGB", (100, 100), color="yellow")
            img.save(tmp.name, "GIF")
            tmp_path = tmp.name

        try:
            result = extract_and_save_first_page(tmp_path, SUPPORTED_MIME_FORMATS["GIF"])

            self.assertTrue(os.path.exists(result))
            self.assertTrue(result.endswith(".jpeg"))

            # Verify the output is a valid JPEG
            output_img = Image.open(result)
            self.assertEqual(output_img.format, "JPEG")

            # Cleanup output
            os.unlink(result)
        finally:
            os.unlink(tmp_path)

    @patch("tools.OCRExampleCreatorTool.extract_and_save_first_page")
    @patch("tools.OCRExampleCreatorTool.read_mime")
    @patch("tools.OCRExampleCreatorTool.get_file_path")
    @unit
    def test_ocr_example_creator_tool_run_pdf(
        self, mock_get_file_path, mock_read_mime, mock_extract
    ):
        """Test OCRExampleCreatorTool.run with PDF file"""
        tool = OCRExampleCreatorTool()

        temp_dir = tempfile.gettempdir()
        mock_get_file_path.return_value = os.path.join(temp_dir, "test.pdf")
        mock_read_mime.return_value = "application/pdf"
        mock_extract.return_value = os.path.join(temp_dir, "output.jpeg")

        input_params = {"path": "/test/document.pdf"}
        result = tool.run(input_params)

        self.assertIsInstance(result, dict)
        self.assertTrue(result["success"])
        self.assertEqual(result["format"], "JPEG")
        self.assertIn("reference", result["message"].lower())

    @patch("tools.OCRExampleCreatorTool.extract_and_save_first_page")
    @patch("tools.OCRExampleCreatorTool.read_mime")
    @patch("tools.OCRExampleCreatorTool.get_file_path")
    @unit
    def test_ocr_example_creator_tool_run_exception(
        self, mock_get_file_path, mock_read_mime, mock_extract
    ):
        """Test OCRExampleCreatorTool.run handles exceptions gracefully"""
        tool = OCRExampleCreatorTool()

        temp_dir = tempfile.gettempdir()
        mock_get_file_path.return_value = os.path.join(temp_dir, "test.png")
        mock_read_mime.return_value = "image/png"
        mock_extract.side_effect = Exception("Unexpected error during extraction")

        input_params = {"path": "/test/image.png"}
        result = tool.run(input_params)

        self.assertIsInstance(result, dict)
        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertIn("Unexpected error", result["error"])

    @patch("tools.OCRExampleCreatorTool.extract_and_save_first_page")
    @patch("tools.OCRExampleCreatorTool.read_mime")
    @patch("tools.OCRExampleCreatorTool.get_file_path")
    @unit
    def test_ocr_example_creator_tool_run_returns_paths(
        self, mock_get_file_path, mock_read_mime, mock_extract
    ):
        """Test OCRExampleCreatorTool.run returns both input and output paths"""
        tool = OCRExampleCreatorTool()

        temp_dir = tempfile.gettempdir()
        input_path = os.path.join(temp_dir, "input.png")
        output_path = os.path.join(temp_dir, "output.jpeg")

        mock_get_file_path.return_value = input_path
        mock_read_mime.return_value = "image/png"
        mock_extract.return_value = output_path

        input_params = {"path": "/test/image.png"}
        result = tool.run(input_params)

        self.assertEqual(result["input_file"], input_path)
        self.assertEqual(result["output_file"], output_path)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    unittest.main()
