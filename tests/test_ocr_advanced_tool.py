import base64
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from langsmith import unit

from tools.OCRAdvancedTool import (
    GET_JSON_PROMPT,
    GET_JSON_WITH_REFERENCE_PROMPT,
    SUPPORTED_MIME_FORMATS,
    OCRAdvancedTool,
    OCRAdvancedToolInput,
    build_messages,
    checktype,
    cleanup_temp_files,
    convert_to_pil_img,
    get_file_path,
    get_image_payload_item,
    image_to_base64,
    read_mime,
    recopile_files,
)

IMAGE_JPEG = "image/jpeg"


class TestOCRAdvancedTool(unittest.TestCase):
    """Test suite for OCRAdvancedTool"""

    @unit
    def test_convert_to_pil_img(self):
        """Test bitmap to PIL image conversion"""
        # Mocking a bitmap object
        mock_bitmap = MagicMock()
        mock_bitmap.width = 100
        mock_bitmap.height = 100
        mock_bitmap.buffer = b"\x00" * (100 * 100 * 4)
        mock_bitmap.format = 2
        mock_bitmap.mode = "RGBA"
        mock_bitmap.stride = 400

        # Testing the conversion function
        pil_image = convert_to_pil_img(mock_bitmap)
        self.assertEqual(pil_image.size, (100, 100))

    @unit
    def test_get_image_payload_item(self):
        """Test image payload item creation for vision API"""
        img_b64 = "sample_base64"
        mime = IMAGE_JPEG
        expected_output = {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{img_b64}", "detail": "high"},
        }
        self.assertEqual(get_image_payload_item(img_b64, mime), expected_output)

    @unit
    def test_checktype_valid_mimes(self):
        """Test checktype with valid MIME types"""
        valid_mimes = [
            IMAGE_JPEG,
            "image/png",
            "image/webp",
            "image/gif",
            "application/pdf",
        ]
        for mime in valid_mimes:
            try:
                checktype("dummy_url", mime)
            except Exception:
                self.fail(f"checktype() raised Exception unexpectedly for mime: {mime}")

    @unit
    def test_checktype_invalid_mime(self):
        """Test checktype with invalid MIME type"""
        invalid_mime = "image/tiff"
        with self.assertRaises(ValueError) as context:
            checktype("dummy_url", invalid_mime)
        self.assertIn("invalid file format", str(context.exception))

    @patch("filetype.guess")
    @unit
    def test_read_mime(self, mock_guess):
        """Test MIME type reading from file"""
        # Test successful MIME detection
        mock_guess.return_value = MagicMock(mime=IMAGE_JPEG)
        self.assertEqual(read_mime("dummy_path"), IMAGE_JPEG)

        # Test failure case
        mock_guess.return_value = None
        self.assertIsNone(read_mime("dummy_path"))

    @unit
    def test_image_to_base64(self):
        """Test image to base64 conversion"""
        # Use a real test image
        test_image = "./tests/resources/images/etendo.png"
        if Path(test_image).exists():
            result = image_to_base64(test_image)
            self.assertIsInstance(result, str)
            self.assertGreater(len(result), 0)
            # Verify it's valid base64
            try:
                base64.b64decode(result)
            except Exception:
                self.fail("image_to_base64 did not return valid base64")

    @patch("tools.OCRAdvancedTool.Path")
    @unit
    def test_get_file_path_exists(self, mock_path):
        """Test file path resolution when file exists"""
        input_params = {"path": "/test/image.png"}
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.is_file.return_value = True
        mock_path.return_value = mock_path_instance

        result = get_file_path(input_params)
        self.assertEqual(result, "/app/test/image.png")

    @patch("tools.OCRAdvancedTool.Path")
    @unit
    def test_get_file_path_not_found(self, mock_path):
        """Test file path resolution when file doesn't exist"""
        input_params = {"path": "/nonexistent/image.png"}
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.is_file.return_value = False
        mock_path.return_value = mock_path_instance

        with self.assertRaises(FileNotFoundError):
            get_file_path(input_params)

    @unit
    def test_build_messages_without_reference(self):
        """Test message building without reference image"""
        base64_images = ["base64_image1", "base64_image2"]
        question = "Extract invoice data"

        messages = build_messages(base64_images, question)

        # Should have 2 image messages + 1 question message
        self.assertEqual(len(messages), 3)

        # Check image messages
        for i in range(2):
            self.assertEqual(messages[i]["role"], "user")
            self.assertIsInstance(messages[i]["content"], list)
            self.assertEqual(messages[i]["content"][0]["type"], "image_url")

        # Check question message
        self.assertEqual(messages[2]["role"], "user")
        self.assertEqual(messages[2]["content"], question)

    @unit
    def test_build_messages_with_reference(self):
        """Test message building with reference image"""
        base64_images = ["base64_image1"]
        question = "Extract data"
        reference_b64 = "reference_base64"

        messages = build_messages(base64_images, question, reference_b64)

        # Should have: 1 reference image + 1 reference text + 1 real image + 1 question = 4
        self.assertEqual(len(messages), 4)

        # Check reference image
        self.assertEqual(messages[0]["role"], "user")
        self.assertIsInstance(messages[0]["content"], list)

        # Check reference explanation text
        self.assertEqual(messages[1]["role"], "user")
        self.assertIn("REFERENCE", messages[1]["content"])

        # Check real image
        self.assertEqual(messages[2]["role"], "user")
        self.assertIsInstance(messages[2]["content"], list)

        # Check question
        self.assertEqual(messages[3]["role"], "user")
        self.assertEqual(messages[3]["content"], question)

    @unit
    def test_cleanup_temp_files(self):
        """Test temporary file cleanup"""
        # Create temporary test files
        temp_dir = "/tmp"
        test_files = []
        for i in range(2):
            temp_file = os.path.join(temp_dir, f"test_cleanup_{i}_{os.getpid()}.txt")
            with open(temp_file, "w") as f:
                f.write("test")
            test_files.append(temp_file)

        # Verify files exist
        for f in test_files:
            self.assertTrue(os.path.exists(f))

        # Clean up
        cleanup_temp_files(test_files)

        # Verify files are deleted
        for f in test_files:
            self.assertFalse(os.path.exists(f))

    @patch("tools.OCRAdvancedTool.image_to_base64")
    @patch("tools.OCRAdvancedTool.os.path.dirname")
    @unit
    def test_recopile_files_jpeg(self, mock_dirname, mock_img_to_b64):
        """Test recopile_files with JPEG image"""
        mock_dirname.return_value = "/tmp"
        mock_img_to_b64.return_value = "base64_data"

        base64_images = []
        filenames_to_delete = []
        mime = SUPPORTED_MIME_FORMATS["JPEG"]

        recopile_files(
            base64_images, filenames_to_delete, "/tmp", mime, "/tmp/test.jpg"
        )

        # Should add one base64 image
        self.assertEqual(len(base64_images), 1)
        self.assertEqual(base64_images[0], "base64_data")
        # No temp files for JPEG
        self.assertEqual(len(filenames_to_delete), 0)

    @patch("pypdfium2.PdfDocument")
    @patch("tools.OCRAdvancedTool.image_to_base64")
    @patch("tools.OCRAdvancedTool.convert_to_pil_img")
    @unit
    def test_recopile_files_pdf(self, mock_convert, mock_img_to_b64, mock_pdf_doc):
        """Test recopile_files with PDF file"""
        from PIL import Image

        # Mock PDF with 2 pages
        mock_pdf = MagicMock()
        mock_pdf.__len__.return_value = 2
        mock_page = MagicMock()
        mock_bitmap = MagicMock()
        mock_page.render.return_value = mock_bitmap
        mock_pdf.get_page.return_value = mock_page
        mock_pdf_doc.return_value = mock_pdf

        # Create a real RGB PIL image instead of RGBA
        mock_pil_image = Image.new("RGB", (100, 100), color="white")
        mock_convert.return_value = mock_pil_image
        mock_img_to_b64.return_value = "base64_page"

        base64_images = []
        filenames_to_delete = []
        mime = SUPPORTED_MIME_FORMATS["PDF"]

        recopile_files(
            base64_images, filenames_to_delete, "/tmp", mime, "/tmp/test.pdf"
        )

        # Should have 2 pages
        self.assertEqual(len(base64_images), 2)
        # Should have 2 temp files
        self.assertEqual(len(filenames_to_delete), 2)

        # Clean up temp files created during test
        for f in filenames_to_delete:
            if os.path.exists(f):
                os.remove(f)

    @patch("tools.OCRAdvancedTool.copilot_debug")
    @unit
    def test_ocr_advanced_tool_input_schema(self, mock_debug):
        """Test OCRAdvancedToolInput schema validation"""
        # Valid input
        valid_input = OCRAdvancedToolInput(
            path="/test/image.png", question="Extract data"
        )
        self.assertEqual(valid_input.path, "/test/image.png")
        self.assertEqual(valid_input.question, "Extract data")

    @unit
    def test_ocr_advanced_tool_run_without_agent(self):
        """Test OCRAdvancedTool.run without agent_id"""
        tool = OCRAdvancedTool()
        tool.agent_id = None

        input_params = {"path": "/test/image.png", "question": "Extract data"}

        result = tool.run(input_params)

        # Should return error about missing agent_id
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("agent_id", result["error"])

    @patch("tools.OCRAdvancedTool.cleanup_temp_files")
    @patch("tools.OCRAdvancedTool.Path")
    @patch("copilot.core.vectordb_utils.find_similar_reference")
    @patch("tools.OCRAdvancedTool.get_vision_model_response")
    @patch("tools.OCRAdvancedTool.prepare_images_for_ocr")
    @patch("tools.OCRAdvancedTool.read_mime")
    @patch("tools.OCRAdvancedTool.get_file_path")
    @patch("tools.OCRAdvancedTool.checktype")
    @unit
    def test_ocr_advanced_tool_run_with_reference(
        self,
        mock_checktype,
        mock_get_file_path,
        mock_read_mime,
        mock_prepare_images,
        mock_get_response,
        mock_find_ref,
        mock_path,
        mock_cleanup,
    ):
        """Test OCRAdvancedTool.run with reference image found"""
        tool = OCRAdvancedTool()
        tool.agent_id = "test_agent_123"

        # Mock Path.exists to return True for first_image_for_search
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        # Setup mocks
        mock_get_file_path.return_value = "/tmp/test.png"
        mock_read_mime.return_value = IMAGE_JPEG
        mock_prepare_images.return_value = (["base64_image"], [])
        mock_find_ref.return_value = ("/path/to/reference.png", "ref_base64")
        mock_get_response.return_value = '{"invoice_number": "12345"}'

        input_params = {"path": "/test/image.png", "question": "Extract invoice"}

        result = tool.run(input_params)

        # Verify result
        self.assertIsInstance(result, str)
        self.assertIn("invoice_number", result)

        # Verify reference was searched
        mock_find_ref.assert_called_once()
        # Verify cleanup was called
        mock_cleanup.assert_called_once()

    @patch("tools.OCRAdvancedTool.cleanup_temp_files")
    @patch("tools.OCRAdvancedTool.Path")
    @patch("copilot.core.vectordb_utils.find_similar_reference")
    @patch("tools.OCRAdvancedTool.get_vision_model_response")
    @patch("tools.OCRAdvancedTool.prepare_images_for_ocr")
    @patch("tools.OCRAdvancedTool.read_mime")
    @patch("tools.OCRAdvancedTool.get_file_path")
    @patch("tools.OCRAdvancedTool.checktype")
    @unit
    def test_ocr_advanced_tool_run_without_reference(
        self,
        mock_checktype,
        mock_get_file_path,
        mock_read_mime,
        mock_prepare_images,
        mock_get_response,
        mock_find_ref,
        mock_path,
        mock_cleanup,
    ):
        """Test OCRAdvancedTool.run without reference image"""
        tool = OCRAdvancedTool()
        tool.agent_id = "test_agent_123"

        # Mock Path.exists to return True for first_image_for_search
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        # Setup mocks
        mock_get_file_path.return_value = "/tmp/test.png"
        mock_read_mime.return_value = IMAGE_JPEG
        mock_prepare_images.return_value = (["base64_image"], [])
        mock_find_ref.return_value = (None, None)  # No reference found
        mock_get_response.return_value = '{"data": "extracted"}'

        input_params = {"path": "/test/image.png"}

        result = tool.run(input_params)

        # Verify result
        self.assertIsInstance(result, str)
        self.assertIn("data", result)

        # Verify reference was searched but not found
        mock_find_ref.assert_called_once()

    @patch("tools.OCRAdvancedTool.get_file_path")
    @unit
    def test_ocr_advanced_tool_run_file_not_found(self, mock_get_file_path):
        """Test OCRAdvancedTool.run with file not found"""
        tool = OCRAdvancedTool()
        tool.agent_id = "test_agent_123"

        mock_get_file_path.side_effect = FileNotFoundError("File not found")

        input_params = {"path": "/nonexistent/image.png"}

        result = tool.run(input_params)

        # Should return error
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)

    @patch("tools.OCRAdvancedTool.checktype")
    @patch("tools.OCRAdvancedTool.read_mime")
    @patch("tools.OCRAdvancedTool.get_file_path")
    @unit
    def test_ocr_advanced_tool_run_invalid_mime(
        self, mock_get_file_path, mock_read_mime, mock_checktype
    ):
        """Test OCRAdvancedTool.run with invalid MIME type"""
        tool = OCRAdvancedTool()
        tool.agent_id = "test_agent_123"

        mock_get_file_path.return_value = "/tmp/test.tiff"
        mock_read_mime.return_value = "image/tiff"
        mock_checktype.side_effect = ValueError("Invalid format")

        input_params = {"path": "/test/image.tiff"}

        result = tool.run(input_params)

        # Should return error
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)

    def test_ocr_advanced_tool_constants(self):
        """Test that required constants are defined"""
        self.assertIsNotNone(GET_JSON_PROMPT)
        self.assertIn("JSON", GET_JSON_PROMPT)

        self.assertIsNotNone(GET_JSON_WITH_REFERENCE_PROMPT)
        self.assertIn("reference", GET_JSON_WITH_REFERENCE_PROMPT.lower())

        self.assertIsInstance(SUPPORTED_MIME_FORMATS, dict)
        self.assertIn("JPEG", SUPPORTED_MIME_FORMATS)
        self.assertIn("PDF", SUPPORTED_MIME_FORMATS)

    @unit
    def test_ocr_advanced_tool_metadata(self):
        """Test OCRAdvancedTool metadata"""
        tool = OCRAdvancedTool()

        self.assertEqual(tool.name, "OCRAdvancedTool")
        self.assertIsNotNone(tool.description)
        self.assertIn("structured data", tool.description.lower())
        self.assertEqual(tool.args_schema, OCRAdvancedToolInput)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    unittest.main()
