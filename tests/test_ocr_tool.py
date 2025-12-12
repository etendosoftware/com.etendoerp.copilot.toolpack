import base64
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from langsmith import unit

from tools.OcrTool import (
    GET_JSON_PROMPT,
    GET_JSON_WITH_REFERENCE_PROMPT,
    SUPPORTED_MIME_FORMATS,
    OcrTool,
    OcrToolInput,
    build_messages,
    checktype,
    cleanup_temp_files,
    convert_to_pil_img,
    get_file_path,
    get_image_payload_item,
    get_llm_model,
    get_vision_model_response,
    image_to_base64,
    pil_image_to_base64,
    prepare_images_for_ocr,
    read_mime,
    recopile_files,
)

IMAGE_JPEG = "image/jpeg"


class TestOcrTool(unittest.TestCase):
    """Test suite for OcrTool"""

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
        # Test OpenAI format (default)
        expected_output = {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{img_b64}", "detail": "high"},
        }
        self.assertEqual(
            get_image_payload_item(img_b64, mime, provider="openai"), expected_output
        )
        self.assertEqual(
            get_image_payload_item(img_b64, mime, provider="openai"), expected_output
        )

    @unit
    def test_get_image_payload_item_gemini(self):
        """Test image payload item creation for Gemini model (no detail field)"""
        img_b64 = "sample_base64"
        mime = IMAGE_JPEG
        expected_output = {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{img_b64}"},
        }
        self.assertEqual(
            get_image_payload_item(img_b64, mime, provider="gemini"), expected_output
        )

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

    @unit
    def test_pil_image_to_base64(self):
        """Test PIL image to base64 conversion without disk I/O"""
        from PIL import Image

        # Create a test PIL image
        test_image = Image.new("RGB", (100, 100), color="red")

        result = pil_image_to_base64(test_image)

        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)
        # Verify it's valid base64
        try:
            base64.b64decode(result)
        except Exception:
            self.fail("pil_image_to_base64 did not return valid base64")

    @unit
    def test_pil_image_to_base64_with_options(self):
        """Test PIL image to base64 with different format and quality"""
        from PIL import Image

        test_image = Image.new("RGB", (100, 100), color="blue")

        # Test with different quality
        result_low = pil_image_to_base64(test_image, format="JPEG", quality=50)
        result_high = pil_image_to_base64(test_image, format="JPEG", quality=95)

        self.assertIsInstance(result_low, str)
        self.assertIsInstance(result_high, str)
        # Higher quality should produce larger output
        self.assertGreater(len(result_high), len(result_low))

    @patch("tools.OcrTool.Path")
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

    @patch("tools.OcrTool.Path")
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

        # Should have: 1 system message + 1 question message + 2 image messages = 4
        self.assertEqual(len(messages), 4)

        # Check system message
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("OCR", messages[0]["content"])

        # Check question message
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(messages[1]["content"], question)

        # Check image messages (come after the question)
        for i in range(2, 4):
            self.assertEqual(messages[i]["role"], "user")
            self.assertIsInstance(messages[i]["content"], list)
            self.assertEqual(messages[i]["content"][0]["type"], "image_url")

    @unit
    def test_build_messages_with_extra_system_content(self):
        """Test message building with extra system content"""
        base64_images = ["base64_image1"]
        question = "Extract data"
        extra_system = "Additional instructions for structured output"

        messages = build_messages(
            base64_images, question, extra_system_content=extra_system
        )

        # Check system message contains extra content
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("OCR", messages[0]["content"])
        self.assertIn(extra_system, messages[0]["content"])

    @unit
    def test_build_messages_gemini_format(self):
        """Test message building with Gemini format (no detail field)"""
        base64_images = ["base64_image1"]
        question = "Extract data"

        messages = build_messages(base64_images, question, provider="gemini")

        # Check that image payload doesn't have detail field (Gemini format)
        image_message = messages[2]  # After system and question
        self.assertIsInstance(image_message["content"], list)
        image_payload = image_message["content"][0]
        self.assertNotIn("detail", image_payload.get("image_url", {}))

    @unit
    def test_build_messages_with_reference(self):
        """Test message building with reference image"""
        base64_images = ["base64_image1"]
        question = "Extract data"
        reference_b64 = "reference_base64"

        messages = build_messages(base64_images, question, reference_b64)

        # Should have: 1 system + 1 ref explanation + 1 ref image + 1 assistant response + 1 question + 1 real image = 6
        self.assertEqual(len(messages), 6)

        # Check system message
        self.assertEqual(messages[0]["role"], "system")

        # Check reference explanation text
        self.assertEqual(messages[1]["role"], "user")
        self.assertIn("REFERENCE", messages[1]["content"])

        # Check reference image
        self.assertEqual(messages[2]["role"], "user")
        self.assertIsInstance(messages[2]["content"], list)

        # Check assistant acknowledgment
        self.assertEqual(messages[3]["role"], "assistant")

        # Check question
        self.assertEqual(messages[4]["role"], "user")
        self.assertEqual(messages[4]["content"], question)

        # Check real image
        self.assertEqual(messages[5]["role"], "user")
        self.assertIsInstance(messages[5]["content"], list)

    @unit
    def test_cleanup_temp_files(self):
        """Test temporary file cleanup"""
        # Create temporary test files using tempfile module for safety
        test_files = []
        for i in range(2):
            fd, temp_file = tempfile.mkstemp(suffix=f"_test_cleanup_{i}.txt")
            os.write(fd, b"test")
            os.close(fd)
            test_files.append(temp_file)

        # Verify files exist
        for f in test_files:
            self.assertTrue(os.path.exists(f))

        # Clean up
        cleanup_temp_files(test_files)

        # Verify files are deleted
        for f in test_files:
            self.assertFalse(os.path.exists(f))

    @patch("tools.OcrTool.image_to_base64")
    @patch("tools.OcrTool.os.path.dirname")
    @unit
    def test_recopile_files_jpeg(self, mock_dirname, mock_img_to_b64):
        """Test recopile_files with JPEG image"""
        temp_dir = tempfile.gettempdir()
        mock_dirname.return_value = temp_dir
        mock_img_to_b64.return_value = "base64_data"

        base64_images = []
        filenames_to_delete = []
        mime = SUPPORTED_MIME_FORMATS["JPEG"]

        recopile_files(
            base64_images,
            filenames_to_delete,
            temp_dir,
            mime,
            os.path.join(temp_dir, "test.jpg"),
            2.0,
        )

        # Should add one base64 image
        self.assertEqual(len(base64_images), 1)
        self.assertEqual(base64_images[0], "base64_data")
        # No temp files for JPEG
        self.assertEqual(len(filenames_to_delete), 0)

    @patch("pypdfium2.PdfDocument")
    @patch("tools.OcrTool.pil_image_to_base64")
    @patch("tools.OcrTool.convert_to_pil_img")
    @unit
    def test_recopile_files_pdf(self, mock_convert, mock_pil_to_b64, mock_pdf_doc):
        """Test recopile_files with PDF file"""
        from PIL import Image

        temp_dir = tempfile.gettempdir()

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
        mock_pil_to_b64.return_value = "base64_page"

        base64_images = []
        filenames_to_delete = []
        mime = SUPPORTED_MIME_FORMATS["PDF"]

        recopile_files(
            base64_images,
            filenames_to_delete,
            temp_dir,
            mime,
            os.path.join(temp_dir, "test.pdf"),
            2.0,
        )

        # Should have 2 pages
        self.assertEqual(len(base64_images), 2)
        # No temp files anymore - PDFs are converted directly in memory
        self.assertEqual(len(filenames_to_delete), 0)

    @patch("tools.OcrTool.recopile_files")
    @unit
    def test_prepare_images_for_ocr(self, mock_recopile):
        """Test prepare_images_for_ocr function"""
        mock_recopile.side_effect = (
            lambda imgs, files, folder, mime, url, scale: imgs.append("base64_data")
        )

        temp_dir = tempfile.gettempdir()
        base64_images, filenames_to_delete = prepare_images_for_ocr(
            os.path.join(temp_dir, "test.jpg"), IMAGE_JPEG, 2.0
        )

        self.assertEqual(len(base64_images), 1)
        self.assertEqual(base64_images[0], "base64_data")
        self.assertIsInstance(filenames_to_delete, list)
        mock_recopile.assert_called_once()

    @patch("tools.OcrTool.pil_image_to_base64")
    @unit
    def test_recopile_files_non_jpeg_image(self, mock_pil_to_b64):
        """Test recopile_files with non-JPEG image (e.g., PNG) converts to JPEG in memory"""
        from PIL import Image

        mock_pil_to_b64.return_value = "base64_converted"

        # Create a temporary PNG file for the test
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            img = Image.new("RGB", (100, 100), color="green")
            img.save(tmp.name, "PNG")
            tmp_path = tmp.name

        try:
            base64_images = []
            filenames_to_delete = []
            mime = SUPPORTED_MIME_FORMATS["PNG"]
            temp_dir = tempfile.gettempdir()

            recopile_files(
                base64_images, filenames_to_delete, temp_dir, mime, tmp_path, 2.0
            )

            # Should have 1 converted image
            self.assertEqual(len(base64_images), 1)
            # No temp files - conversion happens in memory
            self.assertEqual(len(filenames_to_delete), 0)
            mock_pil_to_b64.assert_called_once()
        finally:
            os.unlink(tmp_path)

    @patch("tools.OcrTool.copilot_debug")
    @unit
    def test_ocr_tool_input_schema(self, mock_debug):
        """Test OcrTool schema validation"""
        # Valid input with required fields only
        valid_input = OcrToolInput(path="/test/image.png", question="Extract data")
        self.assertEqual(valid_input.path, "/test/image.png")
        self.assertEqual(valid_input.question, "Extract data")
        # Check default values for optional fields
        self.assertIsNone(valid_input.structured_output)
        self.assertFalse(valid_input.force_structured_output_compat)
        self.assertFalse(valid_input.disable_threshold_filter)
        self.assertEqual(valid_input.scale, 2.0)

    @patch("tools.OcrTool.copilot_debug")
    @unit
    def test_ocr_tool_input_schema_with_optional_fields(self, mock_debug):
        """Test OcrTool schema validation with all optional fields"""
        valid_input = OcrToolInput(
            path="/test/image.png",
            question="Extract data",
            structured_output="Invoice",
            force_structured_output_compat=True,
            disable_threshold_filter=True,
            scale=3.0,
        )
        self.assertEqual(valid_input.path, "/test/image.png")
        self.assertEqual(valid_input.question, "Extract data")
        self.assertEqual(valid_input.structured_output, "Invoice")
        self.assertTrue(valid_input.force_structured_output_compat)
        self.assertTrue(valid_input.disable_threshold_filter)
        self.assertEqual(valid_input.scale, 3.0)

    @unit
    def test_ocr_tool_run_without_agent(self):
        """Test OcrTool.run without agent_id"""
        tool = OcrTool()
        tool.agent_id = None

        input_params = {"path": "/test/image.png", "question": "Extract data"}

        result = tool.run(input_params)

        # Should return error about missing agent_id
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("agent_id", result["error"])

    @patch("tools.OcrTool.cleanup_temp_files")
    @patch("tools.OcrTool.Path")
    @patch("copilot.core.vectordb_utils.find_similar_reference")
    @patch("tools.OcrTool.get_vision_model_response")
    @patch("tools.OcrTool.prepare_images_for_ocr")
    @patch("tools.OcrTool.read_mime")
    @patch("tools.OcrTool.get_file_path")
    @patch("tools.OcrTool.checktype")
    @unit
    def test_ocr_tool_run_with_reference(
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
        """Test OcrTool.run with reference image found"""
        tool = OcrTool()
        tool.agent_id = "test_agent_123"

        # Mock Path.exists to return True for first_image_for_search
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        # Setup mocks
        temp_dir = tempfile.gettempdir()
        mock_get_file_path.return_value = os.path.join(temp_dir, "test.png")
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

    @patch("tools.OcrTool.cleanup_temp_files")
    @patch("tools.OcrTool.Path")
    @patch("copilot.core.vectordb_utils.find_similar_reference")
    @patch("tools.OcrTool.get_vision_model_response")
    @patch("tools.OcrTool.prepare_images_for_ocr")
    @patch("tools.OcrTool.read_mime")
    @patch("tools.OcrTool.get_file_path")
    @patch("tools.OcrTool.checktype")
    @unit
    def test_ocr_tool_run_without_reference(
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
        """Test OcrTool.run without reference image"""
        tool = OcrTool()
        tool.agent_id = "test_agent_123"

        # Mock Path.exists to return True for first_image_for_search
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        # Setup mocks
        temp_dir = tempfile.gettempdir()
        mock_get_file_path.return_value = os.path.join(temp_dir, "test.png")
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

    @patch("tools.OcrTool.get_file_path")
    @unit
    def test_ocr_tool_run_file_not_found(self, mock_get_file_path):
        """Test OcrTool.run with file not found"""
        tool = OcrTool()
        tool.agent_id = "test_agent_123"

        mock_get_file_path.side_effect = FileNotFoundError("File not found")

        input_params = {"path": "/nonexistent/image.png"}

        result = tool.run(input_params)

        # Should return error
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)

    @patch("tools.OcrTool.checktype")
    @patch("tools.OcrTool.read_mime")
    @patch("tools.OcrTool.get_file_path")
    @unit
    def test_ocr_tool_run_invalid_mime(
        self, mock_get_file_path, mock_read_mime, mock_checktype
    ):
        """Test OcrTool.run with invalid MIME type"""
        tool = OcrTool()
        tool.agent_id = "test_agent_123"

        temp_dir = tempfile.gettempdir()
        mock_get_file_path.return_value = os.path.join(temp_dir, "test.tiff")
        mock_read_mime.return_value = "image/tiff"
        mock_checktype.side_effect = ValueError("Invalid format")

        input_params = {"path": "/test/image.tiff"}

        result = tool.run(input_params)

        # Should return error
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)

    def test_ocr_tool_constants(self):
        """Test that required constants are defined"""
        self.assertIsNotNone(GET_JSON_PROMPT)
        self.assertIn("JSON", GET_JSON_PROMPT)

        self.assertIsNotNone(GET_JSON_WITH_REFERENCE_PROMPT)
        self.assertIn("reference", GET_JSON_WITH_REFERENCE_PROMPT.lower())

        self.assertIsInstance(SUPPORTED_MIME_FORMATS, dict)
        self.assertIn("JPEG", SUPPORTED_MIME_FORMATS)
        self.assertIn("PDF", SUPPORTED_MIME_FORMATS)

    @unit
    def test_ocr_tool_metadata(self):
        """Test OcrTool metadata"""
        tool = OcrTool()

        self.assertEqual(tool.name, "OcrTool")
        self.assertIsNotNone(tool.description)
        self.assertIn("structured data", tool.description.lower())
        self.assertEqual(tool.args_schema, OcrToolInput)

    @unit
    def test_ocr_tool_get_prompt_with_reference(self):
        """Test get_prompt method returns reference prompt when reference is available"""
        tool = OcrTool()

        # Test with reference image base64
        prompt = tool.get_prompt(reference_image_base64="base64_data", reference_image_path=None)  # type: ignore[arg-type]
        self.assertEqual(prompt, GET_JSON_WITH_REFERENCE_PROMPT)

        # Test with reference image path
        prompt = tool.get_prompt(reference_image_base64=None, reference_image_path="/path/to/ref.png")  # type: ignore[arg-type]
        self.assertEqual(prompt, GET_JSON_WITH_REFERENCE_PROMPT)

        # Test with both
        prompt = tool.get_prompt(reference_image_base64="base64_data", reference_image_path="/path/to/ref.png")  # type: ignore[arg-type]
        self.assertEqual(prompt, GET_JSON_WITH_REFERENCE_PROMPT)

    @unit
    def test_ocr_tool_get_prompt_without_reference(self):
        """Test get_prompt method returns standard prompt when no reference"""
        tool = OcrTool()

        prompt = tool.get_prompt(reference_image_base64=None, reference_image_path=None)  # type: ignore[arg-type]
        self.assertEqual(prompt, GET_JSON_PROMPT)

    @unit
    def test_ocr_tool_read_structured_output_with_schema(self):
        """Test read_structured_output adds schema to system prompt in compat mode"""
        from pydantic import BaseModel

        class TestSchema(BaseModel):
            field1: str
            field2: int

        tool = OcrTool()

        # Test with force_compat=True and schema
        result = tool.read_structured_output(None, force_compat=True, structured_schema=TestSchema)  # type: ignore[arg-type]

        self.assertIsNotNone(result)
        self.assertIn("Expected output JSON schema", result)
        self.assertIn("field1", result)
        self.assertIn("field2", result)

    @unit
    def test_ocr_tool_read_structured_output_without_compat(self):
        """Test read_structured_output returns None when not in compat mode"""
        from pydantic import BaseModel

        class TestSchema(BaseModel):
            field1: str

        tool = OcrTool()

        # Test with force_compat=False
        result = tool.read_structured_output(None, force_compat=False, structured_schema=TestSchema)  # type: ignore[arg-type]
        self.assertIsNone(result)

    @unit
    def test_ocr_tool_read_structured_output_no_schema(self):
        """Test read_structured_output returns None when no schema provided"""
        tool = OcrTool()

        result = tool.read_structured_output(None, force_compat=True, structured_schema=None)  # type: ignore[arg-type]
        self.assertIsNone(result)

    @patch("tools.OcrTool.get_llm")
    @unit
    def test_get_vision_model_response_unstructured(self, mock_get_llm):
        """Test get_vision_model_response for unstructured output"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"data": "extracted"}'
        mock_llm.invoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        messages = [{"role": "user", "content": "test"}]
        result = get_vision_model_response(messages, "gpt-4o")

        self.assertEqual(result, '{"data": "extracted"}')
        mock_llm.invoke.assert_called_once_with(messages)

    @patch("tools.OcrTool.get_llm")
    @unit
    def test_get_vision_model_response_structured(self, mock_get_llm):
        """Test get_vision_model_response with structured output"""
        from pydantic import BaseModel

        class TestSchema(BaseModel):
            data: str

        mock_llm = MagicMock()
        mock_structured_llm = MagicMock()
        mock_response = {"data": "extracted"}
        mock_structured_llm.invoke.return_value = mock_response
        mock_llm.with_structured_output.return_value = mock_structured_llm
        mock_get_llm.return_value = mock_llm

        messages = [{"role": "user", "content": "test"}]
        result = get_vision_model_response(messages, "gpt-4o", structured_schema=TestSchema)  # type: ignore[arg-type]

        self.assertEqual(result, {"data": "extracted"})
        mock_llm.with_structured_output.assert_called_once()

    @patch("tools.OcrTool.get_llm")
    @unit
    def test_get_vision_model_response_force_compat(self, mock_get_llm):
        """Test get_vision_model_response with force_compat skips structured wrapper"""
        from pydantic import BaseModel

        class TestSchema(BaseModel):
            data: str

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"data": "extracted"}'
        mock_llm.invoke.return_value = mock_response
        mock_get_llm.return_value = mock_llm

        messages = [{"role": "user", "content": "test"}]
        # With force_compat=True, should not use with_structured_output
        result = get_vision_model_response(messages, "gpt-5-mini", structured_schema=TestSchema, force_compat=True)  # type: ignore[arg-type]

        self.assertEqual(result, '{"data": "extracted"}')
        # Should NOT have called with_structured_output
        mock_llm.with_structured_output.assert_not_called()

    @patch("tools.OcrTool.cleanup_temp_files")
    @patch("tools.OcrTool.Path")
    @patch("copilot.core.vectordb_utils.find_similar_reference")
    @patch("tools.OcrTool.get_vision_model_response")
    @patch("tools.OcrTool.prepare_images_for_ocr")
    @patch("tools.OcrTool.read_mime")
    @patch("tools.OcrTool.get_file_path")
    @patch("tools.OcrTool.checktype")
    @unit
    def test_ocr_tool_run_with_structured_output(
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
        """Test OcrTool.run with structured_output parameter"""
        tool = OcrTool()
        tool.agent_id = "test_agent_123"

        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        temp_dir = tempfile.gettempdir()
        mock_get_file_path.return_value = os.path.join(temp_dir, "test.png")
        mock_read_mime.return_value = IMAGE_JPEG
        mock_prepare_images.return_value = (["base64_image"], [])
        mock_find_ref.return_value = (None, None)
        mock_get_response.return_value = {"invoice_number": "12345", "total": 100.0}

        input_params = {
            "path": "/test/image.png",
            "question": "Extract invoice",
            "structured_output": "Invoice",
        }

        result = tool.run(input_params)

        # Verify result is the dict from structured output
        self.assertIsInstance(result, dict)
        self.assertIn("invoice_number", result)

    @patch("tools.OcrTool.cleanup_temp_files")
    @patch("tools.OcrTool.Path")
    @patch("copilot.core.vectordb_utils.find_similar_reference")
    @patch("tools.OcrTool.get_vision_model_response")
    @patch("tools.OcrTool.prepare_images_for_ocr")
    @patch("tools.OcrTool.read_mime")
    @patch("tools.OcrTool.get_file_path")
    @patch("tools.OcrTool.checktype")
    @unit
    def test_ocr_tool_run_with_disable_threshold(
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
        """Test OcrTool.run with disable_threshold_filter parameter"""
        tool = OcrTool()
        tool.agent_id = "test_agent_123"

        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        temp_dir = tempfile.gettempdir()
        mock_get_file_path.return_value = os.path.join(temp_dir, "test.png")
        mock_read_mime.return_value = IMAGE_JPEG
        mock_prepare_images.return_value = (["base64_image"], [])
        mock_find_ref.return_value = ("/path/to/reference.png", "ref_base64")
        mock_get_response.return_value = '{"data": "extracted"}'

        input_params = {
            "path": "/test/image.png",
            "question": "Extract data",
            "disable_threshold_filter": True,
        }

        result = tool.run(input_params)

        # Verify result
        self.assertIsInstance(result, str)
        self.assertIn("data", result)

        # Verify find_similar_reference was called with ignore_env_threshold=True
        mock_find_ref.assert_called_once()
        call_kwargs = mock_find_ref.call_args
        self.assertTrue(
            call_kwargs[1].get("ignore_env_threshold", False)
            or (len(call_kwargs[0]) >= 3 and call_kwargs[0][2] is True)
        )


class TestGetLlmModel(unittest.TestCase):
    """Test suite for get_llm_model function"""

    @unit
    @patch("tools.OcrTool.read_optional_env_var")
    def test_get_llm_model_with_env_var_openai(self, mock_env_var):
        """Test get_llm_model when COPILOT_OCRTOOL_MODEL env var is set with OpenAI model"""
        mock_env_var.return_value = "gpt-4o"

        model, provider = get_llm_model("test-agent-id")

        self.assertEqual(model, "gpt-4o")
        self.assertEqual(provider, "openai")
        mock_env_var.assert_called_once_with("COPILOT_OCRTOOL_MODEL", None)

    @unit
    @patch("tools.OcrTool.read_optional_env_var")
    def test_get_llm_model_with_env_var_gemini(self, mock_env_var):
        """Test get_llm_model when COPILOT_OCRTOOL_MODEL env var is set with Gemini model"""
        mock_env_var.return_value = "gemini-2.5-pro"

        model, provider = get_llm_model("test-agent-id")

        self.assertEqual(model, "gemini-2.5-pro")
        self.assertEqual(provider, "gemini")
        mock_env_var.assert_called_once_with("COPILOT_OCRTOOL_MODEL", None)

    @unit
    @patch("tools.OcrTool.get_extra_info")
    @patch("tools.OcrTool.read_optional_env_var")
    def test_get_llm_model_from_extra_info(self, mock_env_var, mock_extra_info):
        """Test get_llm_model retrieves model from ThreadContext extra_info"""
        mock_env_var.return_value = None
        mock_extra_info.return_value = {
            "tool_config": {
                "agent-123": {
                    "EB58EEA0AA804C219C4D64260550745A": {  # OCR_TOOL_ID
                        "model": "claude-3-5-sonnet",
                        "provider": "anthropic",
                    }
                }
            }
        }

        model, provider = get_llm_model("agent-123")

        self.assertEqual(model, "claude-3-5-sonnet")
        self.assertEqual(provider, "anthropic")

    @unit
    @patch("tools.OcrTool.get_extra_info")
    @patch("tools.OcrTool.read_optional_env_var")
    def test_get_llm_model_from_extra_info_different_agent(
        self, mock_env_var, mock_extra_info
    ):
        """Test get_llm_model with multiple agents in extra_info"""
        mock_env_var.return_value = None
        mock_extra_info.return_value = {
            "tool_config": {
                "agent-123": {
                    "EB58EEA0AA804C219C4D64260550745A": {
                        "model": "gpt-4-turbo",
                        "provider": "openai",
                    }
                },
                "agent-456": {
                    "EB58EEA0AA804C219C4D64260550745A": {
                        "model": "gemini-1.5-flash",
                        "provider": "gemini",
                    }
                },
            }
        }

        model, provider = get_llm_model("agent-456")

        self.assertEqual(model, "gemini-1.5-flash")
        self.assertEqual(provider, "gemini")

    @unit
    @patch("tools.OcrTool.get_extra_info")
    @patch("tools.OcrTool.read_optional_env_var")
    def test_get_llm_model_defaults_when_no_config(self, mock_env_var, mock_extra_info):
        """Test get_llm_model returns defaults when no configuration is available"""
        mock_env_var.return_value = None
        mock_extra_info.return_value = None

        model, provider = get_llm_model("test-agent-id")

        self.assertEqual(model, "gpt-5-mini")  # DEFAULT_MODEL
        self.assertEqual(provider, "openai")  # DEFAULT_PROVIDER

    @unit
    @patch("tools.OcrTool.get_extra_info")
    @patch("tools.OcrTool.read_optional_env_var")
    def test_get_llm_model_defaults_when_agent_not_in_config(
        self, mock_env_var, mock_extra_info
    ):
        """Test get_llm_model returns defaults when agent is not in tool_config"""
        mock_env_var.return_value = None
        mock_extra_info.return_value = {
            "tool_config": {
                "different-agent": {
                    "EB58EEA0AA804C219C4D64260550745A": {
                        "model": "gpt-4",
                        "provider": "openai",
                    }
                }
            }
        }

        model, provider = get_llm_model("test-agent-id")

        self.assertEqual(model, "gpt-5-mini")
        self.assertEqual(provider, "openai")

    @unit
    @patch("tools.OcrTool.get_extra_info")
    @patch("tools.OcrTool.read_optional_env_var")
    def test_get_llm_model_defaults_when_tool_not_in_config(
        self, mock_env_var, mock_extra_info
    ):
        """Test get_llm_model returns defaults when OCR tool is not configured for agent"""
        mock_env_var.return_value = None
        mock_extra_info.return_value = {
            "tool_config": {
                "test-agent-id": {
                    "DIFFERENT_TOOL_ID": {"model": "gpt-4", "provider": "openai"}
                }
            }
        }

        model, provider = get_llm_model("test-agent-id")

        self.assertEqual(model, "gpt-5-mini")
        self.assertEqual(provider, "openai")

    @unit
    @patch("tools.OcrTool.get_extra_info")
    @patch("tools.OcrTool.read_optional_env_var")
    @patch("tools.OcrTool.copilot_error")
    def test_get_llm_model_handles_exception_in_extra_info(
        self, mock_error, mock_env_var, mock_extra_info
    ):
        """Test get_llm_model handles exceptions when reading extra_info gracefully"""
        mock_env_var.return_value = None
        mock_extra_info.side_effect = Exception("Connection error")

        model, provider = get_llm_model("test-agent-id")

        # Should return defaults even when exception occurs
        self.assertEqual(model, "gpt-5-mini")
        self.assertEqual(provider, "openai")
        # Should log the error
        mock_error.assert_called_once()
        self.assertIn(
            "Error reading ThreadContext extra_info", str(mock_error.call_args)
        )

    @unit
    @patch("tools.OcrTool.get_extra_info")
    @patch("tools.OcrTool.read_optional_env_var")
    def test_get_llm_model_handles_malformed_extra_info(
        self, mock_env_var, mock_extra_info
    ):
        """Test get_llm_model handles malformed extra_info structure"""
        mock_env_var.return_value = None
        # Missing nested keys
        mock_extra_info.return_value = {"tool_config": {}}

        model, provider = get_llm_model("test-agent-id")

        self.assertEqual(model, "gpt-5-mini")
        self.assertEqual(provider, "openai")

    @unit
    @patch("tools.OcrTool.get_extra_info")
    @patch("tools.OcrTool.read_optional_env_var")
    def test_get_llm_model_env_var_overrides_extra_info(
        self, mock_env_var, mock_extra_info
    ):
        """Test that environment variable takes precedence over extra_info"""
        mock_env_var.return_value = "gpt-4o-mini"
        mock_extra_info.return_value = {
            "tool_config": {
                "test-agent-id": {
                    "EB58EEA0AA804C219C4D64260550745A": {
                        "model": "claude-3-opus",
                        "provider": "anthropic",
                    }
                }
            }
        }

        model, provider = get_llm_model("test-agent-id")

        # Should use env var, not extra_info
        self.assertEqual(model, "gpt-4o-mini")
        self.assertEqual(provider, "openai")
        # extra_info should not even be called
        mock_extra_info.assert_not_called()

    @unit
    @patch("tools.OcrTool.read_optional_env_var")
    def test_get_llm_model_with_env_var_other_providers(self, mock_env_var):
        """Test get_llm_model correctly identifies non-gemini/openai providers as openai"""
        # Anthropic model should default to openai provider
        mock_env_var.return_value = "claude-3-5-sonnet"

        model, provider = get_llm_model("test-agent-id")

        self.assertEqual(model, "claude-3-5-sonnet")
        self.assertEqual(provider, "openai")  # Defaults to openai for non-gemini


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    unittest.main()
