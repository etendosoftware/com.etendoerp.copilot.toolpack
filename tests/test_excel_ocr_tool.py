import base64
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from tools.ExcelOCRTool import (
    GET_JSON_PROMPT,
    ExcelOCRTool,
    ExcelOCRToolInput,
)


class TestExcelOCRTool(unittest.TestCase):
    """Test suite for ExcelOCRTool"""

    def test_excel_ocr_tool_input_schema(self):
        """Test ExcelOCRToolInput schema validation"""
        valid_input = ExcelOCRToolInput(
            path="/test/file.xlsx", question="Extract all data"
        )
        self.assertEqual(valid_input.path, "/test/file.xlsx")
        self.assertEqual(valid_input.question, "Extract all data")

    def test_excel_ocr_tool_metadata(self):
        """Test ExcelOCRTool metadata"""
        tool = ExcelOCRTool()

        self.assertEqual(tool.name, "ExcelOCRTool")
        self.assertIsNotNone(tool.description)
        self.assertIn("Excel", tool.description)
        self.assertEqual(tool.args_schema, ExcelOCRToolInput)

    def test_get_json_prompt_constant(self):
        """Test that GET_JSON_PROMPT constant is defined"""
        self.assertIsNotNone(GET_JSON_PROMPT)
        self.assertIn("JSON", GET_JSON_PROMPT)
        self.assertIn("Extract", GET_JSON_PROMPT)

    def test_image_to_base64(self):
        """Test image_to_base64 method"""
        tool = ExcelOCRTool()

        # Create a temporary image file
        with tempfile.NamedTemporaryFile(suffix=".jpeg", delete=False) as tmp:
            tmp.write(b"fake image content")
            tmp_path = tmp.name

        try:
            result = tool.image_to_base64(tmp_path)

            self.assertIsInstance(result, str)
            # Verify it's valid base64
            decoded = base64.b64decode(result)
            self.assertEqual(decoded, b"fake image content")
        finally:
            os.unlink(tmp_path)

    def test_render_excel_to_images_single_sheet(self):
        """Test render_excel_to_images with single sheet Excel"""
        tool = ExcelOCRTool()

        # Create a temporary Excel file with one sheet
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            df = pd.DataFrame({"Column1": [1, 2, 3], "Column2": ["A", "B", "C"]})
            df.to_excel(tmp_path, index=False)

            result = tool.render_excel_to_images(tmp_path)

            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 1)  # One sheet = one image
            self.assertTrue(os.path.exists(result[0]))
            self.assertTrue(result[0].endswith(".jpeg"))

            # Cleanup generated images
            for img_path in result:
                os.unlink(img_path)
        finally:
            os.unlink(tmp_path)

    def test_render_excel_to_images_multiple_sheets(self):
        """Test render_excel_to_images with multiple sheets"""
        tool = ExcelOCRTool()

        # Create a temporary Excel file with multiple sheets
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with pd.ExcelWriter(tmp_path) as writer:
                df1 = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
                df2 = pd.DataFrame({"X": [5, 6], "Y": [7, 8]})
                df3 = pd.DataFrame({"P": [9, 10], "Q": [11, 12]})
                df1.to_excel(writer, sheet_name="Sheet1", index=False)
                df2.to_excel(writer, sheet_name="Sheet2", index=False)
                df3.to_excel(writer, sheet_name="Sheet3", index=False)

            result = tool.render_excel_to_images(tmp_path)

            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 3)  # Three sheets = three images

            for img_path in result:
                self.assertTrue(os.path.exists(img_path))
                self.assertTrue(img_path.endswith(".jpeg"))

            # Cleanup generated images
            for img_path in result:
                os.unlink(img_path)
        finally:
            os.unlink(tmp_path)

    @patch("tools.ExcelOCRTool.init_chat_model")
    @patch.object(ExcelOCRTool, "render_excel_to_images")
    @patch.object(ExcelOCRTool, "image_to_base64")
    def test_excel_ocr_tool_run_success(
        self, mock_img_to_b64, mock_render, mock_init_chat
    ):
        """Test ExcelOCRTool.run success case"""
        tool = ExcelOCRTool()

        # Setup mocks
        temp_dir = tempfile.gettempdir()
        mock_render.return_value = [os.path.join(temp_dir, "sheet_0.jpeg")]
        mock_img_to_b64.return_value = "base64_image_data"

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"data": [{"col1": "value1"}]}'
        mock_llm.invoke.return_value = mock_response
        mock_init_chat.return_value = mock_llm

        input_params = {"path": "/test/file.xlsx", "question": "Extract all data"}
        result = tool.run(input_params)

        self.assertEqual(result, '{"data": [{"col1": "value1"}]}')
        mock_render.assert_called_once_with("/test/file.xlsx")
        mock_img_to_b64.assert_called_once()
        mock_llm.invoke.assert_called_once()

    @patch("tools.ExcelOCRTool.init_chat_model")
    @patch.object(ExcelOCRTool, "render_excel_to_images")
    @patch.object(ExcelOCRTool, "image_to_base64")
    def test_excel_ocr_tool_run_uses_default_prompt(
        self, mock_img_to_b64, mock_render, mock_init_chat
    ):
        """Test ExcelOCRTool.run uses default prompt when question not provided"""
        tool = ExcelOCRTool()

        temp_dir = tempfile.gettempdir()
        mock_render.return_value = [os.path.join(temp_dir, "sheet_0.jpeg")]
        mock_img_to_b64.return_value = "base64_data"

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"result": "data"}'
        mock_llm.invoke.return_value = mock_response
        mock_init_chat.return_value = mock_llm

        # No question provided - should use GET_JSON_PROMPT
        input_params = {"path": "/test/file.xlsx"}
        tool.run(input_params)

        # Verify the default prompt was used in the messages
        call_args = mock_llm.invoke.call_args[0][0]
        message_content = call_args[0]["content"]
        text_content = [item for item in message_content if item.get("type") == "text"]
        self.assertEqual(text_content[0]["text"], GET_JSON_PROMPT)

    @patch("tools.ExcelOCRTool.init_chat_model")
    @patch.object(ExcelOCRTool, "render_excel_to_images")
    @patch.object(ExcelOCRTool, "image_to_base64")
    def test_excel_ocr_tool_run_multiple_sheets(
        self, mock_img_to_b64, mock_render, mock_init_chat
    ):
        """Test ExcelOCRTool.run with multiple sheet images"""
        tool = ExcelOCRTool()

        # Multiple sheets = multiple images
        temp_dir = tempfile.gettempdir()
        mock_render.return_value = [
            os.path.join(temp_dir, "sheet_0.jpeg"),
            os.path.join(temp_dir, "sheet_1.jpeg"),
        ]
        mock_img_to_b64.side_effect = ["base64_sheet1", "base64_sheet2"]

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"sheet1": {}, "sheet2": {}}'
        mock_llm.invoke.return_value = mock_response
        mock_init_chat.return_value = mock_llm

        input_params = {"path": "/test/file.xlsx", "question": "Extract all"}
        result = tool.run(input_params)

        self.assertEqual(result, '{"sheet1": {}, "sheet2": {}}')
        # Should have called image_to_base64 twice
        self.assertEqual(mock_img_to_b64.call_count, 2)

        # Verify messages contain two image payloads
        call_args = mock_llm.invoke.call_args[0][0]
        message_content = call_args[0]["content"]
        image_items = [
            item for item in message_content if item.get("type") == "image_url"
        ]
        self.assertEqual(len(image_items), 2)

    @patch.object(ExcelOCRTool, "render_excel_to_images")
    def test_excel_ocr_tool_run_error(self, mock_render):
        """Test ExcelOCRTool.run returns error on exception"""
        tool = ExcelOCRTool()

        mock_render.side_effect = Exception("File not found")

        input_params = {"path": "/nonexistent/file.xlsx", "question": "Extract"}
        result = tool.run(input_params)

        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("File not found", result["error"])

    @patch("os.path.exists")
    @patch("os.unlink")
    @patch("tools.ExcelOCRTool.init_chat_model")
    @patch.object(ExcelOCRTool, "render_excel_to_images")
    @patch.object(ExcelOCRTool, "image_to_base64")
    def test_excel_ocr_tool_run_cleans_up_temp_files(
        self, mock_img_to_b64, mock_render, mock_init_chat, mock_unlink, mock_exists
    ):
        """Test ExcelOCRTool.run cleans up temporary image files"""
        tool = ExcelOCRTool()

        temp_dir = tempfile.gettempdir()
        temp_files = [
            os.path.join(temp_dir, "sheet_0.jpeg"),
            os.path.join(temp_dir, "sheet_1.jpeg"),
        ]
        mock_render.return_value = temp_files
        mock_img_to_b64.return_value = "base64_data"
        mock_exists.return_value = True

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"data": "result"}'
        mock_llm.invoke.return_value = mock_response
        mock_init_chat.return_value = mock_llm

        input_params = {"path": "/test/file.xlsx", "question": "Extract"}
        tool.run(input_params)

        # Verify cleanup was attempted for each temp file
        self.assertEqual(mock_unlink.call_count, 2)

    @patch("os.path.exists")
    @patch("os.unlink")
    @patch.object(ExcelOCRTool, "image_to_base64")
    @patch.object(ExcelOCRTool, "render_excel_to_images")
    def test_excel_ocr_tool_run_cleans_up_on_error(
        self, mock_render, mock_img_to_b64, mock_unlink, mock_exists
    ):
        """Test ExcelOCRTool.run cleans up temp files even on error"""
        tool = ExcelOCRTool()

        temp_dir = tempfile.gettempdir()
        temp_file = os.path.join(temp_dir, "sheet_0.jpeg")
        temp_files = [temp_file]
        mock_render.return_value = temp_files
        mock_exists.return_value = True
        mock_img_to_b64.side_effect = Exception("Read error")

        input_params = {"path": "/test/file.xlsx", "question": "Extract"}
        result = tool.run(input_params)

        self.assertIn("error", result)
        # Cleanup should still happen
        mock_unlink.assert_called_once_with(temp_file)

    @patch("tools.ExcelOCRTool.read_optional_env_var")
    @patch("tools.ExcelOCRTool.init_chat_model")
    @patch.object(ExcelOCRTool, "render_excel_to_images")
    @patch.object(ExcelOCRTool, "image_to_base64")
    def test_excel_ocr_tool_run_uses_configured_model(
        self, mock_img_to_b64, mock_render, mock_init_chat, mock_read_env
    ):
        """Test ExcelOCRTool.run uses model from environment variable"""
        tool = ExcelOCRTool()

        temp_dir = tempfile.gettempdir()
        mock_render.return_value = [os.path.join(temp_dir, "sheet_0.jpeg")]
        mock_img_to_b64.return_value = "base64_data"
        mock_read_env.return_value = "gpt-4o-mini"

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"result": "data"}'
        mock_llm.invoke.return_value = mock_response
        mock_init_chat.return_value = mock_llm

        input_params = {"path": "/test/file.xlsx", "question": "Extract"}
        tool.run(input_params)

        # Verify the model from env var was used
        mock_read_env.assert_called_once_with("COPILOT_OCRTOOL_MODEL", "gpt-4.1")
        mock_init_chat.assert_called_once()
        call_kwargs = mock_init_chat.call_args[1]
        self.assertEqual(call_kwargs["model"], "gpt-4o-mini")
        self.assertEqual(call_kwargs["temperature"], 0)
        self.assertFalse(call_kwargs["streaming"])

    @patch("tools.ExcelOCRTool.init_chat_model")
    @patch.object(ExcelOCRTool, "render_excel_to_images")
    @patch.object(ExcelOCRTool, "image_to_base64")
    def test_excel_ocr_tool_run_message_format(
        self, mock_img_to_b64, mock_render, mock_init_chat
    ):
        """Test ExcelOCRTool.run builds correct message format"""
        tool = ExcelOCRTool()

        temp_dir = tempfile.gettempdir()
        mock_render.return_value = [os.path.join(temp_dir, "sheet_0.jpeg")]
        mock_img_to_b64.return_value = "test_base64"

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "{}"
        mock_llm.invoke.return_value = mock_response
        mock_init_chat.return_value = mock_llm

        input_params = {"path": "/test/file.xlsx", "question": "Test question"}
        tool.run(input_params)

        # Get the messages passed to invoke
        call_args = mock_llm.invoke.call_args[0][0]

        # Should be a list with one user message
        self.assertEqual(len(call_args), 1)
        self.assertEqual(call_args[0]["role"], "user")

        # Content should have image_url and text
        content = call_args[0]["content"]
        self.assertIsInstance(content, list)

        # Find image and text items
        image_items = [item for item in content if item.get("type") == "image_url"]
        text_items = [item for item in content if item.get("type") == "text"]

        self.assertEqual(len(image_items), 1)
        self.assertEqual(len(text_items), 1)

        # Verify image format
        self.assertIn("url", image_items[0]["image_url"])
        self.assertTrue(
            image_items[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
        )
        self.assertEqual(image_items[0]["image_url"]["detail"], "high")

        # Verify text
        self.assertEqual(text_items[0]["text"], "Test question")


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    unittest.main()
