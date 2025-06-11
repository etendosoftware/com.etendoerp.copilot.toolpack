import os
import unittest
from unittest.mock import patch, MagicMock

from langsmith import unit

from tools.OcrTool import convert_to_pil_img, get_image_payload_item, checktype, read_mime, OcrTool

IMAGE_JPEG = 'image/jpeg'


class TestOcrTool(unittest.TestCase):
    @unit
    def test_convert_to_pil_img(self):
        # Mocking a bitmap object
        mock_bitmap = MagicMock()
        mock_bitmap.width = 100
        mock_bitmap.height = 100
        mock_bitmap.buffer = b'\x00' * (100 * 100 * 4)
        mock_bitmap.format = 2
        mock_bitmap.mode = 'RGBA'
        mock_bitmap.stride = 400

        # Testing the conversion function
        pil_image = convert_to_pil_img(mock_bitmap)
        self.assertEqual(pil_image.size, (100, 100))
        self.assertFalse(pil_image.readonly)

    @unit
    def test_get_image_payload_item(self):
        img_b64 = 'sample_base64'
        mime = IMAGE_JPEG
        expected_output = {
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime};base64,{img_b64}",
                "detail": "high"
            }
        }
        self.assertEqual(get_image_payload_item(img_b64, mime), expected_output)

    @unit
    def test_checktype(self):
        valid_mimes = [IMAGE_JPEG, 'image/png', 'image/webp', 'image/gif', 'application/pdf']
        for mime in valid_mimes:
            try:
                checktype('dummy_url', mime)
            except Exception:
                self.fail(f"checktype() raised Exception unexpectedly for mime: {mime}")

        invalid_mime = 'image/tiff'
        with self.assertRaises(Exception):
            checktype('dummy_url', invalid_mime)

    @patch('filetype.guess')
    @unit
    def test_read_mime(self, mock_guess):
        mock_guess.return_value = MagicMock(mime=IMAGE_JPEG)
        self.assertEqual(read_mime('dummy_path'), IMAGE_JPEG)
        mock_guess.return_value = None
        self.assertIsNone(read_mime('dummy_path'))

    def test_ocr_tool_run(self):

        ocr_tool = OcrTool()
        input_params = {
            "path": "./resources/images/welcome-etendo.png",
            "question": "Describe the image and its content in detail.",
        }
        result = ocr_tool.run(input_params)

        self.assertIsNot(result, None)
        self.assertTrue(isinstance(result, str) or (isinstance(result, dict) and (
                "message" in result or "content" in result)))
        result_str = str(result)
        for keyword in ['etendo', 'welcome', 'wiki']:
            self.assertIn(keyword, result_str.lower())


if __name__ == '__main__':
    from dotenv import load_dotenv

    load_dotenv()

    unittest.main()
